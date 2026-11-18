"""Mô hình dữ liệu cho Automatic Lexical Discovery (docs/03 §7, docs/04 §6).

Lưu trữ ứng viên từ vựng, ngữ cảnh, giả thuyết nghĩa/cụm từ, bằng chứng và độ tin cậy.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text, Uuid)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base, IdMixin, TimestampMixin, utcnow

CANDIDATE_STATUS = ("new", "collecting_evidence", "needs_expert", "approved", "rejected", "merged", "purged")
PHRASE_TYPES = ("collocation", "phrase", "verb_phrase", "idiom", "proverb", "unknown")
EVIDENCE_TYPES = ("supports", "contradicts", "ambiguous")


class LexicalCandidate(IdMixin, TimestampMixin, Base):
    __tablename__ = "lexical_candidates"
    candidate_form: Mapped[str] = mapped_column(Text)
    normalized_form: Mapped[str] = mapped_column(Text, index=True)
    language_code: Mapped[str] = mapped_column(String(10), default="ede", index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    candidate_status: Mapped[str] = mapped_column(
        Enum(*CANDIDATE_STATUS, name="candidate_status", native_enum=False), default="new", index=True
    )
    discovery_version: Mapped[str] = mapped_column(String(30), default="discovery-v1")
    source_scope: Mapped[str] = mapped_column(String(60), default="forum_published")

    occurrences: Mapped[list[CandidateOccurrence]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", lazy="selectin"
    )
    clusters: Mapped[list[ContextCluster]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", lazy="selectin"
    )
    senses: Mapped[list[CandidateSense]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", lazy="selectin"
    )
    phrases: Mapped[list[CandidatePhrase]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", lazy="selectin"
    )


class CandidateOccurrence(IdMixin, Base):
    __tablename__ = "candidate_occurrences"
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("lexical_candidates.id", ondelete="CASCADE"), index=True
    )
    content_type: Mapped[str] = mapped_column(String(20))  # post, comment
    content_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    sentence_text: Mapped[str | None] = mapped_column(Text)  # Bị purge khi reject/rút consent
    left_context: Mapped[str | None] = mapped_column(Text)
    right_context: Mapped[str | None] = mapped_column(Text)
    dialect_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("dialects.id"))
    author_pseudonymous_id: Mapped[str | None] = mapped_column(String(64), index=True)
    source_ref: Mapped[str | None] = mapped_column(String(120))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    candidate: Mapped[LexicalCandidate] = relationship(back_populates="occurrences")


class ContextCluster(IdMixin, Base):
    __tablename__ = "context_clusters"
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("lexical_candidates.id", ondelete="CASCADE"), index=True
    )
    cluster_version: Mapped[str] = mapped_column(String(20), default="cluster-v1")
    syntactic_pattern: Mapped[str | None] = mapped_column(String(120))
    topic_label: Mapped[str | None] = mapped_column(String(80))
    dialect_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("dialects.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    candidate: Mapped[LexicalCandidate] = relationship(back_populates="clusters")
    senses: Mapped[list[CandidateSense]] = relationship(back_populates="cluster")


class CandidateSense(IdMixin, Base):
    __tablename__ = "candidate_senses"
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("lexical_candidates.id", ondelete="CASCADE"), index=True
    )
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("context_clusters.id", ondelete="SET NULL"), index=True
    )
    proposed_definition_vi: Mapped[str] = mapped_column(Text)
    proposed_definition_ede: Mapped[str | None] = mapped_column(Text)
    part_of_speech_hypothesis: Mapped[str | None] = mapped_column(String(60))
    support_score: Mapped[float] = mapped_column(Float, default=1.0)
    contradiction_score: Mapped[float] = mapped_column(Float, default=0.0)
    context_diversity_score: Mapped[float] = mapped_column(Float, default=1.0)
    source_independence_score: Mapped[float] = mapped_column(Float, default=1.0)
    expert_validation_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_version: Mapped[str] = mapped_column(String(20), default="score-v1")
    confidence_status: Mapped[str] = mapped_column(String(40), default="moderate_evidence")
    status: Mapped[str] = mapped_column(String(20), default="hypothesis")  # hypothesis, approved, rejected

    candidate: Mapped[LexicalCandidate] = relationship(back_populates="senses")
    cluster: Mapped[ContextCluster | None] = relationship(back_populates="senses")
    evidences: Mapped[list[CandidateEvidence]] = relationship(
        back_populates="sense", cascade="all, delete-orphan", lazy="selectin"
    )


class CandidatePhrase(IdMixin, Base):
    __tablename__ = "candidate_phrases"
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("lexical_candidates.id", ondelete="SET NULL"), index=True
    )
    phrase_text: Mapped[str] = mapped_column(Text)
    normalized_phrase: Mapped[str] = mapped_column(Text, index=True)
    phrase_type_hypothesis: Mapped[str] = mapped_column(
        Enum(*PHRASE_TYPES, name="phrase_type_hypothesis", native_enum=False), default="unknown"
    )
    proposed_meaning: Mapped[str | None] = mapped_column(Text)
    compositionality_assessment: Mapped[str | None] = mapped_column(String(60), default="non_compositional")
    stability_score: Mapped[float] = mapped_column(Float, default=1.0)
    support_score: Mapped[float] = mapped_column(Float, default=1.0)
    contradiction_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="hypothesis")

    candidate: Mapped[LexicalCandidate | None] = relationship(back_populates="phrases")
    evidences: Mapped[list[CandidateEvidence]] = relationship(
        back_populates="phrase", cascade="all, delete-orphan", lazy="selectin"
    )


class CandidateEvidence(IdMixin, Base):
    __tablename__ = "candidate_evidence"
    candidate_sense_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("candidate_senses.id", ondelete="CASCADE"), index=True
    )
    candidate_phrase_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("candidate_phrases.id", ondelete="CASCADE"), index=True
    )
    occurrence_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("candidate_occurrences.id", ondelete="SET NULL")
    )
    evidence_type: Mapped[str] = mapped_column(
        Enum(*EVIDENCE_TYPES, name="evidence_type", native_enum=False), default="supports"
    )
    reason: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(String(60), default="discovery-rules-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sense: Mapped[CandidateSense | None] = relationship(back_populates="evidences")
    phrase: Mapped[CandidatePhrase | None] = relationship(back_populates="evidences")
