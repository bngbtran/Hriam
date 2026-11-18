"""Mô hình dữ liệu cho Live Conversation & Realtime (docs/03 §10, docs/06).

Lưu trữ phòng hội thoại, người tham gia, và các lượt hội thoại (turns).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, Uuid)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base, IdMixin, TimestampMixin, utcnow

ROOM_MODES = ("shared_device", "two_devices")
ROOM_STATUS = ("active", "closed", "expired")
ENDPOINTING_MODES = ("push_to_talk", "auto_pause", "sentence_aware")
TURN_STATUS = ("speaking", "transcribed", "translated", "completed", "error")


class ConversationRoom(IdMixin, TimestampMixin, Base):
    __tablename__ = "conversation_rooms"
    room_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    room_code_hash: Mapped[str] = mapped_column(String(64), index=True)
    mode: Mapped[str] = mapped_column(
        Enum(*ROOM_MODES, name="conversation_mode", native_enum=False), default="shared_device"
    )
    language_a: Mapped[str] = mapped_column(String(10), default="ede")
    language_b: Mapped[str] = mapped_column(String(10), default="vi")
    endpointing_mode: Mapped[str] = mapped_column(
        Enum(*ENDPOINTING_MODES, name="endpointing_mode", native_enum=False), default="push_to_talk"
    )
    silence_threshold_ms: Mapped[int] = mapped_column(Integer, default=1500)
    status: Mapped[str] = mapped_column(
        Enum(*ROOM_STATUS, name="room_status", native_enum=False), default="active", index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    save_audio_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    save_transcript_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    participants: Mapped[list[ConversationParticipant]] = relationship(
        back_populates="room", cascade="all, delete-orphan", lazy="selectin"
    )
    turns: Mapped[list[ConversationTurn]] = relationship(
        back_populates="room", cascade="all, delete-orphan", order_by="ConversationTurn.sequence_no", lazy="selectin"
    )


class ConversationParticipant(IdMixin, Base):
    __tablename__ = "conversation_participants"
    room_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversation_rooms.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    participant_alias: Mapped[str] = mapped_column(String(60))
    language_preference: Mapped[str] = mapped_column(String(10), default="vi")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    room: Mapped[ConversationRoom] = relationship(back_populates="participants")


class ConversationTurn(IdMixin, Base):
    __tablename__ = "conversation_turns"
    room_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversation_rooms.id", ondelete="CASCADE"), index=True
    )
    participant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("conversation_participants.id", ondelete="SET NULL")
    )
    sequence_no: Mapped[int] = mapped_column(Integer, default=1)
    input_language: Mapped[str] = mapped_column(String(10))
    audio_ref: Mapped[str | None] = mapped_column(String(255))
    transcript_draft: Mapped[str | None] = mapped_column(Text)
    transcript_final: Mapped[str] = mapped_column(Text)
    translated_text: Mapped[str] = mapped_column(Text)
    translation_model_version: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(
        Enum(*TURN_STATUS, name="turn_status", native_enum=False), default="completed"
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    room: Mapped[ConversationRoom] = relationship(back_populates="turns")
