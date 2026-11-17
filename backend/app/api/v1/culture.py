"""API Kho tư liệu văn hoá (docs/01 §4.10, docs/04 §2.5, docs/08 §7-8)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ...core import ratelimit
from ...core.db import get_db
from ...core.deps import client_key, current_user, optional_user, paginate, require
from ...core.errors import ok
from ...models import CulturalItem, User
from ...schemas.requests import CulturalItemIn, CulturalItemReviewIn
from ...services import culture

router = APIRouter(prefix="/culture", tags=["culture"])


@router.get("/items")
def list_items(
    category: str | None = Query(None),
    access_tier: str | None = Query(None),
    q: str = Query(""),
    cursor: str | None = None,
    limit: int = 20,
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
):
    stmt = culture.list_items(db, user, category, access_tier, q)
    rows, nxt = paginate(db, stmt, cursor, limit)
    return ok([culture.item_view(item, user) for item in rows], extra_meta={"next_cursor": nxt})


@router.get("/items/{item_id}")
def get_item(item_id: uuid.UUID, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    item = culture.get_item(db, item_id, user)
    return ok(culture.item_view(item, user))


@router.post("/items")
def create_item(
    body: CulturalItemIn,
    request: Request,
    user: User = Depends(require("culture.submit")),
    db: Session = Depends(get_db),
):
    ratelimit.check("culture_submit", client_key(request, user))
    item = culture.create_item(db, user, body.model_dump())
    return ok(culture.item_view(item, user), 201)


@router.post("/items/{item_id}/review")
def review_item(
    item_id: uuid.UUID,
    body: CulturalItemReviewIn,
    reviewer: User = Depends(require("culture.review")),
    db: Session = Depends(get_db),
):
    item = culture.review_item(db, item_id, reviewer, body.approve, body.decision_note)
    return ok(culture.item_view(item, reviewer))
