"""Tra cứu Master Lexicon: tìm kiếm có phân trang, chi tiết mục từ, khớp thuật ngữ trong câu."""
from __future__ import annotations

import re
import threading
from collections import defaultdict

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..core.text import search_key, words
from ..models import CorpusExample, LexicalEntry, LexicalForm, LexicalSense

MAX_NGRAM = 4
PAREN = re.compile(r"\([^)]*\)")


class _TermIndex:
    """Chỉ mục trong bộ nhớ để khớp cụm từ dài nhất trong câu. Làm mới khi Master Lexicon thay đổi."""

    def __init__(self) -> None:
        self.version = 0
        self._built = -1
        self._lock = threading.Lock()
        self.ede: dict[str, list[dict]] = {}
        self.vi: dict[str, list[dict]] = {}
        self.examples: list[tuple[str, str, str, str, str]] = []  # (ede_key, vi_key, ede, vi, status)

    def invalidate(self) -> None:
        self.version += 1

    def ensure(self, db: Session) -> None:
        if self._built == self.version:
            return
        with self._lock:
            if self._built == self.version:
                return
            ede, vi, by_entry = defaultdict(list), defaultdict(list), defaultdict(list)
            rows = db.execute(select(LexicalSense, LexicalEntry).join(LexicalEntry).where(
                LexicalEntry.status == "published", LexicalSense.status != "deprecated")
                .order_by(LexicalEntry.canonical_form, LexicalSense.sense_number))
            for sense, entry in rows:
                item = {"entry_id": str(entry.id), "sense_id": str(sense.id), "status": sense.status,
                        "source": entry.source.code if entry.source else None}
                ede_item = {**item, "text": sense.definition_vi, "form": entry.canonical_form}
                ede[entry.normalized_form].append(ede_item)
                by_entry[entry.id].append(ede_item)
                for part in re.split(r"[,;]", PAREN.sub("", sense.definition_vi)):
                    key = search_key(part.strip(" .:"))
                    if key and len(key.split()) <= MAX_NGRAM:
                        vi[key].append({**item, "text": entry.canonical_form, "form": sense.definition_vi})
            for form in db.scalars(select(LexicalForm)):
                ede[form.normalized_form].extend({**it, "variant": form.form_text} for it in by_entry[form.entry_id])
            examples = [(search_key(e.text_ede), search_key(e.text_vi), e.text_ede, e.text_vi, e.verification_status)
                        for e in db.scalars(select(CorpusExample))]
            self.ede, self.vi, self.examples, self._built = dict(ede), dict(vi), examples, self.version


term_index = _TermIndex()


def lookup_terms(db: Session, text: str, source: str) -> list[dict]:
    """Khớp tham lam cụm dài nhất (tối đa 4 từ) theo từ điển của ngôn ngữ nguồn."""
    term_index.ensure(db)
    index = term_index.ede if source == "ede" else term_index.vi
    tokens = words(text)
    out, i = [], 0
    while i < len(tokens):
        for n in range(min(MAX_NGRAM, len(tokens) - i), 0, -1):
            surface = " ".join(tokens[i:i + n])
            hits = index.get(search_key(surface))
            if hits or n == 1:
                senses = (hits or [])[:6]
                out.append({"term": surface, "senses": senses,
                            "verified": any(s["status"] == "verified" for s in senses)})
                i += n
                break
    return out


def entry_summary(entry: LexicalEntry) -> dict:
    return {
        "id": str(entry.id), "canonical_form": entry.canonical_form, "entry_type": entry.entry_type,
        "part_of_speech": entry.part_of_speech, "status": entry.status,
        "senses": [{"id": str(s.id), "sense_number": s.sense_number, "definition_vi": s.definition_vi,
                    "status": s.status} for s in entry.senses if s.status != "deprecated"],
        "variants": [f.form_text for f in entry.forms],
    }


def entry_detail(entry: LexicalEntry) -> dict:
    src = entry.source
    return {
        **entry_summary(entry),
        "language_code": entry.language_code, "loan_source": entry.loan_source, "notes": entry.notes,
        "forms": [{"form_text": f.form_text, "form_type": f.form_type, "is_preferred": f.is_preferred,
                   "notes": f.notes} for f in entry.forms],
        "senses": [{
            "id": str(s.id), "sense_number": s.sense_number, "definition_vi": s.definition_vi,
            "definition_ede": s.definition_ede, "part_of_speech": s.part_of_speech, "semantic_domain": s.semantic_domain,
            "usage_register": s.usage_register, "literal_or_figurative": s.literal_or_figurative, "status": s.status,
            "verification_level": s.verification_level, "verified_at": s.verified_at,
            "examples": [{"ede": se.example.text_ede, "vi": se.example.text_vi, "role": se.role,
                          "verification_status": se.example.verification_status} for se in
                         sorted(s.examples, key=lambda x: x.position)],
        } for s in entry.senses if s.status != "deprecated"],
        "provenance": {
            "source": {"code": src.code, "name": src.name, "reference": src.url_or_reference} if src else None,
            "source_ref": entry.source_ref,
            "license": {"name": src.license.spdx_id_or_custom_name, "review_status": src.license.review_status}
            if src and src.license else None,
            "updated_at": entry.updated_at,
        },
    }


def search(db: Session, q: str, lang: str = "auto"):
    """Trả câu lệnh select (để phân trang). lang: ede (tìm theo từ Ê Đê), vi (theo nghĩa), auto (cả hai)."""
    key = search_key(q)
    like = f"%{key}%"
    stmt = select(LexicalEntry).where(LexicalEntry.status == "published")
    if not key:
        return stmt.order_by(LexicalEntry.normalized_form)
    by_ede = or_(LexicalEntry.normalized_form.like(like),
                 LexicalEntry.id.in_(select(LexicalForm.entry_id).where(LexicalForm.normalized_form.like(like))))
    by_vi = LexicalEntry.id.in_(select(LexicalSense.entry_id).where(LexicalSense.definition_vi_key.like(like)))
    cond = by_ede if lang == "ede" else by_vi if lang == "vi" else or_(by_ede, by_vi)
    # Khớp đúng trước, rồi bắt đầu bằng, rồi chứa; ngắn trước.
    rank = (LexicalEntry.normalized_form != key, ~LexicalEntry.normalized_form.like(f"{key}%"),
            func.length(LexicalEntry.normalized_form), LexicalEntry.normalized_form)
    return stmt.where(cond).order_by(*rank)


def similar_examples(db: Session, text: str, source: str, limit: int = 5) -> list[dict]:
    """Câu ví dụ song ngữ khớp nguyên câu hoặc chứa cụm cần dịch (gợi ý tham khảo, chưa phải bản dịch đã xác minh)."""
    term_index.ensure(db)
    key = search_key(text)
    if len(key) < 2:
        return []
    col = 0 if source == "ede" else 1
    exact, partial = [], []
    for row in term_index.examples:
        if row[col] == key:
            exact.append(row)
        elif len(partial) < limit * 4 and (key in row[col] or (len(row[col]) > 3 and row[col] in key)):
            partial.append(row)
    partial.sort(key=lambda r: abs(len(r[col]) - len(key)))
    return [{"ede": r[2], "vi": r[3], "exact": r in exact, "verification_status": r[4]}
            for r in (exact + partial)[:limit]]
