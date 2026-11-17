"""Contribution Center (docs/07 §5) và khiếu nại của người dùng (docs/07 §7)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core import ratelimit
from ...core.db import get_db
from ...core.deps import client_key, current_user, paginate, require
from ...core.errors import not_found, ok
from ...models import ContributionSubmission, ModerationCase, User, UserAppeal
from ...schemas.requests import AppealIn, ContributionIn
from ...services import contributions, moderation

router = APIRouter(tags=["contributions"])


@router.post("/contributions")
def submit(body: ContributionIn, request: Request, user: User = Depends(require("contribution.submit")),
           db: Session = Depends(get_db)):
    ratelimit.check("contribution", client_key(request, user))
    sub = contributions.create(db, user, body.model_dump())
    dupes = contributions.duplicates(db, sub)
    db.commit()
    return ok(contributions.view(sub, dupes), 201)


@router.get("/contributions/mine")
def mine(cursor: str | None = None, limit: int = 20, user: User = Depends(current_user),
         db: Session = Depends(get_db)):
    stmt = select(ContributionSubmission).where(ContributionSubmission.submitter_id == user.id) \
        .order_by(ContributionSubmission.created_at.desc())
    rows, nxt = paginate(db, stmt, cursor, limit)
    return ok([contributions.view(s) for s in rows], extra_meta={"next_cursor": nxt})


def _own(db: Session, sub_id: uuid.UUID, user: User) -> ContributionSubmission:
    sub = db.get(ContributionSubmission, sub_id)
    if not sub or sub.submitter_id != user.id:
        raise not_found()
    return sub


@router.get("/contributions/{sub_id}")
def get_one(sub_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(contributions.view(_own(db, sub_id, user)))


@router.delete("/contributions/{sub_id}")
def withdraw(sub_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    sub = contributions.withdraw(db, _own(db, sub_id, user), user)
    db.commit()
    return ok(contributions.view(sub))


def appeal_view(db: Session, a: UserAppeal) -> dict:
    case = db.get(ModerationCase, a.moderation_case_id)
    return {"id": str(a.id), "moderation_case_id": str(a.moderation_case_id), "appeal_text": a.appeal_text,
            "status": a.status, "decision_note": a.decision_note, "created_at": a.created_at,
            "decided_at": a.decided_at, "content_type": case.content_type if case else None,
            "content_id": str(case.content_id) if case else None,
            "original_decision": case.final_decision if case else None,
            "reason_code": case.decision_reason if case else None,
            "reason": moderation.REASONS.get(case.decision_reason or "", "") if case else None}


@router.get("/appeals/mine")
def my_appeals(user: User = Depends(current_user), db: Session = Depends(get_db)):
    appeals = db.scalars(select(UserAppeal).where(UserAppeal.user_id == user.id)
                         .order_by(UserAppeal.created_at.desc())).all()
    appealed = {a.moderation_case_id for a in appeals}
    open_cases = db.scalars(select(ModerationCase).where(
        ModerationCase.author_id == user.id, ModerationCase.final_decision.in_(("reject", "remove")))
        .order_by(ModerationCase.created_at.desc())).all()
    return ok({"appeals": [appeal_view(db, a) for a in appeals],
               "appealable": [{"case_id": str(c.id), "content_type": c.content_type, "content_id": str(c.content_id),
                               "decision": c.final_decision, "reason_code": c.decision_reason,
                               "reason": moderation.REASONS.get(c.decision_reason or "", c.decision_reason),
                               "decided_at": c.resolved_at} for c in open_cases if c.id not in appealed]})


@router.post("/appeals")
def create_appeal(body: AppealIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # Tài khoản bị khoá vẫn được khiếu nại (docs/01 §6).
    case = db.get(ModerationCase, body.moderation_case_id)
    if not case:
        raise not_found()
    appeal = moderation.create_appeal(db, user, case, body.appeal_text)
    db.commit()
    return ok(appeal_view(db, appeal), 201)
