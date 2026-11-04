#!/usr/bin/env python3
"""Gộp Kinh Thánh, từ điển và ví dụ trong bài báo thành bộ dữ liệu Ê Đê – Việt ở data/dataset/.

Chia dữ liệu theo nhóm để tránh rò rỉ: nguyên chương Kinh Thánh, nguyên mục từ điển.
Mục từ và nghĩa của từ điển chỉ vào train. Từ điển được quy về chính tả Kinh Thánh (spelling_map.json).
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "interim"
OUT = ROOT / "data" / "dataset"
LANGS = ("ede", "vi")
BIBLE_DEV, BIBLE_TEST = 0.025, 0.025
DICT_DEV, DICT_TEST = 0.05, 0.10
RATIO_MIN, RATIO_MAX = 0.4, 3.0  # tỉ lệ độ dài Ê Đê / Việt để coi là câu ghép đúng

# Chép tay từ data/raw/GiaiMaTiengEDE.pdf, mục 2.3. "kleih" trong bài báo được sửa thành "klei".
PAPER_PAIRS = [
    ("siam snăk", "rất đẹp"),
    ("Ti anôk sang ih?", "Nhà anh ở đâu?"),
    ("Ya bruă ih ngă?", "Anh làm nghề gì?"),
    ("Ya mnơ̆ng ih čiăng ngă?", "Anh muốn làm cái gì?"),
    ("Si ngă klei hdĭp gŏ êsei ih?", "Cuộc sống gia đình anh thế nào?"),
]
WORD_RE = re.compile(r"[^\W\d_](?:[^\W\d_]|[\u0300-\u036f])*")


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as src:
        return [json.loads(line) for line in src if line.strip()]


def bucket(key: str) -> float:
    return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF


def clean(text: str) -> str:
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", text)).strip()


def bible_rows(rejected: list[dict]) -> list[dict]:
    rows = []
    for row in read_jsonl(DATA / "parallel_aligned.jsonl"):
        book, chapter = row["ref_ede"].split(".")[:2]
        ratio = len(row["ede"]) / max(1, len(row["vi"]))
        out = {"ede": clean(row["ede"]), "vi": clean(row["vi"]), "source": "bible",
               "ref": row["ref_ede"], "ref_vi": row["ref_vi"]}
        if row["low_coverage"] or not RATIO_MIN <= ratio <= RATIO_MAX:
            rejected.append({**out, "reason": f'ratio={ratio:.2f} coverage={row["coverage"]}'})
            continue
        value = bucket(f"{book}.{chapter}")
        out["split"] = "test_bible" if value < BIBLE_TEST else "dev_bible" if value < BIBLE_TEST + BIBLE_DEV else "train"
        rows.append(out)
    return rows


NORMALIZABLE = ("ơ\u0306", "ô\u0306", "ê\u0306")


def bible_vocabulary() -> Counter:
    counts: Counter = Counter()
    for row in read_jsonl(DATA / "ede.jsonl"):
        counts.update(WORD_RE.findall(clean(row["text"]).lower()))
    return counts


def breve_key(word: str) -> str:
    """Gộp các chữ mà sách và Kinh Thánh viết khác nhau: ŏ/ô̆/ơ̆, ĕ/ê̆/ê, ŭ/ư̆."""
    text = clean(word)
    for old, new in (("ơ\u0306", "O"), ("ô\u0306", "O"), ("ŏ", "O"), ("ê\u0306", "E"), ("ĕ", "E"), ("ê", "E"),
                     ("ư\u0306", "U"), ("ŭ", "U")):
        text = text.replace(old, new)
    return text


def spelling_normalizer(vocabulary: Counter):
    """Quy chính tả từ điển về Kinh Thánh, chỉ khi từ vắng trong Kinh Thánh và có đúng một dạng tương ứng."""
    by_key: dict[str, list[str]] = {}
    for word in vocabulary:
        by_key.setdefault(breve_key(word), []).append(word)
    applied: Counter = Counter()

    def normalize(text: str) -> str:
        def replace(match: re.Match) -> str:
            word = match[0]
            lower = word.lower()
            candidates = by_key.get(breve_key(lower), [])
            # Chỉ các chữ ơ̆, ô̆, ê̆: đây là khác biệt chính tả đã kiểm chứng trên bản scan.
            if lower in vocabulary or len(candidates) != 1 or not any(c in lower for c in NORMALIZABLE):
                return word
            applied[f"{lower} -> {candidates[0]}"] += 1
            return candidates[0][0].upper() + candidates[0][1:] if word[0].isupper() else candidates[0]
        return WORD_RE.sub(replace, clean(text))

    return normalize, applied


def dictionary_rows(normalize) -> list[dict]:
    rows = []
    for entry in read_jsonl(DATA / "dictionary.jsonl"):
        value = bucket(entry["headword"].lower())
        split = "test_dict" if value < DICT_TEST else "dev_dict" if value < DICT_TEST + DICT_DEV else "train"
        ref = f'dict.p{entry["page"]}'
        headword = normalize(re.sub(r"\s*\([^)]*\)?", "", entry["headword"]))
        for sense in entry["senses"]:
            if sense["gloss"]:
                rows.append({"ede": headword, "vi": clean(sense["gloss"]), "source": "dict_word",
                             "ref": ref, "split": "train"})
            for example in sense["examples"]:
                rows.append({"ede": normalize(example["ede"]), "vi": clean(example["vi"]),
                             "source": "dict_example", "ref": ref, "split": split})
    return [row for row in rows if len(row["ede"]) >= 1 and len(row["vi"]) >= 1]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rejected: list[dict] = []
    normalize, applied = spelling_normalizer(bible_vocabulary())
    rows = bible_rows(rejected) + dictionary_rows(normalize)
    rows += [{"ede": e, "vi": v, "source": "paper", "ref": "GiaiMaTiengEDE", "split": "train"} for e, v in PAPER_PAIRS]

    # Bỏ trùng; cặp nằm ở dev/test được ưu tiên giữ, rồi loại khỏi train để không rò rỉ.
    rows.sort(key=lambda r: r["split"] == "train")
    seen, unique = set(), []
    for row in rows:
        key = (row["ede"].lower(), row["vi"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(row)
    held_out_ede = {r["ede"].lower() for r in unique if r["split"] != "train"}
    unique = [r for r in unique if r["split"] != "train" or r["ede"].lower() not in held_out_ede]

    stats: dict = {"splits": {}, "rejected": len(rejected)}
    for split in sorted({r["split"] for r in unique}):
        part = [{k: v for k, v in r.items() if k != "split"} for r in unique if r["split"] == split]
        with (OUT / f"{split}.jsonl").open("w", encoding="utf-8") as out:
            for row in part:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
        stats["splits"][split] = {"pairs": len(part), **Counter(r["source"] for r in part)}
    with (OUT / "rejected.jsonl").open("w", encoding="utf-8") as out:
        for row in rejected:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    (OUT / "spelling_map.json").write_text(
        json.dumps(dict(applied.most_common()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stats["spelling_normalized"] = {"types": len(applied), "tokens": sum(applied.values())}
    (OUT / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
