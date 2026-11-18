"""Xác thực và hồ sơ (docs/07 §2). Refresh token nằm trong cookie HttpOnly, SameSite=Strict, chỉ gửi tới /api/v1/auth."""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core import ratelimit
from ...core.config import settings
from ...core.db import get_db, utcnow
from ...core.deps import client_key, current_user, permissions_of
from ...core.errors import AppError, ok
from ...models import ModerationCase, Notification, User, UserStrikeEvent
from ...schemas.requests import LoginIn, ProfilePatch, RefreshIn, RegisterIn, RequestPhoneCodeIn, VerifyPhoneCodeIn
from ...services import accounts

router = APIRouter(tags=["auth"])
COOKIE = "hriam_refresh"


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(COOKIE, token, httponly=True, secure=settings.cookie_secure, samesite="strict",
                        path="/api/v1/auth", max_age=settings.refresh_token_days * 86400)


def me_view(user: User, db: Session) -> dict:
    return {"id": str(user.id), "username": user.username, "display_name": user.display_name,
            "email": user.email_normalized, "has_phone": bool(user.phone_hmac),
            "phone_verified": bool(user.phone_verified_at),
            "status": user.status,
            "roles": user.role_names, "permissions": sorted(permissions_of(user)),
            "save_translation_history": user.save_translation_history,
            "effective_strikes": accounts.effective_strikes(db, user.id), "created_at": user.created_at}


def _session_response(db: Session, user: User, status: int = 200):
    tokens = accounts.issue_tokens(db, user)
    db.commit()
    refresh = tokens.pop("refresh_token")
    response = ok({**tokens, "user": me_view(user, db)}, status)
    _set_cookie(response, refresh)
    return response


@router.post("/auth/register")
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.check("auth", client_key(request))
    if not body.accept_terms:
        raise AppError(422, "TERMS_REQUIRED", "Cần đồng ý quy tắc cộng đồng và chính sách quyền riêng tư.")
    user = accounts.register(db, body.username, body.display_name, body.password, body.email, body.phone)
    return _session_response(db, user, 201)


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.check("auth", client_key(request))
    user = accounts.authenticate(db, body.username, body.password)
    return _session_response(db, user)


@router.post("/auth/refresh")
def refresh(body: RefreshIn | None = None, cookie: str | None = Cookie(default=None, alias=COOKIE),
            db: Session = Depends(get_db)):
    token = cookie or (body.refresh_token if body else None)
    if not token:
        raise AppError(401, "INVALID_REFRESH", "Chưa đăng nhập.")
    user, tokens = accounts.rotate_refresh(db, token)
    db.commit()
    new_refresh = tokens.pop("refresh_token")
    response = ok({**tokens, "user": me_view(user, db)})
    _set_cookie(response, new_refresh)
    return response


@router.post("/auth/logout")
def logout(cookie: str | None = Cookie(default=None, alias=COOKIE), db: Session = Depends(get_db)):
    if cookie:
        accounts.revoke_session(db, cookie)
        db.commit()
    response = ok({"logged_out": True})
    response.delete_cookie(COOKIE, path="/api/v1/auth")
    return response


@router.post("/auth/request-phone-code")
def request_phone_code(body: RequestPhoneCodeIn, request: Request, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    ratelimit.check("auth_phone", client_key(request, user))
    res = accounts.request_phone_code(db, user, body.phone)
    return ok(res)


@router.post("/auth/verify-phone")
def verify_phone(body: VerifyPhoneCodeIn, request: Request, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    ratelimit.check("auth_phone_verify", client_key(request, user))
    res = accounts.verify_phone_code(db, user, body.code)
    return ok(res)



@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(me_view(user, db))


@router.patch("/me")
def update_me(body: ProfilePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.display_name is not None:
        user.display_name = body.display_name.strip()
    if body.save_translation_history is not None:
        user.save_translation_history = body.save_translation_history
    db.commit()
    return ok(me_view(user, db))


@router.get("/me/strikes")
def my_strikes(user: User = Depends(current_user), db: Session = Depends(get_db)):
    events = db.scalars(select(UserStrikeEvent).where(UserStrikeEvent.user_id == user.id)
                        .order_by(UserStrikeEvent.created_at.desc())).all()
    cases = {c.id: c for c in db.scalars(select(ModerationCase).where(ModerationCase.id.in_(
        [e.source_moderation_case_id for e in events if e.source_moderation_case_id])))}
    return ok({"effective_strikes": accounts.effective_strikes(db, user.id), "ban_threshold": accounts.BAN_THRESHOLD,
               "status": user.status,
               "events": [{"id": str(e.id), "event_type": e.event_type, "quantity": e.quantity,
                           "reason_code": e.reason_code, "created_at": e.created_at,
                           "moderation_case_id": str(e.source_moderation_case_id) if e.source_moderation_case_id
                           else None,
                           "content_type": cases[e.source_moderation_case_id].content_type
                           if e.source_moderation_case_id in cases else None} for e in events]})


@router.get("/me/notifications")
def my_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id)
                      .order_by(Notification.created_at.desc()).limit(50)).all()
    return ok([{"id": str(n.id), "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
                "read": n.read_at is not None, "created_at": n.created_at} for n in rows],
              extra_meta={"unread": sum(1 for n in rows if not n.read_at)})


@router.post("/me/notifications/read")
def read_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    for n in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))):
        n.read_at = utcnow()
    db.commit()
    return ok({"read": True})
