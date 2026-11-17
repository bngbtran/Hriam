"""Mật khẩu (Argon2id), access token JWT ngắn hạn, refresh token xoay vòng, HMAC số điện thoại (docs/08 §2–3)."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from .config import settings
from .db import utcnow

_hasher = PasswordHasher()  # mặc định argon2id


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    seconds = settings.access_token_minutes * 60
    now = utcnow()
    token = jwt.encode({"sub": str(user_id), "type": "access", "iat": now, "exp": now + timedelta(seconds=seconds),
                        "jti": secrets.token_hex(8)}, settings.secret_key, algorithm="HS256")
    return token, seconds


def decode_access_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        return None


def new_refresh_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(48)
    return token, sha256(token)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_phone(raw: str) -> str | None:
    """Chuẩn E.164. Số Việt Nam dạng 0xxxxxxxxx được đổi thành +84xxxxxxxxx."""
    digits = re.sub(r"[\s().-]", "", raw or "")
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if re.fullmatch(r"0\d{9,10}", digits):
        digits = "+84" + digits[1:]
    return digits if re.fullmatch(r"\+[1-9]\d{7,14}", digits) else None


def phone_hmac(e164: str) -> tuple[str, str]:
    """HMAC-SHA256 có khoá bí mật lưu ngoài DB. Không phải ẩn danh tuyệt đối."""
    digest = hmac.new(settings.phone_hmac_key.encode(), e164.encode(), hashlib.sha256).hexdigest()
    return digest, settings.phone_hmac_key_version
