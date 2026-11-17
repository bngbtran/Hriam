#!/usr/bin/env python3
"""Dịch Ê Đê ↔ Việt bằng mô hình đã train.

    python scripts/translate.py "Jŭ msĕ si ak"           # dịch một câu, Ê Đê → Việt
    python scripts/translate.py --direction vi2ede "Đen như quạ"
    python scripts/translate.py --file input.txt > output.txt  # mỗi dòng một câu
    python scripts/translate.py                                # gõ từng câu, Enter để dịch, Ctrl+D để thoát
    python scripts/translate.py --model base "..."            # NLLB gốc chưa train, để so sánh

Mặc định dùng models/<hướng> (mô hình chính thức), nếu không có thì kết quả train mới nhất trong runs/.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import torch  # noqa: E402
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MODEL_NAME = "facebook/nllb-200-distilled-600M"
LANG_CODES = {"ede": "ace_Latn", "vi": "vie_Latn"}
DIRECTIONS = {"ede2vi": ("ede", "vi"), "vi2ede": ("vi", "ede")}
MAX_LENGTH = 128
BATCH = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("text", nargs="*", help="câu cần dịch; bỏ trống để gõ từng câu")
    parser.add_argument("--direction", choices=DIRECTIONS, default="ede2vi")
    parser.add_argument("--model", help="thư mục mô hình, hoặc 'base' cho NLLB gốc; mặc định models/<hướng>")
    parser.add_argument("--file", type=Path, help="file văn bản, mỗi dòng một câu")
    parser.add_argument("--beams", type=int, default=4)
    return parser.parse_args()


def decode_ede(tokenizer, ids) -> list[str]:
    """Giải mã, giữ lại chữ ƀ/Ƀ.

    Bộ từ vựng NLLB không có ƀ nên mô hình sinh <unk> ở chỗ đó; giải mã thường bỏ <unk>, "ƀŏng" thành "ŏng".
    Trong tiếng Ê Đê ƀ là ký tự duy nhất hay gặp bị <unk>, nên đổi <unk> lại thành ƀ (đầu câu thì viết hoa).
    """
    drop = set(tokenizer.all_special_ids) - {tokenizer.unk_token_id}
    texts = tokenizer.batch_decode([[i for i in row.tolist() if i not in drop] for row in ids])
    texts = [t.replace(tokenizer.unk_token, "ƀ").strip() for t in texts]
    return [re.sub(r"(^|[.!?]\s+)ƀ", lambda m: m.group(1) + "Ƀ", t) for t in texts]


class Translator:
    def __init__(self, model: str, direction: str, beams: int):
        src, tgt = DIRECTIONS[direction]
        self.device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(model, src_lang=LANG_CODES[src], tgt_lang=LANG_CODES[tgt])
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model).to(self.device).eval()
        self.model.generation_config.max_length = None
        self.target_id = self.tokenizer.convert_tokens_to_ids(LANG_CODES[tgt])
        self.beams = beams
        self.decode = (lambda ids: decode_ede(self.tokenizer, ids)) if tgt == "ede" else \
            (lambda ids: self.tokenizer.batch_decode(ids, skip_special_tokens=True))

    @torch.no_grad()
    def __call__(self, sentences: list[str]) -> list[str]:
        output = []
        for start in range(0, len(sentences), BATCH):
            part = [unicodedata.normalize("NFC", s.strip()) for s in sentences[start:start + BATCH]]
            batch = self.tokenizer(part, return_tensors="pt", padding=True, truncation=True,
                                   max_length=MAX_LENGTH).to(self.device)
            ids = self.model.generate(**batch, forced_bos_token_id=self.target_id, num_beams=self.beams,
                                      max_new_tokens=MAX_LENGTH, no_repeat_ngram_size=3)
            output += self.decode(ids)
        return output


def resolve_model(args: argparse.Namespace) -> str:
    if args.model == "base":
        return MODEL_NAME
    if args.model:
        path = Path(args.model)
    else:  # ưu tiên mô hình văn nói của scripts/train_daily.py, rồi tới mô hình của scripts/train.py
        candidates = [ROOT / "models" / args.direction, ROOT / "runs" / f"{args.direction}-noi" / "best",
                      ROOT / "runs" / args.direction / "best"]
        path = next((p for p in candidates if (p / "config.json").exists()), candidates[-1])
    if not (path / "config.json").exists():
        sys.exit(f"LỖI: không thấy mô hình ở {path}. Hãy train trước: python scripts/train_daily.py {args.direction}")
    return str(path)


def main() -> None:
    args = parse_args()
    translate = Translator(resolve_model(args), args.direction, args.beams)
    if args.file:
        lines = args.file.read_text(encoding="utf-8").splitlines()
        keep = [i for i, line in enumerate(lines) if line.strip()]
        results = dict(zip(keep, translate([lines[i] for i in keep])))
        for i in range(len(lines)):
            print(results.get(i, ""))
    elif args.text:
        print(translate([" ".join(args.text)])[0])
    else:
        print("Gõ câu rồi Enter. Ctrl+D để thoát.", file=sys.stderr)
        for line in sys.stdin:
            if line.strip():
                print(translate([line])[0], flush=True)


if __name__ == "__main__":
    main()
