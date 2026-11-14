#!/usr/bin/env python3
"""Xuất dữ liệu cho web tĩnh (thư mục web/) từ từ điển và bộ dữ liệu song ngữ.

    python scripts/export_web_data.py              # từ điển + câu ví dụ + Kinh Thánh
    python scripts/export_web_data.py --no-bible   # bỏ Kinh Thánh khỏi web (xem phần bản quyền)

Đầu ra:
  web/data/dictionary.json   các mục từ, gọn để trình duyệt tải nhanh
  web/data/pairs.json        các cặp câu Ê Đê – Việt để tìm câu tương tự

Lưu ý bản quyền: web tĩnh cho phép bất kỳ ai tải nguyên các file này. Bản Kinh Thánh Ê Đê 2015
nhiều khả năng còn bản quyền, nên chỉ để Kinh Thánh trên web nếu web không công khai.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DICTIONARY = ROOT / "data" / "dictionary" / "dictionary_full.json"
DATASET = ROOT / "data" / "dataset"
OUT = ROOT / "web" / "data"
SPLITS = ("train", "dev_bible", "dev_dict", "test_bible", "test_dict")
SOURCES = {"bible": "Kinh Thánh", "dict_example": "Từ điển", "paper": "Bài báo"}


def short_pos(full: str) -> str:
    """'Động từ hoặc những tổ hợp tương đương' -> 'Động từ'; 'bt – KHÔNG có trong bảng…' -> 'bt'."""
    return re.sub(r"\s*\(.*", "", full.split(" – ")[0].split(" hoặc ")[0]).strip()


def dump(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{path.relative_to(ROOT)}: {path.stat().st_size / 1e6:.1f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-bible", action="store_true", help="không đưa câu Kinh Thánh lên web")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    source = json.loads(DICTIONARY.read_text(encoding="utf-8"))
    entries = [{
        "id": e["id"], "h": e["headword"], "v": e["variants"], "a": e["alt_forms"],
        "p": [short_pos(p["full"]) for p in e["pos"]], "pg": e["book_page"],
        "s": [[s["label"], s["gloss_vi"], short_pos(s["pos"]["full"]) if s["pos"] else None,
               [[x["ede"], x["vi"]] for x in s["examples"]]] for s in e["senses"]],
    } for e in source["entries"]]
    dump(OUT / "dictionary.json", {"entries": entries})

    names = list(SOURCES.values())
    rows, seen = [], set()
    for split in SPLITS:
        for line in (DATASET / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["source"] not in SOURCES or (args.no_bible and row["source"] == "bible"):
                continue
            if (row["ede"], row["vi"]) in seen:
                continue
            seen.add((row["ede"], row["vi"]))
            ref = row.get("ref", "") if row["source"] == "bible" else ""
            rows.append([row["ede"], row["vi"], names.index(SOURCES[row["source"]]), ref])
    dump(OUT / "pairs.json", {"sources": names, "rows": rows})
    print(f"{len(entries)} mục từ, {len(rows)} cặp câu" + (" (không có Kinh Thánh)" if args.no_bible else ""))


if __name__ == "__main__":
    main()
