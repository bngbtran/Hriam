"""Mô hình dữ liệu cho Kho tư liệu văn hoá (Cultural Archive - docs/01 §4.10, docs/08 §7-8).

Quản lý tư liệu văn hoá, truyện kể, lời hát, tri thức dân gian với các cấp quyền truy cập.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (JSON, DateTime, Enum, ForeignKey, String, Text, Uuid)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base, IdMixin, TimestampMixin, utcnow

CULTURE_CATEGORIES = ("story", "song", "proverb_idiom", "history", "custom", "term", "other")
ACCESS_TIERS = ("public", "community", "restricted", "private")
CULTURE_STATUS = ("draft", "pending_review", "published", "rejected")


class CulturalItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "cultural_items"
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(
        Enum(*CULTURE_CATEGORIES, name="cultural_category", native_enum=False), default="story"
    )
    content_ede: Mapped[str] = mapped_column(Text)
    content_vi: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    storyteller_or_author: Mapped[str | None] = mapped_column(String(200))
    dialect_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("dialects.id"))
    region: Mapped[str | None] = mapped_column(String(200))
    access_tier: Mapped[str] = mapped_column(
        Enum(*ACCESS_TIERS, name="cultural_access_tier", native_enum=False), default="public", index=True
    )
    license_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("licenses.id"))
    source_ref: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(
        Enum(*CULTURE_STATUS, name="cultural_item_status", native_enum=False), default="published", index=True
    )
    consent_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)

    dialect: Mapped[object | None] = relationship("Dialect", lazy="selectin")
    license: Mapped[object | None] = relationship("License", lazy="selectin")
