"""Pipeline dịch (docs/04 §5, docs/02 §5.1):

1. Chọn/gợi ý hướng dịch.  2. Chuẩn hoá NFC, không đổi chữ.
3. Tra mục từ/cụm đã xác minh khớp nguyên câu.  4. Tra translation memory đã duyệt.
4b. Tra câu ví dụ trong từ điển khớp nguyên câu (nhãn dictionary_example, chưa chuyên gia xác minh).
5. Không có thì gửi sang adapter dịch máy.  6. Đối chiếu thuật ngữ: liệt kê mục từ khớp, cảnh báo từ chưa có.
7. Trả bản dịch kèm trạng thái, nguồn và ghi chú không chắc chắn.
Ứng viên chưa xác minh không bao giờ ghi đè dữ liệu đã xác minh.
"""
from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.errors import AppError
from ..core.text import nfc, search_key, words
from ..integrations.gemini import gemini
from ..integrations.mt import DIRECTIONS, mt
from ..models import LexicalEntry, LexicalSense, TranslationCorpus
from .lexicon import lookup_terms, similar_examples

MAX_LINES = 20
log = logging.getLogger("hriam.translation")
REVIEWED = ("community_reviewed", "expert_verified")


@dataclass
class TranslationResult:
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    translation_status: str  # verified_memory, expert_verified, dictionary_example, machine_draft, needs_review
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


def _example_match(examples: list[dict], source: str) -> tuple[str, str, dict] | None:
    """Câu khớp nguyên văn với một câu ví dụ trong từ điển -> dùng luôn, nhưng gắn nhãn riêng:
    câu do sách từ điển cung cấp, chưa qua chuyên gia xác minh."""
    for example in examples:
        if example["exact"]:
            text = example["vi"] if source == "ede" else example["ede"]
            return text, "dictionary_example", {"type": "dictionary_example",
                                                "verification_status": example["verification_status"]}
    return None


def _glossary(matches: list[dict], source: str, limit: int = 25) -> list[str]:
    """Bảng từ (Ê Đê = tiếng Việt) lấy từ các mục từ khớp trong câu, làm ngữ cảnh cho dịch máy ngoài."""
    out: list[str] = []
    for m in matches:
        if m["senses"]:
            text = m["senses"][0]["text"]
            line = f"{m['term']} = {text}" if source == "ede" else f"{text} = {m['term']}"
            if line not in out:
                out.append(line)
    return out[:limit]


def _machine_translate(result: TranslationResult, lines: list[str], source: str, target: str,
                       matches: list[dict], engine: str | None = None) -> bool:
    """Dịch máy theo MT_PROVIDER, thử lần lượt và rơi về bộ dịch còn lại khi lỗi (không phụ thuộc một bên):
    local  -> chỉ model cục bộ.
    auto   -> model cục bộ, rồi Gemini.
    gemini -> Gemini (chất lượng cao hơn, gửi văn bản ra ngoài), rồi model cục bộ.
    Trả False nếu không có bộ dịch nào dùng được; ném 502 nếu có nhưng tất cả đều lỗi."""
    provider = engine or settings.mt_provider
    order = ["gemini", "local"] if provider == "gemini" else ["local", "gemini"] if provider == "auto" else ["local"]
    usable = [name for name in order if (mt.available(source, target) if name == "local" else gemini.available())]
    if not usable:
        return False
    for name in usable:
        try:
            if name == "local":
                result.translated_text = "\n".join(mt.translate(lines, source, target))
                result.model_version = mt.info(DIRECTIONS[(source, target)]).model_version
                result.provenance = {"type": "machine_translation", "adapter": "nllb", "sends_data_externally": False}
            else:
                result.translated_text = "\n".join(gemini.translate(lines, source, target,
                                                                    _glossary(matches, source), result.similar_examples))
                result.model_version = f"gemini/{settings.gemini_model}"
                result.provenance = {"type": "machine_translation", "adapter": "gemini", "sends_data_externally": True}
                result.uncertainty_notes.append({"code": "EXTERNAL_MT", "message":
                                                 "Bản dịch do dịch vụ bên ngoài (Gemini) tạo ra; Gemini chưa được train riêng cho tiếng Ê Đê."})
            result.translation_status = "machine_draft"
            return True
        except Exception:  # lỗi một bộ dịch không làm sập API: thử bộ tiếp theo
            log.exception("Bộ dịch %s lỗi", name)
    raise AppError(502, "MT_UNAVAILABLE", "Dịch vụ dịch đang lỗi, vui lòng thử lại.")


def translate(db: Session, text: str, source: str, target: str, use_verified_memory: bool = True,
              engine: str | None = None) -> TranslationResult:
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
    if not hit and use_verified_memory:
        hit = _example_match(result.similar_examples, source)
    if hit:
        result.translated_text, result.translation_status, result.provenance = hit
    elif _machine_translate(result, [ln for ln in text.splitlines() if ln.strip()][:MAX_LINES], source, target,
                            matches, engine):
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
