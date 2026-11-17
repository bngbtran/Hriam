"""Đóng góp, phản hồi dịch, diễn đàn, kiểm duyệt, strike, khiếu nại, audit, thông báo (docs/03 §6, §8, §9, §11)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base, IdMixin, TimestampMixin, utcnow

SUBMISSION_TYPES = ("word", "sense", "phrase", "sentence_pair", "audio", "correction")
SUBMISSION_STATUS = ("pending", "in_review", "approved", "rejected", "withdrawn", "purged")


class ContributionSubmission(IdMixin, TimestampMixin, Base):
    __tablename__ = "contribution_submissions"
    submitter_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    submission_type: Mapped[str] = mapped_column(Enum(*SUBMISSION_TYPES, name="submission_type", native_enum=False))
    # Nội dung: bị xoá (NULL) khi reject/rút; chỉ còn metadata kiểm toán tối thiểu.
    raw_text: Mapped[str | None] = mapped_column(Text)
    proposed_translation: Mapped[str | None] = mapped_column(Text)
    context_text: Mapped[str | None] = mapped_column(Text)
    phrase_type: Mapped[str | None] = mapped_column(String(40))
    target_entry_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("lexical_entries.id"))
    dialect_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("dialects.id"))
    source_note: Mapped[str | None] = mapped_column(Text)
    attachment_id: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(Enum(*SUBMISSION_STATUS, name="submission_status", native_enum=False),
                                        default="pending", index=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_code: Mapped[str | None] = mapped_column(String(60))
    decision_note: Mapped[str | None] = mapped_column(Text)
    result_entry_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("lexical_entries.id"))
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_to_publication: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_to_research: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_to_model_training: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_version: Mapped[str] = mapped_column(String(20), default="2026-11")


class TranslationRecord(IdMixin, Base):
    """Lịch sử dịch: chỉ lưu khi người dùng bật save_translation_history."""
    __tablename__ = "translation_history"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_text: Mapped[str] = mapped_column(Text)
    translated_text: Mapped[str] = mapped_column(Text)
    source_language: Mapped[str] = mapped_column(String(10))
    target_language: Mapped[str] = mapped_column(String(10))
    translation_status: Mapped[str] = mapped_column(String(30))
    model_version: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TranslationFeedback(IdMixin, Base):
    __tablename__ = "translation_feedback"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    translation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    source_text: Mapped[str] = mapped_column(Text)
    translated_text: Mapped[str] = mapped_column(Text)
    source_language: Mapped[str] = mapped_column(String(10))
    target_language: Mapped[str] = mapped_column(String(10))
    error_type: Mapped[str] = mapped_column(String(40))
    suggested_translation: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(String(120))
    contribution_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("contribution_submissions.id"))
    consent_to_research: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


CONTENT_STATUS = ("draft", "pending_moderation", "pending_human_review", "published", "rejected", "removed")
FORUM_CATEGORIES = ("hoi-dap", "tu-vung", "phat-am", "phuong-ngu", "van-hoa", "hoc-tieng", "gop-y-ban-dich")


class ForumPost(IdMixin, TimestampMixin, Base):
    __tablename__ = "forum_posts"
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(Enum(*FORUM_CATEGORIES, name="forum_category", native_enum=False))
    title: Mapped[str] = mapped_column(String(200))
    body_text: Mapped[str] = mapped_column(Text)
    language_hint: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(Enum(*CONTENT_STATUS, name="content_status", native_enum=False),
                                        default="pending_moderation", index=True)
    consent_research_analysis: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comments: Mapped[list[ForumComment]] = relationship(back_populates="post", order_by="ForumComment.created_at")


class ForumComment(IdMixin, TimestampMixin, Base):
    __tablename__ = "forum_comments"
    post_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("forum_posts.id"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("forum_comments.id"))
    body_text: Mapped[str] = mapped_column(Text)
    language_hint: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(Enum(*CONTENT_STATUS, name="content_status", native_enum=False),
                                        default="pending_moderation", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    post: Mapped[ForumPost] = relationship(back_populates="comments")


class ContentReport(IdMixin, Base):
    __tablename__ = "content_reports"
    __table_args__ = (UniqueConstraint("reporter_id", "content_type", "content_id"),)
    reporter_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    content_type: Mapped[str] = mapped_column(String(20))
    content_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    reason_code: Mapped[str] = mapped_column(String(60))
    note: Mapped[str | None] = mapped_column(Text)
    case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("moderation_cases.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


CASE_STATUS = ("pending_automated", "pending_human_review", "resolved")


class ModerationCase(IdMixin, Base):
    __tablename__ = "moderation_cases"
    content_type: Mapped[str] = mapped_column(String(20))  # post, comment
    content_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    trigger: Mapped[str] = mapped_column(String(20), default="submission")  # submission, edit, report
    policy_version: Mapped[str] = mapped_column(String(40))
    detector_results: Mapped[dict] = mapped_column(JSON, default=dict)
    language_detected: Mapped[str | None] = mapped_column(String(10))
    risk_level: Mapped[str] = mapped_column(String(20), default="unknown")  # low, medium, high, unknown
    status: Mapped[str] = mapped_column(Enum(*CASE_STATUS, name="case_status", native_enum=False), index=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    # publish, reject, remove, overturned
    final_decision: Mapped[str | None] = mapped_column(String(20))
    decision_reason: Mapped[str | None] = mapped_column(String(60))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actions: Mapped[list[ModerationAction]] = relationship(order_by="ModerationAction.created_at", lazy="selectin")


class ModerationAction(IdMixin, Base):
    __tablename__ = "moderation_actions"
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("moderation_cases.id"), index=True)
    actor_type: Mapped[str] = mapped_column(String(20))  # system, user
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    reason_code: Mapped[str | None] = mapped_column(String(60))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserStrikeEvent(IdMixin, Base):
    """Sổ strike bất biến: không sửa/xoá dòng cũ; strike hiệu lực = tổng quantity."""
    __tablename__ = "user_strike_events"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    source_moderation_case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("moderation_cases.id"))
    event_type: Mapped[str] = mapped_column(Enum("strike_applied", "strike_revoked", "strike_reinstated",
                                                 "admin_adjustment", name="strike_event", native_enum=False))
    quantity: Mapped[int] = mapped_column(Integer)
    reason_code: Mapped[str] = mapped_column(String(60))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class UserAppeal(IdMixin, Base):
    __tablename__ = "user_appeals"
    __table_args__ = (UniqueConstraint("user_id", "moderation_case_id"),)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    moderation_case_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("moderation_cases.id"))
    appeal_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Enum("pending", "accepted", "rejected", name="appeal_status",
                                             native_enum=False), default="pending", index=True)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminAuditLog(IdMixin, Base):
    """Không ghi token, số điện thoại, nội dung bị reject hay audio."""
    __tablename__ = "admin_audit_logs"
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    reason_code: Mapped[str | None] = mapped_column(String(60))
    metadata_safe_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Notification(IdMixin, Base):
    __tablename__ = "notifications"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(200))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
