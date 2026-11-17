"""Dependency dùng chung: người dùng hiện tại, kiểm tra quyền, audit, idempotency, phân trang cursor."""
from __future__ import annotations

import base64
import json
from collections.abc import Callable
from typing import Any

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AdminAuditLog, IdempotencyKey, Notification, User
from .db import get_db
from .errors import AppError, forbidden
from .security import decode_access_token


def client_key(request: Request, user: User | None = None) -> str:
    if user:
        return str(user.id)
    from .config import settings
    forwarded = request.headers.get("x-forwarded-for") if settings.trust_proxy else None
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def permissions_of(user: User) -> set[str]:
    return {rp.permission.code for ur in user.roles for rp in ur.role.permissions}


def optional_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    user_id = decode_access_token(authorization.split(" ", 1)[1].strip())
    if not user_id:
        raise AppError(401, "UNAUTHENTICATED", "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")
    user = db.get(User, user_id)
    if not user or user.status == "deleted":
        raise AppError(401, "UNAUTHENTICATED", "Tài khoản không còn tồn tại.")
    return user


def current_user(user: User | None = Depends(optional_user)) -> User:
    if not user:
        raise AppError(401, "UNAUTHENTICATED", "Vui lòng đăng nhập.")
    return user


def active_user(user: User = Depends(current_user)) -> User:
    if user.status != "active":
        raise AppError(403, "ACCOUNT_RESTRICTED", "Tài khoản đang bị khoá. Bạn vẫn có thể xem strike và gửi khiếu nại.")
    return user


def require(*perms: str) -> Callable[..., User]:
    def checker(user: User = Depends(active_user)) -> User:
        if not set(perms) <= permissions_of(user):
            raise forbidden()
        return user
    return checker


def audit(db: Session, actor: User | None, action: str, target_type: str, target_id: Any,
          reason_code: str | None = None, **safe_meta: Any) -> None:
    db.add(AdminAuditLog(actor_id=actor.id if actor else None, action=action, target_type=target_type,
                         target_id=str(target_id), reason_code=reason_code, metadata_safe_json=safe_meta))


def notify(db: Session, user_id: Any, kind: str, title: str, body: str = "", link: str | None = None) -> None:
    db.add(Notification(user_id=user_id, kind=kind, title=title, body=body, link=link))


def idempotency_key(key: str | None = Header(default=None, alias="Idempotency-Key")) -> str:
    if not key or len(key) > 120:
        raise AppError(400, "IDEMPOTENCY_KEY_REQUIRED", "Thiếu header Idempotency-Key.")
    return key


def idempotent_replay(db: Session, actor: User, scope: str, key: str) -> dict | None:
    row = db.scalar(select(IdempotencyKey).where(IdempotencyKey.actor_id == actor.id, IdempotencyKey.scope == scope,
                                                 IdempotencyKey.key == key))
    return json.loads(row.response_json) if row else None


def remember_idempotent(db: Session, actor: User, scope: str, key: str, response: dict) -> None:
    db.add(IdempotencyKey(actor_id=actor.id, scope=scope, key=key, response_json=json.dumps(response, default=str)))


def encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(0, int(base64.urlsafe_b64decode(cursor.encode()).decode()))
    except (ValueError, UnicodeDecodeError):
        raise AppError(400, "BAD_CURSOR", "Cursor không hợp lệ.")


def paginate(db: Session, stmt, cursor: str | None, limit: int) -> tuple[list, str | None]:
    limit = max(1, min(limit, 100))
    offset = decode_cursor(cursor)
    rows = list(db.scalars(stmt.offset(offset).limit(limit + 1)))
    return rows[:limit], (encode_cursor(offset + limit) if len(rows) > limit else None)
