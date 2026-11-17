"""Tài khoản, phân quyền, phiên đăng nhập, hạn chế số điện thoại (docs/03 §3)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base, IdMixin, TimestampMixin, utcnow

USER_STATUS = ("active", "suspended", "permanently_banned", "deleted")


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    email_normalized: Mapped[str | None] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Không lưu số điện thoại rõ; chỉ HMAC có khoá để tra trùng/hạn chế (docs/08 §3).
    phone_hmac: Mapped[str | None] = mapped_column(String(128), index=True)
    phone_hmac_key_version: Mapped[str | None] = mapped_column(String(16))
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Enum(*USER_STATUS, name="user_status", native_enum=False), default="active",
                                        index=True)
    save_translation_history: Mapped[bool] = mapped_column(Boolean, default=False)
    roles: Mapped[list[UserRole]] = relationship(back_populates="user", cascade="all, delete-orphan", lazy="selectin",
                                                  foreign_keys="UserRole.user_id")

    @property
    def role_names(self) -> list[str]:
        return sorted({r.role.name for r in self.roles})


class Role(IdMixin, Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(40), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    permissions: Mapped[list[RolePermission]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class Permission(IdMixin, Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(60), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("permissions.id", ondelete="CASCADE"),
                                                     primary_key=True)
    permission: Mapped[Permission] = relationship(lazy="selectin")


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User] = relationship(back_populates="roles", foreign_keys=[user_id])
    role: Mapped[Role] = relationship(lazy="selectin")


class RefreshSession(IdMixin, Base):
    """Refresh token: chỉ lưu SHA-256 của token ngẫu nhiên; xoay vòng mỗi lần dùng, thu hồi khi đăng xuất/khoá."""
    __tablename__ = "refresh_sessions"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserPhoneRestriction(IdMixin, Base):
    __tablename__ = "user_phone_restrictions"
    phone_hmac: Mapped[str] = mapped_column(String(128), index=True)
    key_version: Mapped[str] = mapped_column(String(16))
    restriction_type: Mapped[str] = mapped_column(
        Enum("registration_block", "manual_review", name="restriction_type", native_enum=False))
    reason_code: Mapped[str] = mapped_column(String(60))
    source_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(Enum("active", "released", "expired", name="restriction_status",
                                             native_enum=False), default="active", index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    released_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(Text)


class IdempotencyKey(Base):
    """Khoá idempotency cho approve/reject, ban/unban, submit (docs/07 §1)."""
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("actor_id", "scope", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    scope: Mapped[str] = mapped_column(String(120))
    key: Mapped[str] = mapped_column(String(120))
    response_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PhoneVerificationCode(IdMixin, Base):
    """Mã xác thực số điện thoại (docs/07 §2)."""
    __tablename__ = "phone_verification_codes"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    phone_hmac: Mapped[str] = mapped_column(String(128), index=True)
    phone_display_masked: Mapped[str] = mapped_column(String(20))
    code: Mapped[str] = mapped_column(String(10))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

