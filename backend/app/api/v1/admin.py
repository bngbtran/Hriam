"""Khu quản trị (docs/07 §6–8): đóng góp, kiểm duyệt, khiếu nại, người dùng, dataset, audit, cấu hình.

Mọi endpoint kiểm tra quyền ở backend. Thao tác duyệt/khoá cần Idempotency-Key và mã lý do.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.deps import (audit, idempotency_key, idempotent_replay, paginate, permissions_of,
                          remember_idempotent, require)
from ...core.errors import AppError, not_found, ok
from ...core.permissions import ROLES
from ...models import (AdminAuditLog, ContributionSubmission, DatasetRelease, ForumComment, ForumPost,
                       LexicalCandidate, License, ModerationCase, OrthographyProfile, Role, Source, User,
                       UserAppeal, UserPhoneRestriction, UserRole)
from ...schemas.requests import (AppealDecisionIn, CandidateApproveIn, CandidateRejectIn, CandidateRequestEvidenceIn,
                                DecisionIn, ReasonIn, ReleaseIn, ReviewIn, RolesIn)
from ...services import accounts, contributions, datasets, discovery, moderation
from .contributions import appeal_view

router = APIRouter(prefix="/admin", tags=["admin"])


def _replay_or(db: Session, actor: User, scope: str, key: str, fn) -> dict:
    """Chạy thao tác một lần duy nhất cho mỗi Idempotency-Key; gọi lại trả đúng kết quả cũ."""
    cached = idempotent_replay(db, actor, scope, key)
    if cached is not None:
        return cached
    result = jsonable_encoder(fn())
    remember_idempotent(db, actor, scope, key, result)
    db.commit()
    return result


def _user_brief(u: User | None) -> dict | None:
    return {"id": str(u.id), "username": u.username, "display_name": u.display_name} if u else None


# ---------- Đóng góp ----------

@router.get("/contributions")
def list_contributions(status: str = Query("pending"), cursor: str | None = None, limit: int = 30,
                       _: User = Depends(require("lexicon.review")), db: Session = Depends(get_db)):
    stmt = select(ContributionSubmission)
    if status != "all":
        stmt = stmt.where(ContributionSubmission.status == status)
    rows, nxt = paginate(db, stmt.order_by(ContributionSubmission.created_at), cursor, limit)
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({s.submitter_id for s in rows})))}
    return ok([{**contributions.view(s), "submitter": _user_brief(users.get(s.submitter_id))} for s in rows],
              extra_meta={"next_cursor": nxt})


@router.get("/contributions/{sub_id}")
def contribution_detail(sub_id: uuid.UUID, _: User = Depends(require("lexicon.review")),
                        db: Session = Depends(get_db)):
    sub = db.get(ContributionSubmission, sub_id)
    if not sub:
        raise not_found()
    return ok({**contributions.view(sub, contributions.duplicates(db, sub)),
               "submitter": _user_brief(db.get(User, sub.submitter_id) if sub.submitter_id else None)})


@router.post("/contributions/{sub_id}/approve")
def approve_contribution(sub_id: uuid.UUID, body: ReviewIn, key: str = Depends(idempotency_key),
                         actor: User = Depends(require("lexicon.approve")), db: Session = Depends(get_db)):
    def run():
        sub = db.get(ContributionSubmission, sub_id)
        if not sub:
            raise not_found()
        return contributions.view(contributions.approve(db, sub, actor, body.reason_code, body.review_note,
                                                        body.model_dump(exclude_none=True)))
    return ok(_replay_or(db, actor, f"contribution.approve:{sub_id}", key, run))


@router.post("/contributions/{sub_id}/reject")
def reject_contribution(sub_id: uuid.UUID, body: ReviewIn, key: str = Depends(idempotency_key),
                        actor: User = Depends(require("lexicon.reject")), db: Session = Depends(get_db)):
    def run():
        sub = db.get(ContributionSubmission, sub_id)
        if not sub:
            raise not_found()
        return contributions.view(contributions.reject(db, sub, actor, body.reason_code))
    return ok(_replay_or(db, actor, f"contribution.reject:{sub_id}", key, run))


# ---------- Ứng viên AI (Lexical Discovery - docs/01 §4.7, docs/04 §6) ----------

@router.get("/lexical-candidates")
def list_lexical_candidates(status: str = Query("all"), cursor: str | None = None, limit: int = 30,
                            _: User = Depends(require("lexicon.candidate_review")), db: Session = Depends(get_db)):
    stmt = discovery.list_candidates(db, status)
    rows, nxt = paginate(db, stmt, cursor, limit)
    counts = {s: db.scalar(select(func.count()).select_from(LexicalCandidate).where(LexicalCandidate.candidate_status == s))
              for s in ("new", "collecting_evidence", "needs_expert", "approved", "rejected")}
    return ok([discovery.candidate_view(c) for c in rows], extra_meta={"next_cursor": nxt, "counts": counts})


@router.post("/lexical-candidates/run-discovery")
def trigger_discovery(_: User = Depends(require("lexicon.candidate_review")), db: Session = Depends(get_db)):
    """Kích hoạt pipeline phân tích các bài viết đã public có consent để tìm từ/cụm từ mới."""
    report = discovery.run_discovery_pipeline(db, limit=50)
    return ok(report)


@router.get("/lexical-candidates/{candidate_id}")
def candidate_detail(candidate_id: uuid.UUID, _: User = Depends(require("lexicon.candidate_review")),
                     db: Session = Depends(get_db)):
    cand = db.get(LexicalCandidate, candidate_id)
    if not cand:
        raise not_found()
    return ok(discovery.candidate_view(cand, full=True))


@router.post("/lexical-candidates/{candidate_id}/approve")
def approve_candidate(candidate_id: uuid.UUID, body: CandidateApproveIn, key: str = Depends(idempotency_key),
                      actor: User = Depends(require("lexicon.approve")), db: Session = Depends(get_db)):
    def run():
        return discovery.approve_candidate(
            db, candidate_id, actor, body.reason_code, body.definition_vi,
            body.part_of_speech, body.entry_type, body.sense_id, body.review_note
        )
    return ok(_replay_or(db, actor, f"candidate.approve:{candidate_id}", key, run))


@router.post("/lexical-candidates/{candidate_id}/reject")
def reject_candidate(candidate_id: uuid.UUID, body: CandidateRejectIn, key: str = Depends(idempotency_key),
                     actor: User = Depends(require("lexicon.reject")), db: Session = Depends(get_db)):
    def run():
        return discovery.reject_candidate(db, candidate_id, actor, body.reason_code, body.review_note)
    return ok(_replay_or(db, actor, f"candidate.reject:{candidate_id}", key, run))


@router.post("/lexical-candidates/{candidate_id}/request-evidence")
def request_candidate_evidence(candidate_id: uuid.UUID, body: CandidateRequestEvidenceIn,
                               actor: User = Depends(require("lexicon.candidate_review")),
                               db: Session = Depends(get_db)):
    return ok(discovery.request_evidence(db, candidate_id, actor, body.note))



# ---------- Kiểm duyệt ----------

def _case_view(db: Session, c: ModerationCase, full: bool = False) -> dict:
    content = moderation.content_of(db, c.content_type, c.content_id)
    data = {"id": str(c.id), "content_type": c.content_type, "content_id": str(c.content_id), "trigger": c.trigger,
            "status": c.status, "risk_level": c.risk_level, "language_detected": c.language_detected,
            "final_decision": c.final_decision, "decision_reason": c.decision_reason,
            "policy_version": c.policy_version, "created_at": c.created_at, "resolved_at": c.resolved_at,
            "content_status": content.status if content else None,
            "excerpt": ((content.title + " — ") if c.content_type == "post" and content else "") +
                       (content.body_text[:160] if content else "")}
    if full:
        author = db.get(User, c.author_id)
        post_id = (content.id if c.content_type == "post" else content.post_id) if content else None
        data |= {"detector_results": c.detector_results,
                 "content": {"title": getattr(content, "title", None), "body_text": content.body_text if content else None,
                             "post_id": str(post_id) if post_id else None},
                 "author": {**_user_brief(author), "status": author.status,
                            "effective_strikes": accounts.effective_strikes(db, author.id)},
                 "actions": [{"action": a.action, "actor_type": a.actor_type, "reason_code": a.reason_code,
                              "note": a.note, "created_at": a.created_at} for a in c.actions],
                 "appeal": next((appeal_view(db, a) for a in db.scalars(select(UserAppeal).where(
                     UserAppeal.moderation_case_id == c.id))), None),
                 "reasons": moderation.REASONS}
    return data


QUEUES = {
    "human_review": lambda s: s.where(ModerationCase.status == "pending_human_review",
                                      ModerationCase.trigger != "report"),
    "reports": lambda s: s.where(ModerationCase.status == "pending_human_review", ModerationCase.trigger == "report"),
    "automated": lambda s: s.where(ModerationCase.status == "pending_automated"),
    "rejected": lambda s: s.where(ModerationCase.final_decision.in_(("reject", "remove"))),
    "resolved": lambda s: s.where(ModerationCase.status == "resolved"),
}


@router.get("/moderation/cases")
def cases(queue: str = Query("human_review"), cursor: str | None = None, limit: int = 30,
          _: User = Depends(require("moderation.review")), db: Session = Depends(get_db)):
    if queue not in QUEUES:
        raise AppError(422, "UNKNOWN_QUEUE", "Hàng chờ không hợp lệ.")
    stmt = QUEUES[queue](select(ModerationCase)).order_by(ModerationCase.created_at.desc())
    rows, nxt = paginate(db, stmt, cursor, limit)
    counts = {q: db.scalar(select(func.count()).select_from(QUEUES[q](select(ModerationCase)).subquery()))
              for q in ("human_review", "reports")}
    return ok([_case_view(db, c) for c in rows], extra_meta={"next_cursor": nxt, "counts": counts})


def _case(db: Session, case_id: uuid.UUID) -> ModerationCase:
    c = db.get(ModerationCase, case_id)
    if not c:
        raise not_found()
    return c


@router.get("/moderation/cases/{case_id}")
def case_detail(case_id: uuid.UUID, _: User = Depends(require("moderation.review")), db: Session = Depends(get_db)):
    return ok(_case_view(db, _case(db, case_id), full=True))


def _decide(action: str):
    def endpoint(case_id: uuid.UUID, body: DecisionIn, key: str = Depends(idempotency_key),
                 actor: User = Depends(require("moderation.decide")), db: Session = Depends(get_db)):
        if body.apply_strike and "user.strike" not in permissions_of(actor):
            raise AppError(403, "FORBIDDEN", "Bạn không có quyền áp dụng strike.")
        def run():
            return _case_view(db, moderation.decide(db, _case(db, case_id), actor, action, body.reason_code,
                                                    body.note, body.apply_strike), full=True)
        return ok(_replay_or(db, actor, f"moderation.{action}:{case_id}", key, run))
    return endpoint


for _action in ("approve", "reject", "remove", "ask_context"):
    router.add_api_route(f"/moderation/cases/{{case_id}}/{_action.replace('_', '-')}", _decide(_action),
                         methods=["POST"], name=f"moderation_{_action}")


@router.post("/moderation/cases/{case_id}/apply-strike")
def apply_strike(case_id: uuid.UUID, key: str = Depends(idempotency_key), actor: User = Depends(require("user.strike")),
                 db: Session = Depends(get_db)):
    def run():
        applied, total = moderation.strike(db, _case(db, case_id), actor)
        return {"applied": applied, "effective_strikes": total}
    return ok(_replay_or(db, actor, f"moderation.strike:{case_id}", key, run))


# ---------- Khiếu nại ----------

@router.get("/appeals")
def appeals(status: str = Query("pending"), _: User = Depends(require("appeal.review")), db: Session = Depends(get_db)):
    stmt = select(UserAppeal)
    if status != "all":
        stmt = stmt.where(UserAppeal.status == status)
    rows = db.scalars(stmt.order_by(UserAppeal.created_at).limit(100)).all()
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({a.user_id for a in rows})))}
    return ok([{**appeal_view(db, a), "user": _user_brief(users.get(a.user_id))} for a in rows])


def _appeal_decision(accept: bool):
    def endpoint(appeal_id: uuid.UUID, body: AppealDecisionIn, key: str = Depends(idempotency_key),
                 actor: User = Depends(require("appeal.decide")), db: Session = Depends(get_db)):
        def run():
            appeal = db.get(UserAppeal, appeal_id)
            if not appeal:
                raise not_found()
            case = db.get(ModerationCase, appeal.moderation_case_id)
            if case and case.decided_by == actor.id and db.scalar(select(func.count()).select_from(UserRole).join(
                    Role).where(Role.name.in_(("moderator", "admin")))) > 1:
                raise AppError(409, "SAME_REVIEWER", "Khiếu nại nên do người khác với người ra quyết định ban đầu xem xét.")
            return appeal_view(db, moderation.decide_appeal(db, appeal, actor, accept, body.decision_note))
        return ok(_replay_or(db, actor, f"appeal.{'accept' if accept else 'reject'}:{appeal_id}", key, run))
    return endpoint


router.add_api_route("/appeals/{appeal_id}/accept", _appeal_decision(True), methods=["POST"], name="appeal_accept")
router.add_api_route("/appeals/{appeal_id}/reject", _appeal_decision(False), methods=["POST"], name="appeal_reject")


# ---------- Người dùng ----------

@router.get("/users")
def users(q: str = "", status: str | None = None, cursor: str | None = None, limit: int = 30,
          _: User = Depends(require("user.read")), db: Session = Depends(get_db)):
    stmt = select(User)
    if q:
        stmt = stmt.where(or_(User.username.ilike(f"%{q}%"), User.display_name.ilike(f"%{q}%")))
    if status:
        stmt = stmt.where(User.status == status)
    rows, nxt = paginate(db, stmt.order_by(User.created_at.desc()), cursor, limit)
    return ok([{**_user_brief(u), "status": u.status, "roles": u.role_names, "created_at": u.created_at,
                "effective_strikes": accounts.effective_strikes(db, u.id)} for u in rows],
              extra_meta={"next_cursor": nxt})


def _user(db: Session, user_id: uuid.UUID) -> User:
    u = db.get(User, user_id)
    if not u:
        raise not_found()
    return u


@router.get("/users/{user_id}")
def user_detail(user_id: uuid.UUID, _: User = Depends(require("user.read")), db: Session = Depends(get_db)):
    u = _user(db, user_id)
    posts = db.scalar(select(func.count()).select_from(ForumPost).where(ForumPost.author_id == u.id))
    comments = db.scalar(select(func.count()).select_from(ForumComment).where(ForumComment.author_id == u.id))
    return ok({**_user_brief(u), "status": u.status, "roles": u.role_names, "created_at": u.created_at,
               "has_phone": bool(u.phone_hmac), "effective_strikes": accounts.effective_strikes(db, u.id),
               "posts": posts, "comments": comments, "available_roles": list(ROLES)})


@router.post("/users/{user_id}/ban")
def ban(user_id: uuid.UUID, body: ReasonIn, key: str = Depends(idempotency_key),
        actor: User = Depends(require("user.ban")), db: Session = Depends(get_db)):
    def run():
        u = _user(db, user_id)
        if u.id == actor.id:
            raise AppError(409, "SELF_ACTION", "Không thể tự khoá tài khoản của mình.")
        if u.status != "permanently_banned":
            accounts.ban(db, u, actor, body.reason_code)
        return {"status": u.status}
    return ok(_replay_or(db, actor, f"user.ban:{user_id}", key, run))


@router.post("/users/{user_id}/unban")
def unban(user_id: uuid.UUID, body: ReasonIn, key: str = Depends(idempotency_key),
          actor: User = Depends(require("user.unban")), db: Session = Depends(get_db)):
    def run():
        u = _user(db, user_id)
        if u.status == "active":
            raise AppError(409, "NOT_BANNED", "Tài khoản đang hoạt động.")
        accounts.unban(db, u, actor, body.reason_code, body.note)
        return {"status": u.status}
    return ok(_replay_or(db, actor, f"user.unban:{user_id}", key, run))


@router.put("/users/{user_id}/roles")
def set_roles(user_id: uuid.UUID, body: RolesIn, actor: User = Depends(require("user.roles")),
              db: Session = Depends(get_db)):
    u = _user(db, user_id)
    wanted = set(body.roles) | {"user"}
    if u.id == actor.id and "admin" not in wanted:
        raise AppError(409, "SELF_ACTION", "Không thể tự bỏ quyền quản trị của mình.")
    before = set(u.role_names)
    for ur in list(u.roles):
        if ur.role.name not in wanted:
            u.roles.remove(ur)
    for name in wanted - before:
        accounts.assign_role(db, u, name, actor)
    audit(db, actor, "user.roles", "user", u.id, "ROLE_CHANGE", added=sorted(wanted - before),
          removed=sorted(before - wanted), note=body.note)
    db.commit()
    db.refresh(u)
    return ok({"roles": u.role_names})


@router.get("/users/{user_id}/audit")
def user_audit(user_id: uuid.UUID, _: User = Depends(require("audit.read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(AdminAuditLog).where(AdminAuditLog.target_id == str(user_id))
                      .order_by(AdminAuditLog.created_at.desc()).limit(100)).all()
    return ok([_audit_view(a, {}) for a in rows])


@router.get("/phone-restrictions")
def phone_restrictions(_: User = Depends(require("phone_restriction.manage")), db: Session = Depends(get_db)):
    rows = db.scalars(select(UserPhoneRestriction).order_by(UserPhoneRestriction.created_at.desc()).limit(100)).all()
    # Không trả HMAC ra giao diện (docs/07 §8).
    return ok([{"id": str(r.id), "restriction_type": r.restriction_type, "reason_code": r.reason_code,
                "status": r.status, "source_user_id": str(r.source_user_id) if r.source_user_id else None,
                "key_version": r.key_version, "created_at": r.created_at, "released_at": r.released_at}
               for r in rows])


@router.post("/phone-restrictions/{restriction_id}/release")
def release_phone(restriction_id: uuid.UUID, body: ReasonIn, key: str = Depends(idempotency_key),
                  actor: User = Depends(require("phone_restriction.manage")), db: Session = Depends(get_db)):
    def run():
        from ...core.db import utcnow
        r = db.get(UserPhoneRestriction, restriction_id)
        if not r:
            raise not_found()
        if r.status == "active":
            r.status, r.released_by, r.released_at, r.release_reason = "released", actor.id, utcnow(), body.note
            audit(db, actor, "phone_restriction.release", "phone_restriction", r.id, body.reason_code)
        return {"status": r.status}
    return ok(_replay_or(db, actor, f"phone.release:{restriction_id}", key, run))


# ---------- Dataset ----------

@router.get("/dataset-releases")
def releases(_: User = Depends(require("dataset.read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(DatasetRelease).order_by(DatasetRelease.released_at.desc())).all()
    creators = {u.id: u.display_name for u in db.scalars(select(User).where(User.id.in_({r.created_by for r in rows})))}
    return ok([{"id": str(r.id), "version": r.version, "status": r.status, "checksum_sha256": r.checksum_sha256,
                "record_counts": r.record_counts, "license_inventory": r.license_inventory,
                "change_summary": r.change_summary, "manifest_uri": r.manifest_uri, "released_at": r.released_at,
                "created_by": creators.get(r.created_by)} for r in rows])


@router.post("/dataset-releases")
def create_release(body: ReleaseIn, key: str = Depends(idempotency_key),
                   actor: User = Depends(require("dataset.release")), db: Session = Depends(get_db)):
    def run():
        r = datasets.create_release(db, actor, body.version, body.change_summary)
        return {"id": str(r.id), "version": r.version, "status": r.status, "checksum_sha256": r.checksum_sha256,
                "record_counts": r.record_counts}
    return ok(_replay_or(db, actor, f"dataset.release:{body.version}", key, run), 201)


@router.get("/sources")
def sources(_: User = Depends(require("dataset.read")), db: Session = Depends(get_db)):
    return ok([{"code": s.code, "name": s.name, "source_type": s.source_type, "reference": s.url_or_reference,
                "notes": s.notes, "license": {"name": s.license.spdx_id_or_custom_name,
                                              "review_status": s.license.review_status,
                                              "commercial_allowed": s.license.commercial_allowed,
                                              "notes": s.license.notes} if s.license else None}
               for s in db.scalars(select(Source).order_by(Source.code))])


# ---------- Audit, cấu hình ----------

def _audit_view(a: AdminAuditLog, actors: dict) -> dict:
    return {"id": str(a.id), "actor": actors.get(a.actor_id), "action": a.action, "target_type": a.target_type,
            "target_id": a.target_id, "reason_code": a.reason_code, "metadata": a.metadata_safe_json,
            "created_at": a.created_at}


@router.get("/audit")
def audit_log(action: str | None = None, cursor: str | None = None, limit: int = 50,
              _: User = Depends(require("audit.read")), db: Session = Depends(get_db)):
    stmt = select(AdminAuditLog)
    if action:
        stmt = stmt.where(AdminAuditLog.action.like(f"{action}%"))
    rows, nxt = paginate(db, stmt.order_by(AdminAuditLog.created_at.desc()), cursor, limit)
    actors = {u.id: u.username for u in db.scalars(select(User).where(User.id.in_({a.actor_id for a in rows})))}
    return ok([_audit_view(a, actors) for a in rows], extra_meta={"next_cursor": nxt})


@router.get("/settings")
def settings_view(_: User = Depends(require("settings.manage")), db: Session = Depends(get_db)):
    from ...core.config import settings
    from ...integrations import moderation as detector
    from ...integrations.mt import mt
    return ok({"moderation_policy_version": settings.moderation_policy_version,
               "moderation_terms": detector._terms(),
               "orthography_profiles": [{"code": p.code, "name": p.name, "version": p.version, "status": p.status,
                                         "characters": len(p.characters)} for p in db.scalars(select(OrthographyProfile))],
               "licenses": [{"name": lic.spdx_id_or_custom_name, "review_status": lic.review_status}
                            for lic in db.scalars(select(License))],
               "translation_adapters": {d: {k: v for k, v in vars(mt.info(d)).items() if k != "metrics"}
                                        for d in ("ede2vi", "vi2ede")},
               "roles": {name: perms for name, (_, perms) in ROLES.items()}})
