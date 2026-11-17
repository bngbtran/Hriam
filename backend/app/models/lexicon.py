"""Master Lexicon, nguồn/giấy phép, corpus và dataset release (docs/03 §4–5).

Chỉ dữ liệu đã duyệt mới vào các bảng này. Đóng góp người dùng nằm ở contribution_submissions.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint,
                        Uuid)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base, IdMixin, TimestampMixin, utcnow


class OrthographyProfile(IdMixin, TimestampMixin, Base):
    __tablename__ = "orthography_profiles"
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text, default="")
    region_scope: Mapped[str] = mapped_column(String(255), default="")
    # Danh sách ký tự gợi ý trên bàn phím [{"char": "ƀ", "upper": "Ƀ", "name": "...", "note": "..."}]
    characters: Mapped[list] = mapped_column(JSON, default=list)
    examples: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(Enum("draft", "approved", "retired", name="profile_status",
                                             native_enum=False), default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(255))
    effective_from: Mapped[date | None] = mapped_column(Date)


class Dialect(IdMixin, Base):
    __tablename__ = "dialects"
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    region: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")


class License(IdMixin, Base):
    __tablename__ = "licenses"
    spdx_id_or_custom_name: Mapped[str] = mapped_column(String(120), unique=True)
    commercial_allowed: Mapped[bool | None] = mapped_column(Boolean)
    redistribution_allowed: Mapped[bool | None] = mapped_column(Boolean)
    derivatives_allowed: Mapped[bool | None] = mapped_column(Boolean)
    attribution_required: Mapped[bool | None] = mapped_column(Boolean)
    training_allowed: Mapped[bool | None] = mapped_column(Boolean)
    terms_url: Mapped[str | None] = mapped_column(String(500))
    # pending: chưa rõ điều khoản -> không được đưa vào release dùng production
    review_status: Mapped[str] = mapped_column(Enum("pending", "approved", "rejected", name="license_review",
                                                    native_enum=False), default="pending")
    notes: Mapped[str] = mapped_column(Text, default="")


class Source(IdMixin, Base):
    __tablename__ = "sources"
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(40))  # dictionary, corpus, community, expert, ...
    url_or_reference: Mapped[str] = mapped_column(String(500), default="")
    owner: Mapped[str] = mapped_column(String(255), default="")
    contact: Mapped[str] = mapped_column(String(255), default="")
    license_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("licenses.id", ondelete="RESTRICT"))
    access_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
    license: Mapped[License | None] = relationship(lazy="selectin")


ENTRY_TYPES = ("word", "multiword_expression", "idiom", "proverb", "phrase", "other")


class LexicalEntry(IdMixin, TimestampMixin, Base):
    __tablename__ = "lexical_entries"
    canonical_form: Mapped[str] = mapped_column(Text)
    normalized_form: Mapped[str] = mapped_column(Text, index=True)
    entry_type: Mapped[str] = mapped_column(Enum(*ENTRY_TYPES, name="entry_type", native_enum=False), default="word")
    language_code: Mapped[str] = mapped_column(String(10), default="ede", index=True)
    orthography_profile_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("orthography_profiles.id"))
    status: Mapped[str] = mapped_column(Enum("published", "deprecated", "under_revision", name="entry_status",
                                             native_enum=False), default="published", index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("sources.id", ondelete="RESTRICT"))
    source_ref: Mapped[str | None] = mapped_column(String(120))  # ví dụ mã mục/trang trong sách nguồn
    part_of_speech: Mapped[str | None] = mapped_column(String(60))
    loan_source: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str] = mapped_column(Text, default="")
    senses: Mapped[list[LexicalSense]] = relationship(back_populates="entry", order_by="LexicalSense.sense_number",
                                                      lazy="selectin")
    forms: Mapped[list[LexicalForm]] = relationship(lazy="selectin")
    source: Mapped[Source | None] = relationship(lazy="selectin")


class LexicalForm(IdMixin, Base):
    __tablename__ = "lexical_forms"
    entry_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("lexical_entries.id", ondelete="RESTRICT"),
                                                index=True)
    form_text: Mapped[str] = mapped_column(Text)
    normalized_form: Mapped[str] = mapped_column(Text, index=True)
    form_type: Mapped[str] = mapped_column(String(40), default="variant")  # variant, dialectal, historical, alt
    dialect_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("dialects.id"))
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("sources.id"))
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")


class LexicalSense(IdMixin, TimestampMixin, Base):
    __tablename__ = "lexical_senses"
    entry_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("lexical_entries.id", ondelete="RESTRICT"),
                                                index=True)
    sense_number: Mapped[int] = mapped_column(Integer, default=1)
    definition_vi: Mapped[str] = mapped_column(Text)
    definition_vi_key: Mapped[str] = mapped_column(Text, index=True)
    definition_ede: Mapped[str | None] = mapped_column(Text)
    part_of_speech: Mapped[str | None] = mapped_column(String(60))
    semantic_domain: Mapped[str | None] = mapped_column(String(80))
    usage_register: Mapped[str | None] = mapped_column(String(80))
    literal_or_figurative: Mapped[str | None] = mapped_column(String(20))
    dialect_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("dialects.id"))
    # draft: có trong nguồn nhưng chưa được chuyên gia xác minh; verified: Language Expert đã xác minh
    status: Mapped[str] = mapped_column(Enum("draft", "verified", "deprecated", name="sense_status",
                                             native_enum=False), default="draft", index=True)
    verification_level: Mapped[str] = mapped_column(String(40), default="source_unreviewed")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("sources.id"))
    entry: Mapped[LexicalEntry] = relationship(back_populates="senses")
    examples: Mapped[list[SenseExample]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class CorpusExample(IdMixin, TimestampMixin, Base):
    __tablename__ = "corpus_examples"
    text_ede: Mapped[str] = mapped_column(Text)
    text_vi: Mapped[str] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(Text)
    dialect_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("dialects.id"))
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("sources.id"))
    verification_status: Mapped[str] = mapped_column(String(30), default="unreviewed")


class SenseExample(Base):
    __tablename__ = "sense_examples"
    sense_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("lexical_senses.id", ondelete="CASCADE"),
                                                primary_key=True)
    example_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("corpus_examples.id", ondelete="RESTRICT"),
                                                  primary_key=True)
    role: Mapped[str] = mapped_column(Enum("illustrates", "contrasts", "ambiguous", name="example_role",
                                           native_enum=False), default="illustrates")
    position: Mapped[int] = mapped_column(Integer, default=0)
    example: Mapped[CorpusExample] = relationship(lazy="selectin")


class PhraseComponent(IdMixin, Base):
    __tablename__ = "phrase_components"
    phrase_entry_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("lexical_entries.id"), index=True)
    component_entry_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("lexical_entries.id"))
    component_text: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    syntactic_role: Mapped[str | None] = mapped_column(String(60))


QUALITY = ("unreviewed", "machine_translated", "community_reviewed", "expert_verified", "rejected")


class TranslationCorpus(IdMixin, Base):
    """Cặp câu song song; chỉ community_reviewed/expert_verified mới dùng làm translation memory."""
    __tablename__ = "translation_corpus"
    source_text: Mapped[str] = mapped_column(Text)
    source_key: Mapped[str] = mapped_column(Text, index=True)
    target_text: Mapped[str] = mapped_column(Text)
    source_lang: Mapped[str] = mapped_column(String(10))
    target_lang: Mapped[str] = mapped_column(String(10))
    domain: Mapped[str | None] = mapped_column(String(60))
    dialect_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("dialects.id"))
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("sources.id", ondelete="RESTRICT"))
    license_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("licenses.id", ondelete="RESTRICT"))
    quality_status: Mapped[str] = mapped_column(Enum(*QUALITY, name="corpus_quality", native_enum=False),
                                                default="unreviewed", index=True)
    consent_scope: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DatasetRelease(IdMixin, Base):
    __tablename__ = "dataset_releases"
    version: Mapped[str] = mapped_column(String(40), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="released")
    manifest_uri: Mapped[str] = mapped_column(String(500))
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    record_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    license_inventory: Mapped[list] = mapped_column(JSON, default=list)
    change_summary: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DatasetReleaseItem(IdMixin, Base):
    __tablename__ = "dataset_release_items"
    __table_args__ = (UniqueConstraint("release_id", "record_type", "record_id"),)
    release_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("dataset_releases.id", ondelete="RESTRICT"),
                                                  index=True)
    record_type: Mapped[str] = mapped_column(String(40))
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    record_version: Mapped[str] = mapped_column(String(40))
    inclusion_reason: Mapped[str] = mapped_column(String(120), default="")
