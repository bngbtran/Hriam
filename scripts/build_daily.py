#!/usr/bin/env python3
"""Dựng bộ dữ liệu cho giai đoạn train "văn nói": câu đời thường là chính, thêm ít Kinh Thánh để mô hình không quên.

    python scripts/build_daily.py --base data/dataset_bpt --out data/dataset_noi

Nguồn câu đời thường:
  - Ví dụ và nghĩa trong từ điển (đã có trong bộ dữ liệu gốc --base).
  - Câu hội thoại nhóm tự thu thập trong data/raw/hoi_thoai/: file .tsv có dòng tiêu đề "vi<TAB>ede",
    hoặc file .jsonl mỗi dòng {"vi": ..., "ede": ...}. Xem data/raw/hoi_thoai/README.md.

Ra: train.jsonl, dev_dict.jsonl, dev_hoithoai.jsonl (nếu có), test_dict.jsonl, test_hoithoai.jsonl (nếu có),
test_bible.jsonl (để xem mô hình có quên Kinh Thánh không), stats.json. Mô hình tốt nhất được chọn theo
các tập dev, toàn là câu đời thường.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONV_DIR = ROOT / "data" / "raw" / "hoi_thoai"
SEED = 42
DAILY_SOURCES = {"dict_example", "dict_word", "paper"}


def short(path: Path) -> str:
    """Đường dẫn gọn để in ra: tương đối với repo nếu nằm trong repo."""
    path = path.resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")


def clean(text: str) -> str:
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", text or "")).strip()


def bucket(key: str) -> float:
    return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF


def load_conversations(folder: Path) -> list[dict]:
    rows = []
    for path in sorted(folder.glob("*.tsv")):
        with path.open(encoding="utf-8", newline="") as src:
            for i, rec in enumerate(csv.DictReader(src, delimiter="\t"), 2):
                vi, ede = clean(rec.get("vi")), clean(rec.get("ede"))
                if vi and ede:
                    rows.append({"ede": ede, "vi": vi, "source": "hoi_thoai", "ref": f"{path.name}:{i}"})
    for path in sorted(folder.glob("*.jsonl")):
        for i, rec in enumerate(read_jsonl(path), 1):
            vi, ede = clean(rec.get("vi")), clean(rec.get("ede"))
            if vi and ede:
                rows.append({"ede": ede, "vi": vi, "source": "hoi_thoai", "ref": f"{path.name}:{i}"})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", type=Path, default=ROOT / "data" / "dataset", help="bộ dữ liệu gốc đã dựng")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "dataset_noi")
    parser.add_argument("--conv-dir", type=Path, default=CONV_DIR, help="thư mục câu hội thoại")
    parser.add_argument("--replay", type=int, default=3000, help="số câu Kinh Thánh ngắn trộn vào để không quên")
    parser.add_argument("--max-words", type=int, default=25, help="chỉ lấy câu Kinh Thánh ngắn, gần với câu nói")
    parser.add_argument("--conv-repeat", type=int, default=3, help="số lần lặp câu hội thoại trong tập train")
    args = parser.parse_args()
    rng = random.Random(SEED)
    base, out = args.base.resolve(), args.out.resolve()
    if not (base / "train.jsonl").exists():
        raise SystemExit(f"LỖI: không thấy {base}/train.jsonl. Hãy chạy scripts/build_dataset.py trước.")
    out.mkdir(parents=True, exist_ok=True)

    base_train = read_jsonl(base / "train.jsonl")
    daily = [r for r in base_train if r["source"] in DAILY_SOURCES]
    bible = [r for r in base_train if r["source"] == "bible" and len(r["vi"].split()) <= args.max_words]
    replay = rng.sample(bible, min(args.replay, len(bible)))

    conv = load_conversations(args.conv_dir)
    seen, conv_unique = set(), []
    for row in conv:
        key = (row["ede"].lower(), row["vi"].lower())
        if key not in seen:
            seen.add(key)
            conv_unique.append(row)
    splits: dict[str, list[dict]] = {"train": [], "dev": [], "test": []}
    for row in conv_unique:
        value = bucket(row["vi"].lower())
        splits["test" if value < 0.1 else "dev" if value < 0.2 else "train"].append(row)
    held_out = {r["ede"].lower() for r in splits["dev"] + splits["test"]}
    held_out |= {r["ede"].lower() for name in ("dev_dict", "test_dict") for r in read_jsonl(base / f"{name}.jsonl")}

    train = daily + replay + splits["train"] * args.conv_repeat
    train = [r for r in train if r["ede"].lower() not in held_out]
    rng.shuffle(train)

    for old in out.glob("*.jsonl"):
        old.unlink()
    write_jsonl(out / "train.jsonl", train)
    files = {"dev_dict": read_jsonl(base / "dev_dict.jsonl"), "test_dict": read_jsonl(base / "test_dict.jsonl"),
             "test_bible": read_jsonl(base / "test_bible.jsonl")}
    if splits["dev"]:
        files["dev_hoithoai"] = splits["dev"]
    if splits["test"]:
        files["test_hoithoai"] = splits["test"]
    for name, rows in files.items():
        if rows:
            write_jsonl(out / f"{name}.jsonl", rows)

    stats = {"base": short(base), "train": {"pairs": len(train), **Counter(r["source"] for r in train)},
             **{name: len(rows) for name, rows in files.items() if rows},
             "hoi_thoai": {"tong": len(conv_unique), **{k: len(v) for k, v in splits.items()}}}
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if not conv_unique:
        print("\nChưa có câu hội thoại nào trong", short(args.conv_dir),
              "- mô hình sẽ học văn nói chủ yếu từ ví dụ trong từ điển. Thêm câu hội thoại để dịch tự nhiên hơn.")


if __name__ == "__main__":
    main()
