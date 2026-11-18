"""Đăng ký/đăng nhập, phiên refresh, strike, khoá/mở khoá, hạn chế số điện thoại (docs/01 §6, docs/05 §6–8)."""
from __future__ import annotations

import re
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import utcnow
from ..core.deps import audit, notify
from ..core.errors import AppError
from ..core.security import (create_access_token, hash_password, new_refresh_token, normalize_phone, phone_hmac,
                             sha256, verify_password)
from ..models import (PhoneVerificationCode, RefreshSession, Role, User, UserPhoneRestriction,
                      UserRole, UserStrikeEvent)

BAN_THRESHOLD = 3  # khoá khi strike hiệu lực > 3 (strike thứ 4) — ADR-010
USERNAME = re.compile(r"^[a-zA-Z0-9_.]{3,40}$")


def assign_role(db: Session, user: User, role_name: str, granted_by: User | None = None) -> None:
    role = db.scalar(select(Role).where(Role.name == role_name))
    if not role:
        raise AppError(422, "UNKNOWN_ROLE", f"Không có vai trò {role_name}.")
    if role_name not in user.role_names:
        user.roles.append(UserRole(role=role, granted_by=granted_by.id if granted_by else None))


def register(db: Session, username: str, display_name: str, password: str, email: str | None,
             phone: str | None) -> User:
    if not USERNAME.match(username):
        raise AppError(422, "INVALID_USERNAME", "Tên đăng nhập 3–40 ký tự: chữ không dấu, số, dấu chấm, gạch dưới.")
    if len(password) < 10:
        raise AppError(422, "WEAK_PASSWORD", "Mật khẩu cần ít nhất 10 ký tự.")
    if db.scalar(select(User).where(func.lower(User.username) == username.lower())):
        raise AppError(409, "USERNAME_TAKEN", "Tên đăng nhập đã được dùng.")
    email_norm = email.strip().lower() if email else None
    if email_norm and db.scalar(select(User).where(User.email_normalized == email_norm)):
        raise AppError(409, "EMAIL_TAKEN", "Email đã được dùng.")
    digest = version = None
    if phone:
        e164 = normalize_phone(phone)
        if not e164:
            raise AppError(422, "INVALID_PHONE", "Số điện thoại không hợp lệ.")
        digest, version = phone_hmac(e164)
        if db.scalar(select(UserPhoneRestriction).where(UserPhoneRestriction.phone_hmac == digest,
                                                        UserPhoneRestriction.status == "active")):
            raise AppError(403, "REGISTRATION_BLOCKED",
                           "Số điện thoại này không thể dùng để đăng ký. Liên hệ quản trị viên nếu bạn cho rằng có nhầm lẫn.")
    user = User(username=username, display_name=display_name.strip() or username, email_normalized=email_norm,
                password_hash=hash_password(password), phone_hmac=digest, phone_hmac_key_version=version)
    db.add(user)
    db.flush()
    assign_role(db, user, "user")
    return user


def authenticate(db: Session, username: str, password: str) -> User:
    user = db.scalar(select(User).where(func.lower(User.username) == username.lower()))
    if not user or not verify_password(user.password_hash, password) or user.status == "deleted":
        raise AppError(401, "INVALID_CREDENTIALS", "Sai tên đăng nhập hoặc mật khẩu.")
    return user


def issue_tokens(db: Session, user: User) -> dict:
    access, expires_in = create_access_token(user.id)
    refresh, digest = new_refresh_token()
    db.add(RefreshSession(user_id=user.id, token_hash=digest,
                          expires_at=utcnow() + timedelta(days=settings.refresh_token_days)))
    return {"access_token": access, "token_type": "bearer", "expires_in": expires_in, "refresh_token": refresh}


def rotate_refresh(db: Session, token: str) -> tuple[User, dict]:
    session = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == sha256(token)))
    now = utcnow()
    if not session:
        raise AppError(401, "INVALID_REFRESH", "Phiên đăng nhập không hợp lệ.")
    if session.revoked_at:  # dùng lại token đã xoay: có thể bị lộ -> thu hồi mọi phiên
        revoke_all_sessions(db, session.user_id)
        db.commit()
        raise AppError(401, "INVALID_REFRESH", "Phiên đăng nhập không hợp lệ.")
    expires = session.expires_at if session.expires_at.tzinfo else session.expires_at.replace(tzinfo=now.tzinfo)
    if expires < now:
        raise AppError(401, "INVALID_REFRESH", "Phiên đăng nhập đã hết hạn.")
    user = db.get(User, session.user_id)
    session.revoked_at = now
    return user, issue_tokens(db, user)


def revoke_session(db: Session, token: str) -> None:
    db.execute(update(RefreshSession).where(RefreshSession.token_hash == sha256(token),
                                            RefreshSession.revoked_at.is_(None)).values(revoked_at=utcnow()))


def revoke_all_sessions(db: Session, user_id) -> None:
    db.execute(update(RefreshSession).where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
               .values(revoked_at=utcnow()))


# ---------- Strike ----------

def effective_strikes(db: Session, user_id) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(UserStrikeEvent.quantity), 0))
                         .where(UserStrikeEvent.user_id == user_id)) or 0)


