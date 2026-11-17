"""Contribution Center và duyệt vào Master Lexicon (docs/01 §4.5–4.6, §5.2; docs/03 §6).

- Gửi: lưu ở contribution_submissions (pending), KHÔNG ghi vào Master Dataset.
- Approve: trong một transaction, tạo/cập nhật entry/sense/example hoặc translation_corpus, ghi audit, làm mới chỉ mục.
  Nghĩa chỉ ở trạng thái "verified" khi người duyệt có quyền lexicon.verify (Language Expert).
- Reject/rút: xoá nội dung (purge), chỉ giữ metadata kiểm toán tối thiểu.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.db import utcnow
from ..core.deps import audit, notify, permissions_of
from ..core.errors import AppError
from ..core.text import nfc, search_key
from ..models import (ContributionSubmission, CorpusExample, LexicalEntry, LexicalSense, SenseExample, Source,
                      TranslationCorpus, User)
from .lexicon import term_index

COMMUNITY_SOURCE = "community"
CONTENT_FIELDS = ("raw_text", "proposed_translation", "context_text", "source_note", "attachment_id", "phrase_type")


def duplicates(db: Session, sub: ContributionSubmission) -> dict:
    if not sub.raw_text:
        return {"entries": [], "pending": 0}
    key = search_key(sub.raw_text)
    entries = db.scalars(select(LexicalEntry).where(LexicalEntry.normalized_form == key).limit(5)).all()
    pending = db.scalar(select(func.count()).select_from(ContributionSubmission).where(
        ContributionSubmission.id != sub.id, ContributionSubmission.status.in_(("pending", "in_review")),
        func.lower(ContributionSubmission.raw_text) == sub.raw_text.lower()))
    return {"entries": [{"id": str(e.id), "canonical_form": e.canonical_form,
                         "senses": [s.definition_vi for s in e.senses]} for e in entries], "pending": pending or 0}


def create(db: Session, user: User, data: dict) -> ContributionSubmission:
    kind = data["submission_type"]
    if kind == "audio":
        raise AppError(422, "AUDIO_NOT_SUPPORTED", "Đóng góp âm thanh chưa được mở (cần kho lưu trữ và quy trình đồng ý riêng).")
    raw, meaning = nfc(data["ede_form"]).strip(), nfc(data.get("proposed_vi_meaning") or "").strip()
    if not raw:
        raise AppError(422, "EMPTY_CONTRIBUTION", "Hãy nhập từ, cụm hoặc câu tiếng Ê Đê.")
    if kind != "correction" and not meaning:
        raise AppError(422, "MEANING_REQUIRED", "Hãy nhập nghĩa hoặc bản dịch tiếng Kinh.")
    consents = data.get("consents") or {}
    sub = ContributionSubmission(
        submitter_id=user.id, submission_type=kind, raw_text=raw, proposed_translation=meaning or None,
        context_text=nfc(data.get("context_text") or "").strip() or None, phrase_type=data.get("phrase_type"),
        target_entry_id=data.get("target_entry_id"), source_note=(data.get("source_note") or "").strip() or None,
        consent_to_publication=bool(consents.get("publish_as_lexicon")),
        consent_to_research=bool(consents.get("use_for_research")),
        consent_to_model_training=bool(consents.get("use_for_model_training")))
    db.add(sub)
    db.flush()
    return sub


def _community_source(db: Session) -> Source | None:
    return db.scalar(select(Source).where(Source.code == COMMUNITY_SOURCE))


def approve(db: Session, sub: ContributionSubmission, reviewer: User, reason_code: str, note: str | None,
            sense_overrides: dict | None = None) -> ContributionSubmission:
    if sub.status not in ("pending", "in_review"):
        raise AppError(409, "INVALID_STATE", f"Đóng góp đang ở trạng thái {sub.status}, không duyệt được.")
    if not sub.consent_to_publication:
        raise AppError(409, "NO_PUBLICATION_CONSENT", "Người đóng góp chưa đồng ý công bố vào từ điển.")
    is_expert = "lexicon.verify" in permissions_of(reviewer)
    now = utcnow()
    source = _community_source(db)
    overrides = sense_overrides or {}
    text, meaning = sub.raw_text, overrides.get("definition_vi") or sub.proposed_translation

    if sub.submission_type == "sentence_pair":
        db.add(TranslationCorpus(source_text=text, source_key=search_key(text), target_text=meaning, source_lang="ede",
                                 target_lang="vi", domain=overrides.get("domain"), source_id=source.id if source else None,
                                 license_id=source.license_id if source else None,
                                 quality_status="expert_verified" if is_expert else "community_reviewed",
                                 consent_scope=_consent_scope(sub), verified_at=now))
        db.add(TranslationCorpus(source_text=meaning, source_key=search_key(meaning), target_text=text,
                                 source_lang="vi", target_lang="ede", domain=overrides.get("domain"),
                                 source_id=source.id if source else None,
                                 license_id=source.license_id if source else None,
                                 quality_status="expert_verified" if is_expert else "community_reviewed",
                                 consent_scope=_consent_scope(sub), verified_at=now))
    else:
        entry = db.get(LexicalEntry, sub.target_entry_id) if sub.target_entry_id else None
        entry = entry or db.scalar(select(LexicalEntry).where(LexicalEntry.normalized_form == search_key(text),
                                                              LexicalEntry.status == "published"))
        if sub.submission_type == "correction" and not entry:
            raise AppError(409, "NO_TARGET_ENTRY", "Không tìm thấy mục từ cần sửa.")
        if not entry:
            entry_type = {"phrase": sub.phrase_type or "multiword_expression"}.get(sub.submission_type, "word")
            if entry_type not in ("word", "multiword_expression", "idiom", "proverb", "phrase", "other"):
                entry_type = "multiword_expression"
            entry = LexicalEntry(canonical_form=text, normalized_form=search_key(text), entry_type=entry_type,
                                 source_id=source.id if source else None, source_ref=f"contribution:{sub.id}")
            db.add(entry)
            db.flush()
        number = (max((s.sense_number for s in entry.senses), default=0)) + 1
        sense = LexicalSense(entry_id=entry.id, sense_number=number, definition_vi=meaning,
                             definition_vi_key=search_key(meaning), part_of_speech=overrides.get("part_of_speech"),
                             status="verified" if is_expert else "draft",
                             verification_level="language_expert" if is_expert else "admin_approved",
                             verified_by=reviewer.id if is_expert else None, verified_at=now if is_expert else None,
                             source_id=source.id if source else None)
        db.add(sense)
        db.flush()
        if sub.context_text and "|" in sub.context_text:  # "câu Ê Đê | bản dịch"
            ede, vi = (p.strip() for p in sub.context_text.split("|", 1))
            example = CorpusExample(text_ede=ede, text_vi=vi, source_id=source.id if source else None,
                                    verification_status="expert_verified" if is_expert else "community_reviewed")
            db.add(example)
            db.flush()
            db.add(SenseExample(sense_id=sense.id, example_id=example.id))
        entry.updated_at = now
        sub.result_entry_id = entry.id
    sub.status, sub.reviewed_by, sub.reviewed_at = "approved", reviewer.id, now
    sub.decision_code, sub.decision_note = reason_code, note
    audit(db, reviewer, "contribution.approve", "contribution", sub.id, reason_code,
          submission_type=sub.submission_type, verified=is_expert)
    if sub.submitter_id:
        notify(db, sub.submitter_id, "contribution", "Đóng góp của bạn đã được duyệt",
               "Cảm ơn bạn. Nội dung sẽ có trong từ điển và bản phát hành dữ liệu kế tiếp.", "/contribute")
    term_index.invalidate()
    return sub


def _consent_scope(sub: ContributionSubmission) -> str:
    scopes = ["public_display"] + (["research_analysis"] if sub.consent_to_research else []) + \
             (["model_training"] if sub.consent_to_model_training else [])
    return ",".join(scopes)


def purge(sub: ContributionSubmission) -> None:
    for field in CONTENT_FIELDS:
        setattr(sub, field, None)
    sub.decision_note = None
    sub.purged_at = utcnow()


def reject(db: Session, sub: ContributionSubmission, reviewer: User, reason_code: str) -> ContributionSubmission:
    if sub.status not in ("pending", "in_review"):
        raise AppError(409, "INVALID_STATE", f"Đóng góp đang ở trạng thái {sub.status}, không từ chối được.")
    sub.status, sub.reviewed_by, sub.reviewed_at, sub.decision_code = "rejected", reviewer.id, utcnow(), reason_code
    purge(sub)  # docs/03 §6: không giữ nội dung bị từ chối, kể cả trong audit
    audit(db, reviewer, "contribution.reject", "contribution", sub.id, reason_code,
          submission_type=sub.submission_type)
    if sub.submitter_id:
        notify(db, sub.submitter_id, "contribution", "Đóng góp chưa được duyệt",
               f"Mã lý do: {reason_code}. Nội dung đóng góp đã được xoá khỏi hệ thống.", "/contribute")
    return sub


def withdraw(db: Session, sub: ContributionSubmission, user: User) -> ContributionSubmission:
    if sub.status != "pending":
        raise AppError(409, "INVALID_STATE", "Chỉ rút được đóng góp đang chờ duyệt.")
    sub.status = "withdrawn"
    purge(sub)
    audit(db, user, "contribution.withdraw", "contribution", sub.id)
    return sub


def view(sub: ContributionSubmission, include_dupes: dict | None = None) -> dict:
    data = {
        "id": str(sub.id), "submission_type": sub.submission_type, "status": sub.status,
        "ede_form": sub.raw_text, "proposed_vi_meaning": sub.proposed_translation, "context_text": sub.context_text,
        "phrase_type": sub.phrase_type, "source_note": sub.source_note,
        "target_entry_id": str(sub.target_entry_id) if sub.target_entry_id else None,
        "result_entry_id": str(sub.result_entry_id) if sub.result_entry_id else None,
        "decision_code": sub.decision_code, "decision_note": sub.decision_note, "purged": sub.purged_at is not None,
        "consents": {"publish_as_lexicon": sub.consent_to_publication, "use_for_research": sub.consent_to_research,
                     "use_for_model_training": sub.consent_to_model_training},
        "created_at": sub.created_at, "reviewed_at": sub.reviewed_at,
    }
    if include_dupes is not None:
        data["duplicates"] = include_dupes
    return data
