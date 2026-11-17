"""Diễn đàn (docs/07 §4). Bài/bình luận chỉ hiện công khai sau kiểm duyệt; tạo bài trả 202."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core import ratelimit
from ...core.db import get_db, utcnow
from ...core.deps import client_key, current_user, optional_user, paginate, permissions_of, require
from ...core.errors import AppError, not_found, ok
from ...core.text import nfc
from ...models import ForumComment, ForumPost, ModerationCase, User
from ...schemas.requests import CommentIn, PostIn, PostPatch, ReportIn
from ...services import moderation

router = APIRouter(tags=["forum"])
CATEGORIES = {"hoi-dap": "Hỏi đáp ngôn ngữ", "tu-vung": "Từ vựng", "phat-am": "Phát âm", "phuong-ngu": "Phương ngữ",
              "van-hoa": "Văn hoá", "hoc-tieng": "Học tiếng", "gop-y-ban-dich": "Góp ý bản dịch"}


def _authors(db: Session, ids) -> dict:
    return {u.id: u.display_name for u in db.scalars(select(User).where(User.id.in_(set(ids))))}


def _post_view(p: ForumPost, authors: dict, comments: int | None = None, own: bool = False) -> dict:
    data = {"id": str(p.id), "category": p.category, "category_label": CATEGORIES[p.category], "title": p.title,
            "body_text": p.body_text, "author": authors.get(p.author_id, "Thành viên"), "language_hint": p.language_hint,
            "status": p.status, "published_at": p.published_at, "created_at": p.created_at,
            "comment_count": comments}
    if own:
        data["consent_research_analysis"] = p.consent_research_analysis
    return data


def _can_moderate(user: User | None) -> bool:
    return bool(user and "moderation.review" in permissions_of(user))


@router.get("/forum/categories")
def categories():
    return ok([{"code": k, "label": v} for k, v in CATEGORIES.items()])


@router.get("/forum/posts")
def feed(category: str | None = Query(None), cursor: str | None = None, limit: int = 20,
         db: Session = Depends(get_db)):
    stmt = select(ForumPost).where(ForumPost.status == "published")
    if category:
        stmt = stmt.where(ForumPost.category == category)
    rows, nxt = paginate(db, stmt.order_by(ForumPost.published_at.desc()), cursor, limit)
    counts = dict(db.execute(select(ForumComment.post_id, func.count()).where(
        ForumComment.post_id.in_([p.id for p in rows]), ForumComment.status == "published")
        .group_by(ForumComment.post_id)).all())
    authors = _authors(db, [p.author_id for p in rows])
    return ok([_post_view(p, authors, counts.get(p.id, 0)) for p in rows], extra_meta={"next_cursor": nxt})


@router.post("/forum/posts")
def create_post(body: PostIn, request: Request, user: User = Depends(require("forum.post")),
                db: Session = Depends(get_db)):
    ratelimit.check("forum", client_key(request, user))
    post = ForumPost(author_id=user.id, category=body.category, title=nfc(body.title).strip(),
                     body_text=nfc(body.body_text).strip(), consent_research_analysis=body.consent_research_analysis)
    db.add(post)
    db.flush()
    moderation.screen(db, "post", post)
    db.commit()
    return ok(_post_view(post, {user.id: user.display_name}, own=True), 202)


@router.get("/forum/my-submissions")
def my_submissions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    posts = db.scalars(select(ForumPost).where(ForumPost.author_id == user.id, ForumPost.deleted_at.is_(None))
                       .order_by(ForumPost.created_at.desc()).limit(100)).all()
    comments = db.scalars(select(ForumComment).where(ForumComment.author_id == user.id,
                                                     ForumComment.deleted_at.is_(None))
                          .order_by(ForumComment.created_at.desc()).limit(100)).all()
    ids = [p.id for p in posts] + [c.id for c in comments]
    cases = {}
    for c in db.scalars(select(ModerationCase).where(ModerationCase.content_id.in_(ids))
                        .order_by(ModerationCase.created_at)):
        cases[c.content_id] = c  # case mới nhất
    def case_info(cid):
        c = cases.get(cid)
        return {"case_id": str(c.id), "decision": c.final_decision, "reason_code": c.decision_reason,
                "reason": moderation.REASONS.get(c.decision_reason or "", c.decision_reason)} if c else None
    return ok({"posts": [{**_post_view(p, {user.id: user.display_name}, own=True), "moderation": case_info(p.id)}
                         for p in posts],
               "comments": [{"id": str(c.id), "post_id": str(c.post_id), "body_text": c.body_text, "status": c.status,
                             "created_at": c.created_at, "moderation": case_info(c.id)} for c in comments]})


def _visible_post(db: Session, post_id: uuid.UUID, user: User | None) -> ForumPost:
    post = db.get(ForumPost, post_id)
    if not post or post.deleted_at:
        raise not_found()
    if post.status != "published" and not (user and (user.id == post.author_id or _can_moderate(user))):
        raise not_found()
    return post


@router.get("/forum/posts/{post_id}")
def get_post(post_id: uuid.UUID, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    post = _visible_post(db, post_id, user)
    comments = [c for c in post.comments if c.deleted_at is None and (
        c.status == "published" or (user and (c.author_id == user.id or _can_moderate(user))))]
    authors = _authors(db, [post.author_id] + [c.author_id for c in comments])
    own = bool(user and user.id == post.author_id)
    return ok({**_post_view(post, authors, len([c for c in comments if c.status == "published"]), own),
               "is_author": own,
               "comments": [{"id": str(c.id), "parent_id": str(c.parent_id) if c.parent_id else None,
                             "body_text": c.body_text, "author": authors.get(c.author_id, "Thành viên"),
                             "status": c.status, "created_at": c.created_at,
                             "is_author": bool(user and c.author_id == user.id)} for c in comments]})


@router.patch("/forum/posts/{post_id}")
def edit_post(post_id: uuid.UUID, body: PostPatch, user: User = Depends(require("forum.post")),
              db: Session = Depends(get_db)):
    post = db.get(ForumPost, post_id)
    if not post or post.author_id != user.id or post.deleted_at:
        raise not_found()
    if post.status == "removed":
        raise AppError(409, "REMOVED", "Bài đã bị gỡ; hãy gửi khiếu nại nếu cần.")
    if body.title is not None:
        post.title = nfc(body.title).strip()
    if body.body_text is not None:
        post.body_text = nfc(body.body_text).strip()
    if body.consent_research_analysis is not None:
        post.consent_research_analysis = body.consent_research_analysis
    if body.title is not None or body.body_text is not None:
        post.status = "pending_moderation"  # sửa nội dung -> kiểm duyệt lại
        moderation.screen(db, "post", post, trigger="edit")
    db.commit()
    return ok(_post_view(post, {user.id: user.display_name}, own=True), 202)


@router.delete("/forum/posts/{post_id}")
def delete_post(post_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    post = db.get(ForumPost, post_id)
    if not post or post.author_id != user.id or post.deleted_at:
        raise not_found()
    post.deleted_at, post.status = utcnow(), "removed"
    db.commit()
    return ok({"deleted": True})


@router.post("/forum/posts/{post_id}/comments")
def comment(post_id: uuid.UUID, body: CommentIn, request: Request, user: User = Depends(require("forum.post")),
            db: Session = Depends(get_db)):
    ratelimit.check("forum", client_key(request, user))
    post = db.get(ForumPost, post_id)
    if not post or post.status != "published":
        raise not_found()
    c = ForumComment(post_id=post.id, author_id=user.id, parent_id=body.parent_id, body_text=nfc(body.body_text).strip())
    db.add(c)
    db.flush()
    moderation.screen(db, "comment", c)
    db.commit()
    return ok({"id": str(c.id), "status": c.status, "body_text": c.body_text, "created_at": c.created_at}, 202)


@router.post("/forum/posts/{post_id}/report")
def report(post_id: uuid.UUID, body: ReportIn, request: Request, user: User = Depends(require("forum.post")),
           db: Session = Depends(get_db)):
    ratelimit.check("report", client_key(request, user))
    if body.comment_id:
        target, kind = db.get(ForumComment, body.comment_id), "comment"
        if not target or target.post_id != post_id:
            raise not_found()
    else:
        target, kind = db.get(ForumPost, post_id), "post"
    if not target or target.status != "published":
        raise not_found()
    moderation.report(db, user, kind, target, body.reason_code, body.note)
    db.commit()
    return ok({"reported": True}, 202)
