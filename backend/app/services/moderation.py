"""Kiểm duyệt trước khi đăng, hàng chờ người duyệt, báo cáo, khiếu nại (docs/05, docs/01 §5.4).

Hệ thống tự động chỉ đăng / giữ lại / từ chối spam rõ ràng; không bao giờ tự tính strike.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import utcnow
from ..core.deps import audit, notify
from ..core.errors import AppError
from ..integrations import moderation as detector
from ..models import ForumComment, ForumPost, ModerationAction, ModerationCase, User, UserAppeal
from . import accounts

REASONS = {
    "SPAM": "Spam, quảng cáo rác hoặc lừa đảo",
    "HARASSMENT": "Quấy rối, bắt nạt, đe doạ",
    "HATE": "Ngôn từ thù ghét, phân biệt đối xử",
    "VIOLENCE": "Bạo lực, tự hại, nội dung nguy hiểm",
    "SEXUAL": "Nội dung tình dục không phù hợp",
    "PERSONAL_DATA": "Tiết lộ dữ liệu cá nhân",
    "COPYRIGHT": "Vi phạm bản quyền",
    "MISLEADING": "Giả mạo, thao túng",
    "OFF_TOPIC": "Không phù hợp chủ đề (không tính strike)",
}


def content_of(db: Session, content_type: str, content_id) -> ForumPost | ForumComment | None:
    model = ForumPost if content_type == "post" else ForumComment
    return db.get(model, content_id)


def _label(content_type: str) -> str:
    return "Bài viết" if content_type == "post" else "Bình luận"


def _link(db: Session, content_type: str, content) -> str:
    post_id = content.id if content_type == "post" else content.post_id
    return f"/community/posts/{post_id}"


def screen(db: Session, content_type: str, content: ForumPost | ForumComment, trigger: str = "submission") -> ModerationCase:
    """Chạy kiểm tra tự động cho nội dung mới/sửa; nội dung ẩn cho đến khi có kết quả."""
    text = f"{content.title}\n{content.body_text}" if content_type == "post" else content.body_text
    verdict = detector.evaluate(text)
    content.language_hint = verdict.language
    case = ModerationCase(content_type=content_type, content_id=content.id, author_id=content.author_id,
                          trigger=trigger, policy_version=settings.moderation_policy_version,
                          detector_results=verdict.results, language_detected=verdict.language,
                          risk_level=verdict.risk_level, status="pending_automated")
    db.add(case)
    db.flush()
    db.add(ModerationAction(case_id=case.id, actor_type="system", action=f"auto_{verdict.decision}",
                            reason_code=verdict.reason_code))
    now = utcnow()
    if verdict.decision == "publish":
        content.status, content.published_at = "published", now
        case.status, case.final_decision, case.resolved_at = "resolved", "publish", now
    elif verdict.decision == "reject":
        content.status = "rejected"
        case.status, case.final_decision, case.decision_reason, case.resolved_at = "resolved", "reject", \
            verdict.reason_code, now
        notify(db, content.author_id, "moderation", f"{_label(content_type)} chưa được đăng",
               f"Lý do: {REASONS.get(verdict.reason_code, verdict.reason_code)}. Không tính strike. "
               "Bạn có thể sửa nội dung hoặc gửi khiếu nại.", "/community/my-submissions")
    else:
        content.status = "pending_human_review"
        case.status = "pending_human_review"
    return case


def report(db: Session, reporter: User, content_type: str, content, reason_code: str, note: str | None):
    """Báo cáo nội dung đã đăng: mở case cho người duyệt; nội dung vẫn hiển thị đến khi moderator gỡ."""
    from ..models import ContentReport
    if db.scalar(select(ContentReport).where(ContentReport.reporter_id == reporter.id,
                                             ContentReport.content_type == content_type,
                                             ContentReport.content_id == content.id)):
        raise AppError(409, "ALREADY_REPORTED", "Bạn đã báo cáo nội dung này.")
    case = db.scalar(select(ModerationCase).where(ModerationCase.content_type == content_type,
                                                  ModerationCase.content_id == content.id,
                                                  ModerationCase.trigger == "report",
                                                  ModerationCase.status != "resolved"))
    if not case:
        case = ModerationCase(content_type=content_type, content_id=content.id, author_id=content.author_id,
                              trigger="report", policy_version=settings.moderation_policy_version,
                              detector_results={"reports": 0}, language_detected=content.language_hint,
                              risk_level="unknown", status="pending_human_review")
        db.add(case)
        db.flush()
    case.detector_results = {**case.detector_results, "reports": case.detector_results.get("reports", 0) + 1}
    db.add(ContentReport(reporter_id=reporter.id, content_type=content_type, content_id=content.id,
                         reason_code=reason_code, note=note, case_id=case.id))
    db.add(ModerationAction(case_id=case.id, actor_type="user", actor_id=reporter.id, action="report",
                            reason_code=reason_code))
    return case


def decide(db: Session, case: ModerationCase, actor: User, action: str, reason_code: str | None = None,
           note: str | None = None, apply_strike: bool = False) -> ModerationCase:
    content = content_of(db, case.content_type, case.content_id)
    if not content:
        raise AppError(404, "NOT_FOUND", "Nội dung không còn tồn tại.")
    author = db.get(User, case.author_id)
    now = utcnow()
    if action in ("reject", "remove") and reason_code not in REASONS:
        raise AppError(422, "REASON_REQUIRED", "Hãy chọn mã lý do hợp lệ.")
    if action == "approve":
        content.status = "published"
        content.published_at = content.published_at or now
        case.final_decision = "publish"
        notify(db, author.id, "moderation", f"{_label(case.content_type)} đã được đăng", "",
               _link(db, case.content_type, content))
    elif action in ("reject", "remove"):
        content.status = "rejected" if action == "reject" else "removed"
        case.final_decision, case.decision_reason = action, reason_code
        notify(db, author.id, "moderation",
               f"{_label(case.content_type)} {'không được đăng' if action == 'reject' else 'đã bị gỡ'}",
               f"Lý do: {REASONS[reason_code]}. Bạn có thể gửi khiếu nại trong mục Khiếu nại.", "/community/appeals")
    elif action == "ask_context":
        db.add(ModerationAction(case_id=case.id, actor_type="user", actor_id=actor.id, action="ask_context",
                                note=note))
        notify(db, author.id, "moderation", "Người kiểm duyệt cần thêm ngữ cảnh",
               note or "Vui lòng bổ sung giải thích cho nội dung của bạn.", "/community/my-submissions")
        audit(db, actor, "moderation.ask_context", case.content_type, case.content_id)
        return case
    else:
        raise AppError(422, "UNKNOWN_ACTION", "Thao tác không hợp lệ.")
    case.status, case.decided_by, case.resolved_at = "resolved", actor.id, now
    db.add(ModerationAction(case_id=case.id, actor_type="user", actor_id=actor.id, action=action,
                            reason_code=reason_code, note=note))
    audit(db, actor, f"moderation.{action}", case.content_type, case.content_id, reason_code,
          case_id=str(case.id))
    if apply_strike and action in ("reject", "remove"):
        if reason_code == "OFF_TOPIC":
            raise AppError(422, "NO_STRIKE_FOR_REASON", "Lý do này không tính strike.")
        accounts.apply_strike(db, author, case.id, reason_code, actor)
    return case


def strike(db: Session, case: ModerationCase, actor: User) -> tuple[bool, int]:
    if case.final_decision not in ("reject", "remove") or case.decision_reason in (None, "OFF_TOPIC"):
        raise AppError(409, "NOT_A_CONFIRMED_VIOLATION",
                       "Chỉ áp dụng strike cho vi phạm đã được người kiểm duyệt xác nhận.")
    if case.decided_by is None:
        raise AppError(409, "AUTOMATED_DECISION",
                       "Quyết định tự động phải được người kiểm duyệt xem lại trước khi tính strike.")
    return accounts.apply_strike(db, db.get(User, case.author_id), case.id, case.decision_reason, actor)


def create_appeal(db: Session, user: User, case: ModerationCase, text: str) -> UserAppeal:
    if case.author_id != user.id:
        raise AppError(404, "NOT_FOUND", "Không tìm thấy quyết định.")
    if case.final_decision not in ("reject", "remove"):
        raise AppError(409, "NOT_APPEALABLE", "Chỉ khiếu nại được quyết định từ chối hoặc gỡ nội dung.")
    if db.scalar(select(UserAppeal).where(UserAppeal.user_id == user.id, UserAppeal.moderation_case_id == case.id)):
        raise AppError(409, "ALREADY_APPEALED", "Bạn đã khiếu nại quyết định này.")
    appeal = UserAppeal(user_id=user.id, moderation_case_id=case.id, appeal_text=text.strip())
    db.add(appeal)
    db.flush()
    return appeal


def decide_appeal(db: Session, appeal: UserAppeal, actor: User, accept: bool, note: str) -> UserAppeal:
    if appeal.status != "pending":
        raise AppError(409, "INVALID_STATE", "Khiếu nại đã được xử lý.")
    case = db.get(ModerationCase, appeal.moderation_case_id)
    user = db.get(User, appeal.user_id)
    appeal.status, appeal.reviewer_id, appeal.decision_note, appeal.decided_at = \
        "accepted" if accept else "rejected", actor.id, note, utcnow()
    if accept:
        accounts.revoke_strike_for_case(db, user, case.id, actor, "APPEAL_ACCEPTED")
        case.final_decision = "overturned"
        content = content_of(db, case.content_type, case.content_id)
        if content and content.status in ("rejected", "removed"):
            content.status, content.published_at = "published", content.published_at or utcnow()
        db.add(ModerationAction(case_id=case.id, actor_type="user", actor_id=actor.id, action="appeal_accepted"))
    audit(db, actor, "appeal.accept" if accept else "appeal.reject", "appeal", appeal.id,
          effective_strikes=accounts.effective_strikes(db, user.id))
    total = accounts.effective_strikes(db, user.id)
    extra = ""
    if accept and user.status == "permanently_banned" and total <= accounts.BAN_THRESHOLD:
        extra = " Tài khoản sẽ được quản trị viên xem xét mở khoá."
    notify(db, user.id, "appeal", "Khiếu nại được chấp nhận" if accept else "Khiếu nại không được chấp nhận",
           f"{note} Strike hiệu lực hiện tại: {total}.{extra}", "/community/appeals")
    return appeal
