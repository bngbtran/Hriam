"""Dịch và từ điển (docs/07 §3)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core import ratelimit
from ...core.db import get_db
from ...core.deps import client_key, current_user, optional_user, paginate, require
from ...core.errors import AppError, not_found, ok
from ...core.text import guess_language
from ...core.config import settings
from ...integrations.gemini import gemini
from ...integrations.mt import mt
from ...models import (LexicalEntry, OrthographyProfile, TranslationFeedback, TranslationRecord, User)
from ...schemas.requests import FeedbackIn, TranslateIn
from ...services import contributions, lexicon, translation

router = APIRouter(tags=["translation"])


@router.get("/translations/capabilities")
def capabilities():
    """Hướng dịch nào có mô hình; adapter công bố phiên bản, giấy phép, giới hạn, dữ liệu gửi ra ngoài."""
    return ok({d: {k: v for k, v in vars(mt.info(d)).items() if k != "path"} for d in ("ede2vi", "vi2ede")})


@router.get("/translations/engines")
def engines():
    """Bộ dịch máy nào dùng được, để giao diện bật/tắt công tắc Gemini ↔ mô hình Hriăm."""
    return ok({"default": settings.mt_provider,
               "local": {"available": {d: mt.info(d).available for d in ("ede2vi", "vi2ede")},
                         "sends_data_externally": False},
               "gemini": {"available": gemini.available(), "model": settings.gemini_model if gemini.available() else None,
                          "sends_data_externally": True}})


@router.post("/translations")
def translate(body: TranslateIn, request: Request, user: User | None = Depends(optional_user),
              db: Session = Depends(get_db)):
    ratelimit.check("translate", client_key(request, user))
    if (body.engine or settings.mt_provider) == "gemini" and gemini.available():
        ratelimit.check("translate_gemini", client_key(request, user))
    source = guess_language(body.text) if body.source_language == "auto" else body.source_language
    target = body.target_language or ("vi" if source == "ede" else "ede")
    result = translation.translate(db, body.text, source, target, body.use_verified_memory, body.engine)
    data = translation.as_dict(result) | {"detected_language": source if body.source_language == "auto" else None,
                                          "id": None}
    if user and user.save_translation_history:
        record = TranslationRecord(user_id=user.id, source_text=result.source_text,
                                   translated_text=result.translated_text, source_language=source,
                                   target_language=target, translation_status=result.translation_status,
                                   model_version=result.model_version)
        db.add(record)
        db.commit()
        data["id"] = str(record.id)
    return ok(data)


@router.get("/translations/history")
def history(cursor: str | None = None, limit: int = 20, user: User = Depends(current_user),
            db: Session = Depends(get_db)):
    stmt = select(TranslationRecord).where(TranslationRecord.user_id == user.id) \
        .order_by(TranslationRecord.created_at.desc())
    rows, nxt = paginate(db, stmt, cursor, limit)
    return ok([{"id": str(r.id), "source_text": r.source_text, "translated_text": r.translated_text,
                "source_language": r.source_language, "target_language": r.target_language,
                "translation_status": r.translation_status, "created_at": r.created_at} for r in rows],
              extra_meta={"next_cursor": nxt, "history_enabled": user.save_translation_history})


@router.delete("/translations/history")
def clear_history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    for r in db.scalars(select(TranslationRecord).where(TranslationRecord.user_id == user.id)):
        db.delete(r)
    db.commit()
    return ok({"cleared": True})


def _feedback(body: FeedbackIn, translation_id: uuid.UUID | None, request: Request, user: User, db: Session):
    ratelimit.check("feedback", client_key(request, user))
    fb = TranslationFeedback(user_id=user.id, translation_id=translation_id, source_text=body.source_text,
                             translated_text=body.translated_text, source_language=body.source_language,
                             target_language=body.target_language, error_type=body.error_type,
                             suggested_translation=body.suggested_translation, comment=body.comment,
                             model_version=body.model_version, consent_to_research=body.consent_research)
    db.add(fb)
    if body.suggested_translation:  # đề xuất bản dịch -> vào hàng chờ đóng góp, không ghi thẳng vào dữ liệu chính
        ede, vi = (body.source_text, body.suggested_translation) if body.source_language == "ede" \
            else (body.suggested_translation, body.source_text)
        sub = contributions.create(db, user, {
            "submission_type": "sentence_pair", "ede_form": ede, "proposed_vi_meaning": vi,
            "source_note": f"Góp ý bản dịch máy ({body.model_version or 'không rõ mô hình'}), lỗi: {body.error_type}",
            "consents": {"publish_as_lexicon": body.consent_publish_as_lexicon,
                         "use_for_research": body.consent_research}})
        fb.contribution_id = sub.id
    db.commit()
    return ok({"id": str(fb.id), "contribution_id": str(fb.contribution_id) if fb.contribution_id else None}, 201)


@router.post("/translations/feedback")
def feedback(body: FeedbackIn, request: Request, user: User = Depends(require("translation.feedback")),
             db: Session = Depends(get_db)):
    return _feedback(body, None, request, user, db)


@router.post("/translations/{translation_id}/feedback")
def feedback_for(translation_id: uuid.UUID, body: FeedbackIn, request: Request,
                 user: User = Depends(require("translation.feedback")), db: Session = Depends(get_db)):
    record = db.get(TranslationRecord, translation_id)
    if not record or record.user_id != user.id:
        raise not_found()
    return _feedback(body, translation_id, request, user, db)


@router.get("/lexicon/search")
def search(q: str = Query("", max_length=100), lang: str = Query("auto", pattern="^(auto|ede|vi)$"),
           cursor: str | None = None, limit: int = 20, db: Session = Depends(get_db)):
    rows, nxt = paginate(db, lexicon.search(db, q, lang), cursor, limit)
    return ok([lexicon.entry_summary(e) for e in rows], extra_meta={"next_cursor": nxt})


@router.get("/lexicon/entries/{entry_id}")
def entry(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    e = db.get(LexicalEntry, entry_id)
    if not e or e.status == "deprecated":
        raise not_found()
    return ok(lexicon.entry_detail(e))


@router.get("/lexicon/entries/{entry_id}/examples")
def examples(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    e = db.get(LexicalEntry, entry_id)
    if not e:
        raise not_found()
    return ok([{"sense_number": s["sense_number"], **ex} for s in lexicon.entry_detail(e)["senses"]
               for ex in s["examples"]])


@router.get("/lexicon/stats")
def stats(db: Session = Depends(get_db)):
    from sqlalchemy import func
    from ...models import LexicalSense, SenseExample
    return ok({"entries": db.scalar(select(func.count()).select_from(LexicalEntry)
                                    .where(LexicalEntry.status == "published")),
               "senses": db.scalar(select(func.count()).select_from(LexicalSense)),
               "verified_senses": db.scalar(select(func.count()).select_from(LexicalSense)
                                            .where(LexicalSense.status == "verified")),
               "examples": db.scalar(select(func.count()).select_from(SenseExample))})


@router.get("/orthography/profiles")
def profiles(db: Session = Depends(get_db)):
    rows = db.scalars(select(OrthographyProfile).where(OrthographyProfile.status != "retired")).all()
    if not rows:
        raise AppError(404, "NO_PROFILE", "Chưa có chuẩn chữ viết. Chạy: python -m app.cli seed")
    return ok([{"id": str(p.id), "code": p.code, "name": p.name, "version": p.version, "status": p.status,
                "description": p.description, "region_scope": p.region_scope, "characters": p.characters,
                "examples": p.examples} for p in rows])