def apply_strike(db: Session, user: User, case_id, reason_code: str, actor: User) -> tuple[bool, int]:
    """Một case chỉ tính tối đa một strike hiệu lực. Trả về (đã áp dụng mới?, tổng strike hiệu lực)."""
    net = db.scalar(select(func.coalesce(func.sum(UserStrikeEvent.quantity), 0)).where(
        UserStrikeEvent.source_moderation_case_id == case_id)) or 0
    if net > 0:
        return False, effective_strikes(db, user.id)
    db.add(UserStrikeEvent(user_id=user.id, source_moderation_case_id=case_id, event_type="strike_applied",
                           quantity=1, reason_code=reason_code, actor_id=actor.id))
    db.flush()
    total = effective_strikes(db, user.id)
    audit(db, actor, "strike.apply", "user", user.id, reason_code, case_id=str(case_id), effective=total)
    level = {1: "cảnh cáo lần 1", 2: "cảnh cáo lần 2", 3: "cảnh cáo nghiêm trọng"}.get(total, "khoá tài khoản")
    notify(db, user.id, "strike", f"Bạn nhận một strike ({level})",
           f"Tổng strike hiệu lực: {total}. Bạn có thể gửi khiếu nại nếu cho rằng quyết định chưa đúng.", "/profile")
    if total > BAN_THRESHOLD and user.status != "permanently_banned":
        ban(db, user, actor, "STRIKE_THRESHOLD", automatic=True)
    return True, total


def revoke_strike_for_case(db: Session, user: User, case_id, actor: User, reason_code: str) -> bool:
    net = db.scalar(select(func.coalesce(func.sum(UserStrikeEvent.quantity), 0)).where(
        UserStrikeEvent.source_moderation_case_id == case_id)) or 0
    if net <= 0:
        return False
    db.add(UserStrikeEvent(user_id=user.id, source_moderation_case_id=case_id, event_type="strike_revoked",
                           quantity=-1, reason_code=reason_code, actor_id=actor.id))
    db.flush()
    audit(db, actor, "strike.revoke", "user", user.id, reason_code, case_id=str(case_id),
          effective=effective_strikes(db, user.id))
    return True


def ban(db: Session, user: User, actor: User, reason_code: str, automatic: bool = False) -> None:
    user.status = "permanently_banned"
    revoke_all_sessions(db, user.id)
    if user.phone_hmac and not db.scalar(select(UserPhoneRestriction).where(
            UserPhoneRestriction.phone_hmac == user.phone_hmac, UserPhoneRestriction.status == "active")):
        db.add(UserPhoneRestriction(phone_hmac=user.phone_hmac, key_version=user.phone_hmac_key_version or "v1",
                                    restriction_type="registration_block", reason_code=reason_code,
                                    source_user_id=user.id, created_by=actor.id))
    audit(db, actor, "user.ban", "user", user.id, reason_code, automatic=automatic)
    notify(db, user.id, "account", "Tài khoản đã bị khoá",
           "Tài khoản bị khoá theo quy tắc cộng đồng. Bạn vẫn có thể gửi khiếu nại.", "/community/appeals")


def unban(db: Session, user: User, actor: User, reason_code: str, note: str) -> None:
    user.status = "active"
    for r in db.scalars(select(UserPhoneRestriction).where(UserPhoneRestriction.source_user_id == user.id,
                                                           UserPhoneRestriction.status == "active")):
        r.status, r.released_by, r.released_at, r.release_reason = "released", actor.id, utcnow(), note
    audit(db, actor, "user.unban", "user", user.id, reason_code)
    notify(db, user.id, "account", "Tài khoản đã được mở khoá", note)


# ---------- Xác minh số điện thoại ----------

def _mask_phone(e164: str) -> str:
    if len(e164) > 6:
        return f"{e164[:4]}***{e164[-3:]}"
    return e164


def request_phone_code(db: Session, user: User, phone_raw: str) -> dict:
    e164 = normalize_phone(phone_raw)
    if not e164:
        raise AppError(422, "INVALID_PHONE", "Số điện thoại không hợp lệ theo chuẩn quốc tế E.164.")
    digest, version = phone_hmac(e164)
    if db.scalar(select(UserPhoneRestriction).where(UserPhoneRestriction.phone_hmac == digest,
                                                    UserPhoneRestriction.status == "active")):
        raise AppError(403, "PHONE_BLOCKED", "Số điện thoại này đang bị hạn chế trên hệ thống.")
    # Sinh mã 6 chữ số ngẫu nhiên
    import secrets
    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = utcnow() + timedelta(minutes=10)
    masked = _mask_phone(e164)

    record = PhoneVerificationCode(
        user_id=user.id,
        phone_hmac=digest,
        phone_display_masked=masked,
        code=code,
        expires_at=expires_at,
    )
    db.add(record)
    user.phone_hmac = digest
    user.phone_hmac_key_version = version
    db.commit()
    return {
        "status": "code_sent",
        "phone_masked": masked,
        "expires_in_seconds": 600,
        "dev_code_hint": code,  # Hỗ trợ môi trường phát triển / demo
    }


def verify_phone_code(db: Session, user: User, code: str) -> dict:
    now = utcnow()
    record = db.scalar(
        select(PhoneVerificationCode)
        .where(
            PhoneVerificationCode.user_id == user.id,
            PhoneVerificationCode.verified_at.is_(None),
            PhoneVerificationCode.expires_at > now,
        )
        .order_by(PhoneVerificationCode.created_at.desc())
    )
    if not record:
        raise AppError(400, "EXPIRED_CODE", "Mã xác thực đã hết hạn hoặc không tồn tại. Vui lòng yêu cầu mã mới.")
    if record.attempts >= 5:
        raise AppError(429, "TOO_MANY_ATTEMPTS", "Bạn đã nhập sai quá số lần cho phép. Hãy yêu cầu mã mới.")

    record.attempts += 1
    if record.code != code.strip():
        db.commit()
        raise AppError(400, "INVALID_CODE", f"Mã xác thực không đúng. Còn {5 - record.attempts} lần thử.")

    record.verified_at = now
    user.phone_verified_at = now
    audit(db, user, "phone.verify", "user", user.id, masked_phone=record.phone_display_masked)
    db.commit()
    return {"verified": True, "phone_masked": record.phone_display_masked, "verified_at": now}

