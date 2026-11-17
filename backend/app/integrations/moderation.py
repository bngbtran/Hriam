"""Adapter kiểm duyệt tự động bằng quy tắc (docs/05). Chưa có mô hình kiểm duyệt hiểu tiếng Ê Đê, nên:

- Chỉ đăng ngay nội dung tiếng Kinh rõ ràng không có dấu hiệu bất thường.
- Nội dung có tiếng Ê Đê, trộn ngôn ngữ, có liên kết hoặc khớp danh sách từ cần xem -> giữ ẩn, chờ người duyệt.
- Dấu hiệu spam rõ (nhiều liên kết, lặp ký tự dài) -> từ chối tự động nhưng KHÔNG tính strike.
- Hệ thống không bao giờ tự tính strike; strike chỉ do moderator áp dụng sau khi xác nhận.
Danh sách từ cần xem nằm ở backend/app/integrations/moderation_terms.json, do Language Expert quản lý.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core.config import settings
from ..core.text import guess_language, search_key

TERMS_FILE = Path(__file__).with_name("moderation_terms.json")
URL = re.compile(r"https?://|www\.", re.I)
REPEAT = re.compile(r"(.)\1{14,}")


@dataclass
class Verdict:
    decision: str  # publish, human_review, reject
    risk_level: str
    reason_code: str | None
    language: str
    results: dict = field(default_factory=dict)


def _terms() -> list[dict]:
    try:
        return json.loads(TERMS_FILE.read_text(encoding="utf-8")).get("terms", [])
    except (OSError, json.JSONDecodeError):
        return []


def evaluate(text: str) -> Verdict:
    language = guess_language(text)
    key = search_key(text)
    links = len(URL.findall(text))
    hits = [t["category"] for t in _terms() if search_key(t["term"]) in key]
    results = {"policy_version": settings.moderation_policy_version, "language_hint": language, "links": links,
               "term_hits": sorted(set(hits)), "detector": "rules-v1"}
    if links > 3 or REPEAT.search(text):
        return Verdict("reject", "high", "SPAM", language, results)
    if hits:
        return Verdict("human_review", "medium", "TERM_MATCH", language, results)
    if language != "vi":
        return Verdict("human_review", "unknown", "LOW_LANGUAGE_COVERAGE", language, results)
    if links:
        return Verdict("human_review", "low", "CONTAINS_LINK", language, results)
    return Verdict("publish", "low", None, language, results)
