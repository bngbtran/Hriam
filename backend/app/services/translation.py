"""Pipeline dịch (docs/04 §5, docs/02 §5.1):

1. Chọn/gợi ý hướng dịch.  2. Chuẩn hoá NFC, không đổi chữ.
3. Tra mục từ/cụm đã xác minh khớp nguyên câu.  4. Tra translation memory đã duyệt.
5. Không có thì gửi sang adapter dịch máy.  6. Đối chiếu thuật ngữ: liệt kê mục từ khớp, cảnh báo từ chưa có.
7. Trả bản dịch kèm trạng thái, nguồn và ghi chú không chắc chắn.
Ứng viên chưa xác minh không bao giờ ghi đè dữ liệu đã xác minh.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.errors import AppError
from ..core.text import nfc, search_key, words
from ..integrations.mt import DIRECTIONS, mt
from ..models import LexicalEntry, LexicalSense, TranslationCorpus
from .lexicon import lookup_terms, similar_examples

MAX_LINES = 20
REVIEWED = ("community_reviewed", "expert_verified")


@dataclass
class TranslationResult:
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    translation_status: str  # verified_memory, expert_verified, machine_draft, needs_review
    verified_matches: list = field(default_factory=list)
    lexicon_matches: list = field(default_factory=list)
    similar_examples: list = field(default_factory=list)
    uncertainty_notes: list = field(default_factory=list)
    model_version: str | None = None
    provenance: dict = field(default_factory=dict)
    seconds: float = 0.0


def _whole_text_match(db: Session, text: str, source: str) -> tuple[str, str, dict] | None:
    """Mục từ khớp nguyên văn và có nghĩa đã xác minh -> dùng luôn."""
    key = search_key(text)
    if source == "ede":
        entry = db.scalar(select(LexicalEntry).where(LexicalEntry.normalized_form == key,
                                                     LexicalEntry.status == "published"))
        senses = [s for s in (entry.senses if entry else []) if s.status == "verified"]
        if senses:
            return "; ".join(s.definition_vi for s in senses), "expert_verified", {
                "type": "lexicon", "entry_id": str(entry.id), "source": entry.source.name if entry.source else None}
    else:
        sense = db.scalar(select(LexicalSense).where(LexicalSense.definition_vi_key == key,
                                                     LexicalSense.status == "verified"))
        if sense and sense.entry.status == "published":
            return sense.entry.canonical_form, "expert_verified", {"type": "lexicon", "entry_id": str(sense.entry_id)}
    row = db.scalar(select(TranslationCorpus).where(
        TranslationCorpus.source_key == key, TranslationCorpus.source_lang == source,
        TranslationCorpus.quality_status.in_(REVIEWED)).order_by(TranslationCorpus.verified_at.desc()))
    if row:
        return row.target_text, "verified_memory", {"type": "translation_memory", "corpus_id": str(row.id),
                                                    "quality_status": row.quality_status}
    return None


def translate(db: Session, text: str, source: str, target: str, use_verified_memory: bool = True) -> TranslationResult:
    if (source, target) not in (("ede", "vi"), ("vi", "ede")):
        raise AppError(422, "UNSUPPORTED_DIRECTION", "Chỉ hỗ trợ dịch Ê Đê ↔ tiếng Kinh.")
    text = nfc(text).strip()
    if not text:
        raise AppError(422, "EMPTY_TEXT", "Hãy nhập nội dung cần dịch.")
    if len(text) > settings.max_translate_chars:
        raise AppError(413, "TEXT_TOO_LONG", f"Tối đa {settings.max_translate_chars} ký tự mỗi lần dịch.")
    started = time.perf_counter()
    result = TranslationResult(text, "", source, target, "needs_review")

    matches = lookup_terms(db, text, source)
    result.lexicon_matches = matches
    result.similar_examples = similar_examples(db, text, source)
    result.verified_matches = [m for m in matches if m["verified"]]
    # Từ điển nguồn là Ê Đê → Việt: chỉ cảnh báo từ lạ khi câu nguồn là tiếng Ê Đê.
    unknown = [m["term"] for m in matches if not m["senses"]] if source == "ede" else []
    unverified = [m["term"] for m in matches if m["senses"] and not m["verified"]]
    if unknown:
        result.uncertainty_notes.append({"code": "UNKNOWN_TERMS", "terms": unknown[:12],
                                         "message": "Có từ chưa có trong từ điển: " + ", ".join(unknown[:12])})
    if unverified:
        result.uncertainty_notes.append({"code": "UNVERIFIED_TERMS", "terms": unverified[:12],
                                         "message": "Nghĩa lấy từ từ điển nguồn, chưa được chuyên gia xác minh."})

    hit = _whole_text_match(db, text, source) if use_verified_memory else None
    if hit:
        result.translated_text, result.translation_status, result.provenance = hit
    elif mt.available(source, target):
        lines = [ln for ln in text.splitlines() if ln.strip()][:MAX_LINES]
        try:
            result.translated_text = "\n".join(mt.translate(lines, source, target))
        except Exception as exc:  # lỗi mô hình không làm sập API
            raise AppError(502, "MT_UNAVAILABLE", "Mô hình dịch đang lỗi, vui lòng thử lại.") from exc
        info = mt.info(DIRECTIONS[(source, target)])
        result.translation_status = "machine_draft"
        result.model_version = info.model_version
        result.provenance = {"type": "machine_translation", "adapter": "nllb", "sends_data_externally": False}
        if len(words(text)) <= 3:
            result.uncertainty_notes.append({"code": "SHORT_INPUT",
                                             "message": "Câu rất ngắn: đối chiếu thêm với từ điển bên dưới."})
    else:
        # Không có mô hình: ghép nghĩa theo từ điển, đánh dấu cần xem lại.
        result.translated_text = " ".join(m["senses"][0]["text"] if m["senses"] else f"[{m['term']}]"
                                          for m in matches)
        result.translation_status = "needs_review"
        result.provenance = {"type": "dictionary_gloss"}
        result.uncertainty_notes.append({"code": "NO_MT_MODEL",
                                         "message": "Chưa có mô hình dịch cho chiều này; đây là bản ghép nghĩa từng từ."})
    result.seconds = round(time.perf_counter() - started, 3)
    return result


def as_dict(result: TranslationResult) -> dict:
    return asdict(result)
