"""Chuẩn hoá Unicode theo docs/04 §4: giữ nguyên chữ hiển thị, khoá tìm kiếm là trường riêng.

- Hiển thị/lưu: NFC, không NFKC, không bỏ dấu phụ hay ký tự ngoài ASCII.
- Khoá tìm kiếm: NFC + casefold + gộp khoảng trắng. Vẫn giữ dấu (ă khác a, ƀ khác b).
"""
from __future__ import annotations

import re
import unicodedata

_SPACE = re.compile(r"\s+")
# Ký tự đặc thù chữ Ê Đê (theo bảng chữ cái trong từ điển nguồn) dùng để gợi ý ngôn ngữ, không phải để kết luận.
EDE_MARKERS = set("ƀƁčČĕĔĭĬŏŎŭŬñÑ") | {"̆"}  # ̆: dấu á (breve) đi kèm ê̆, ô̆, ơ̆, ư̆
WORD = re.compile(r"[^\W\d_]+(?:[̀-ͯ]*[^\W\d_]*)*", re.UNICODE)


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def search_key(text: str) -> str:
    return _SPACE.sub(" ", nfc(text).casefold()).strip()


def words(text: str) -> list[str]:
    return WORD.findall(nfc(text))


def guess_language(text: str) -> str:
    """Gợi ý ngôn ngữ: 'ede' nếu có ký tự riêng của chữ Ê Đê, ngược lại 'vi'. Người dùng luôn chọn lại được."""
    return "ede" if any(ch in EDE_MARKERS for ch in nfc(text)) else "vi"
