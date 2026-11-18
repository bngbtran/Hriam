"""Dịch vụ Kho tư liệu văn hoá Ê Đê (docs/01 §4.10, docs/04 §2.5, docs/08 §7-8).

Quản trị các tư liệu văn hoá theo 4 cấp quyền truy cập:
- public: Công khai cho mọi người
- community: Chỉ thành viên đã đăng nhập
- restricted: Tư liệu có điều kiện hạn chế (cần thẩm định / người được phép)
- private: Riêng tư / lưu trữ chưa công bố
"""
from __future__ import annotations

import uuid
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..core.db import utcnow
from ..core.deps import audit, permissions_of
from ..core.errors import AppError, not_found
from ..core.text import nfc
from ..models import CulturalItem, User

CATEGORY_NAMES = {
    "story": "Truyện kể dân gian",
    "song": "Lời hát / dân ca",
    "proverb_idiom": "Tục ngữ / thành ngữ",
    "history": "Tư liệu lịch sử",
    "custom": "Phong tục / nghi lễ",
    "term": "Thuật ngữ văn hoá",
    "other": "Khác",
}


def item_view(item: CulturalItem, current_user: User | None = None) -> dict:
    perms = permissions_of(current_user) if current_user else set()
    is_admin = bool(current_user and "admin" in current_user.role_names)
    is_author = bool(current_user and item.submitted_by == current_user.id)

    data = {
        "id": str(item.id),
        "title": item.title,
        "category": item.category,
        "category_label": CATEGORY_NAMES.get(item.category, item.category),
        "summary": item.summary,
        "storyteller_or_author": item.storyteller_or_author,
        "region": item.region,
        "access_tier": item.access_tier,
        "status": item.status,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "is_author": is_author,
    }

    # Nội dung đầy đủ được trả khi đủ quyền
    can_read = False
    if item.access_tier == "public":
        can_read = True
    elif item.access_tier == "community" and current_user:
        can_read = True
    elif item.access_tier == "restricted" and ("culture.restricted" in perms or is_admin or is_author):
        can_read = True
    elif item.access_tier == "private" and (is_author or is_admin):
        can_read = True

    if can_read:
        data["content_ede"] = item.content_ede
        data["content_vi"] = item.content_vi
        data["source_ref"] = item.source_ref
        data["consent_flags"] = item.consent_flags
    else:
        data["content_ede"] = "(Nội dung thuộc cấp quyền hạn chế, bạn chưa đủ quyền truy cập)"
        data["content_vi"] = "(Nội dung thuộc cấp quyền hạn chế, bạn chưa đủ quyền truy cập)"

    return data


def list_items(
    db: Session, current_user: User | None = None, category: str | None = None,
    access_tier: str | None = None, q: str = ""
):
    perms = permissions_of(current_user) if current_user else set()
    is_admin = bool(current_user and "admin" in current_user.role_names)

    stmt = select(CulturalItem)
    # Lọc trạng thái published (trừ khi là admin hoặc tác giả)
    if not is_admin:
        if current_user:
            stmt = stmt.where(or_(CulturalItem.status == "published", CulturalItem.submitted_by == current_user.id))
        else:
            stmt = stmt.where(CulturalItem.status == "published")

    # Lọc quyền truy cập theo cấp bậc
    allowed_tiers = ["public"]
    if current_user:
        allowed_tiers.append("community")
    if "culture.restricted" in perms or is_admin:
        allowed_tiers.append("restricted")
    if is_admin:
        allowed_tiers.append("private")

    if access_tier:
        if access_tier in allowed_tiers:
            stmt = stmt.where(CulturalItem.access_tier == access_tier)
        else:
            stmt = stmt.where(CulturalItem.access_tier == "public")  # fallback an toàn
    else:
        stmt = stmt.where(CulturalItem.access_tier.in_(allowed_tiers))

    if category:
        stmt = stmt.where(CulturalItem.category == category)

    if q:
        kw = f"%{q.strip()}%"
        stmt = stmt.where(or_(
            CulturalItem.title.ilike(kw),
            CulturalItem.summary.ilike(kw),
            CulturalItem.content_ede.ilike(kw),
            CulturalItem.content_vi.ilike(kw),
        ))

    return stmt.order_by(CulturalItem.created_at.desc())


def get_item(db: Session, item_id: uuid.UUID, current_user: User | None = None) -> CulturalItem:
    item = db.get(CulturalItem, item_id)
    if not item:
        raise not_found()
    return item


def create_item(db: Session, user: User, data: dict) -> CulturalItem:
    title = nfc(data["title"]).strip()
    content_ede = nfc(data["content_ede"]).strip()
    content_vi = nfc(data["content_vi"]).strip()
    summary = nfc(data.get("summary") or "").strip() or None

    is_expert = "culture.review" in permissions_of(user) or "admin" in user.role_names
    status = "published" if is_expert else "pending_review"

    item = CulturalItem(
        title=title,
        category=data.get("category", "story"),
        content_ede=content_ede,
        content_vi=content_vi,
        summary=summary,
        storyteller_or_author=data.get("storyteller_or_author"),
        region=data.get("region"),
        access_tier=data.get("access_tier", "public"),
        status=status,
        consent_flags=data.get("consent_flags", {}),
        submitted_by=user.id,
        reviewed_by=user.id if is_expert else None,
        reviewed_at=utcnow() if is_expert else None,
    )
    db.add(item)
    db.flush()
    audit(db, user, "culture.create_item", "cultural_item", item.id, category=item.category, status=item.status)
    db.commit()
    return item


def review_item(db: Session, item_id: uuid.UUID, reviewer: User, approve: bool, decision_note: str) -> CulturalItem:
    item = db.get(CulturalItem, item_id)
    if not item:
        raise not_found()
    item.status = "published" if approve else "rejected"
    item.reviewed_by = reviewer.id
    item.reviewed_at = utcnow()
    item.decision_note = decision_note

    audit(db, reviewer, f"culture.{'approve' if approve else 'reject'}", "cultural_item", item.id, note=decision_note)
    db.commit()
    return item
