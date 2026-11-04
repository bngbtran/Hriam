#!/usr/bin/env python3
"""Phân tích bản chép tay từ điển (data/raw/dict_transcribed/pNNN.txt) thành data/interim/dictionary.jsonl.

Mỗi dòng có dạng 'mục từ (từ loại) | nội dung'. Dòng bắt đầu bằng '| ' nối tiếp mục từ của trang trước.
Giữ nguyên lỗi in trong sách. Trang 146–147 của sách không có trong bản scan.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "raw" / "dict_transcribed"
OUTPUT = ROOT / "data" / "interim" / "dictionary.jsonl"

POS = {"dt", "đgt", "tt", "đt", "pht", "phó từ", "trt", "trgt", "trạng từ", "lt", "liên từ", "gt", "giới từ",
       "bt", "ht", "tht", "ct", "st", "số từ", "tl", "pt", "hư từ", "đại từ", "phụ từ", "trợ từ", "trtừ", "tng",
       "đại từ chỉ định", "đen", "bóng"}
LOAN = {"yu": "Việt", "yuăn": "Việt", "pr": "Pháp", "prăng": "Pháp", "anh": "Anh"}
NOT_EDE = set("àáảãạằắẳẵặấầẩẫậèéẻẽẹếềểễệìíỉĩịòóỏõọốồổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ")
SENSE_RE = re.compile(r"(?:^|(?<=[.;:?!)]\s))(?:[1-9]|I{1,3})(?:[.,]\s*|\s+(?=[A-ZĐÂĂÊÔƠƯ(]))")
LEADING_TAG_RE = re.compile(r"^\(\s*([^()]{1,20}?)\s*\)\s*[.,:]?\s*")


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", text)).strip()


def vi_ratio(text: str) -> float:
    words = re.findall(r"[^\W\d_]+", text.lower())
    return sum(bool(set(w) & NOT_EDE) for w in words) / max(1, len(words))


def parse_head(head: str) -> tuple[str, list[str], str | None]:
    pos, loan = [], None
    head = head.strip()
    while True:
        match = re.search(r"\(?\s*([^()\s][^()]{0,14}?)\s*\)\s*$", head)
        if not match:
            break
        tag = match[1].strip().lower()
        if tag in POS:
            pos.insert(0, tag)
        elif tag in LOAN:
            loan = LOAN[tag]
        else:
            break
        head = head[: match.start()].strip()
    return head.strip(" :;."), pos, loan


def split_examples(sense: str) -> dict:
    """Đoạn 'Ê Đê: Việt' là ví dụ; đoạn đầu không có dấu hai chấm là phần giải nghĩa."""
    pos = []
    while (match := LEADING_TAG_RE.match(sense)) and match[1].lower() in POS:
        pos.append(match[1].lower())
        sense = sense[match.end():]
    sense = re.sub(r"^[1-9][.,]?\s*(?=\S)", "", sense)
    gloss: list[str] = []
    examples: list[dict] = []
    segments = [s.strip() for s in re.split(r"(?<=[.;!?])\s+", sense) if s.strip()]
    gloss_open = True
    for segment in segments:
        if ":" not in segment:
            if gloss_open:
                gloss.append(segment)
                gloss_open = segment.endswith(";")
            continue
        gloss_open = False
        left, right = (part.strip() for part in segment.split(":", 1))
        if ":" in right:  # 'Xem: Dlăng rup: Xem tranh' — phần trước là giải nghĩa
            if not gloss:
                gloss.append(left)
            left, right = (part.strip() for part in right.split(":", 1))
        right = right.rstrip(" ;.")
        if vi_ratio(left) > 0.5 and vi_ratio(right) <= 0.5:  # sách đảo thứ tự Việt: Ê Đê
            left, right = right, left
        if left and right and vi_ratio(left) <= 0.5:
            examples.append({"ede": nfc(left), "vi": nfc(right)})
    return {"gloss": nfc(" ".join(gloss)).rstrip(" .;"), "pos": pos, "examples": examples}


def main() -> None:
    raw: list[dict] = []
    for path in sorted(SOURCE.glob("p*.txt")):
        page = int(path.stem[1:])
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            head, _, body = line.partition("|")
            if head.strip():
                raw.append({"head": head, "body": body.strip(), "page": page})
            else:
                raw[-1]["body"] += " " + body.strip()

    entries = []
    for item in raw:
        headword, pos, loan = parse_head(item["head"])
        senses = [split_examples(part.strip()) for part in SENSE_RE.split(item["body"]) if part.strip()]
        senses = [s for s in senses if s["gloss"] or s["examples"]]
        entries.append({"headword": nfc(headword), "pos": pos, "loan": loan, "senses": senses,
                        "page": item["page"], "raw": nfc(item["head"] + " | " + item["body"])})
    with OUTPUT.open("w", encoding="utf-8") as out:
        for entry in entries:
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
    examples = sum(len(s["examples"]) for e in entries for s in e["senses"])
    print(f"{len(entries)} mục từ, {examples} câu ví dụ, {sum(not e['senses'] for e in entries)} mục không có nghĩa")


if __name__ == "__main__":
    main()
