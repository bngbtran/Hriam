#!/usr/bin/env python3
"""Web dịch Việt ↔ Ê Đê, chạy trên máy.

    conda activate msa
    python app/server.py              # mở http://127.0.0.1:8000
    python app/server.py --port 8080

Web dùng được ngay mà không cần train:
  - Dịch từng từ: ghép nghĩa từ điển theo cụm dài nhất khớp được (chỉ để tham khảo).
  - Từ điển: các mục từ xuất hiện trong câu, kèm nghĩa và ví dụ.
  - Câu tương tự: các cặp câu song ngữ gần giống nhất trong Kinh Thánh và từ điển.
Nếu đã train (runs/<hướng>/best tồn tại), web có thêm bản dịch máy cả câu.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import unicodedata
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
DICTIONARY = ROOT / "data" / "dictionary" / "dictionary_full.json"
DATASET = ROOT / "data" / "dataset"
RUNS = ROOT / "runs"
DIRECTIONS = {"vi2ede": ("vi", "ede"), "ede2vi": ("ede", "vi")}
MAX_PHRASE = 5          # số từ tối đa của một cụm khi tra từ điển
MAX_INPUT = 2000        # số ký tự tối đa của một lần dịch
WORD_RE = re.compile(r"[^\W\d_](?:[^\W\d_]|[̀-ͯ]|')*")
# Từ chỉ loại đứng đầu nghĩa tiếng Việt, bỏ đi để "cóc" khớp được "Con cóc".
VI_CLASSIFIERS = ("cái ", "con ", "cây ", "quả ", "trái ", "sự ", "việc ", "người ", "bộ ", "chiếc ")
SOURCES = {"bible": "Kinh Thánh", "dict_example": "Từ điển", "dict_word": "Từ điển", "paper": "Bài báo"}

sys.path.insert(0, str(ROOT / "scripts"))


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def fold(text: str) -> str:
    """Bỏ dấu để tra được cả khi người dùng gõ thiếu dấu: 'dhong' khớp 'Dhŏng'."""
    text = unicodedata.normalize("NFD", text.lower()).replace("đ", "d").replace("ƀ", "b")
    return unicodedata.normalize("NFC", "".join(ch for ch in text if not unicodedata.combining(ch)))


def words(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(nfc(text))]


def strip_parens(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", text).strip()


def vi_phrases(gloss: str) -> list[str]:
    """'Bà (nội, ngoại)' -> ['bà']; 'Xén, cắt' -> ['xén', 'cắt']; thêm dạng bỏ từ chỉ loại."""
    out = []
    for part in re.split(r"[,;.]", strip_parens(gloss)):
        phrase = " ".join(words(part))
        if not phrase:
            continue
        out.append(phrase)
        for prefix in VI_CLASSIFIERS:
            if phrase.startswith(prefix) and len(phrase) > len(prefix):
                out.append(phrase[len(prefix):])
    return out


class Dictionary:
    def __init__(self, path: Path):
        self.entries = json.loads(path.read_text(encoding="utf-8"))["entries"]
        self.ede: dict[str, list[int]] = {}
        self.ede_folded: dict[str, list[int]] = {}
        self.vi: dict[str, list[tuple[int, int]]] = {}       # cụm Việt -> (mục, độ ưu tiên)
        for i, entry in enumerate(self.entries):
            forms = entry["variants"] or [entry["headword"]]
            forms = [strip_parens(f) for f in forms] + list(entry["alt_forms"])
            for form in forms:
                key = " ".join(words(form))
                if key:
                    self.ede.setdefault(key, []).append(i)
                    self.ede_folded.setdefault(fold(key), []).append(i)
            for rank, sense in enumerate(entry["senses"]):
                for j, phrase in enumerate(vi_phrases(sense["gloss_vi"])):
                    self.vi.setdefault(phrase, []).append((i, rank + j))
        for key in self.vi:
            self.vi[key] = sorted(set(self.vi[key]), key=lambda t: (t[1], len(self.entries[t[0]]["headword"])))

    def lookup(self, phrase: list[str], lang: str) -> tuple[list[int], bool]:
        """Trả về (các mục, khớp chính xác hay khớp bỏ dấu)."""
        key = " ".join(phrase)
        if lang == "ede":
            if key in self.ede:
                return self.ede[key], True
            return self.ede_folded.get(fold(key), []), False
        return [i for i, _ in self.vi.get(key, [])], True

    def segment(self, text: str, lang: str) -> list[dict]:
        """Ghép theo cụm dài nhất khớp từ điển, từ trái sang phải."""
        tokens, out, i = words(text), [], 0
        while i < len(tokens):
            # "con dao": "con" chỉ là từ chỉ loại khi phần sau tra được, tránh dịch thành "Anak" (con cái).
            if (lang == "vi" and f"{tokens[i]} " in VI_CLASSIFIERS and i + 1 < len(tokens)
                    and self.lookup(tokens[i + 1:i + 2], lang)[0]
                    and not self.lookup(tokens[i:i + 2], lang)[0]):
                out.append({"text": tokens[i], "entries": [], "exact": True, "classifier": True})
                i += 1
                continue
            for size in range(min(MAX_PHRASE, len(tokens) - i), 0, -1):
                found, exact = self.lookup(tokens[i:i + size], lang)
                if found:
                    out.append({"text": " ".join(tokens[i:i + size]), "entries": found[:6], "exact": exact})
                    i += size
                    break
            else:
                out.append({"text": tokens[i], "entries": [], "exact": False})
                i += 1
        return out

    def short(self, index: int, lang: str) -> str:
        entry = self.entries[index]
        if lang == "ede":         # nguồn Ê Đê -> lấy nghĩa Việt
            gloss = strip_parens(entry["senses"][0]["gloss_vi"]) if entry["senses"] else ""
            return re.split(r"[,;]", gloss)[0].strip()
        return (entry["variants"] or [strip_parens(entry["headword"])])[0]

    def card(self, index: int) -> dict:
        entry = self.entries[index]
        return {"id": entry["id"], "headword": entry["headword"],
                "pos": [p["full"] for p in entry["pos"]], "page": entry["book_page"],
                "senses": [{"label": s["label"], "gloss": s["gloss_vi"],
                            "pos": s["pos"]["full"] if s["pos"] else None,
                            "examples": s["examples"][:4]} for s in entry["senses"]]}


class Corpus:
    """Tìm cặp câu song ngữ gần giống câu nhập vào, theo n-gram ký tự."""

    def __init__(self, folder: Path):
        self.rows = []
        seen = set()
        for name in ("train", "dev_bible", "dev_dict", "test_bible", "test_dict"):
            for line in (folder / f"{name}.jsonl").read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                key = (row["ede"], row["vi"])
                if row["source"] != "dict_word" and key not in seen:
                    seen.add(key)
                    self.rows.append(row)
        self.index = {}
        for lang in ("ede", "vi"):
            vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True,
                                         preprocessor=fold if lang == "ede" else str.lower)
            self.index[lang] = (vectorizer, vectorizer.fit_transform([r[lang] for r in self.rows]))

    def similar(self, text: str, lang: str, k: int = 6) -> list[dict]:
        vectorizer, matrix = self.index[lang]
        scores = linear_kernel(vectorizer.transform([text]), matrix).ravel()
        best = scores.argsort()[::-1][:k]
        return [{"ede": self.rows[i]["ede"], "vi": self.rows[i]["vi"], "score": round(float(scores[i]), 3),
                 "source": SOURCES.get(self.rows[i]["source"], self.rows[i]["source"]), "ref": self.rows[i].get("ref")}
                for i in best if scores[i] > 0.12]


class Models:
    """Nạp mô hình đã train khi cần lần đầu; không có thì web vẫn chạy."""

    def __init__(self):
        self.loaded: dict[str, object] = {}
        self.lock = threading.Lock()

    @staticmethod
    def path(direction: str) -> Path:
        return RUNS / direction / "best"

    def available(self, direction: str) -> bool:
        return (self.path(direction) / "config.json").exists()

    def translate(self, text: str, direction: str) -> str | None:
        if not self.available(direction):
            return None
        with self.lock:
            if direction not in self.loaded:
                from translate import Translator
                self.loaded[direction] = Translator(str(self.path(direction)), direction, beams=4)
            lines = [line for line in text.splitlines() if line.strip()]
            return "\n".join(self.loaded[direction](lines))


class App:
    def __init__(self):
        print("Đang nạp từ điển và kho câu...", flush=True)
        self.dictionary = Dictionary(DICTIONARY)
        self.corpus = Corpus(DATASET)
        self.models = Models()
        print(f"Đã nạp {len(self.dictionary.entries)} mục từ, {len(self.corpus.rows)} cặp câu.", flush=True)

    def status(self) -> dict:
        return {"entries": len(self.dictionary.entries), "pairs": len(self.corpus.rows),
                "models": {d: self.models.available(d) for d in DIRECTIONS}}

    def translate(self, text: str, direction: str) -> dict:
        src, tgt = DIRECTIONS[direction]
        text = nfc(text.strip())[:MAX_INPUT]
        segments = self.dictionary.segment(text, src)
        gloss, cards, shown = [], [], set()
        for seg in segments:
            options = []
            for i in seg["entries"]:
                value = self.dictionary.short(i, src)
                if value and value.lower() not in (o.lower() for o in options):
                    options.append(value)
                if i not in shown and len(cards) < 12:
                    shown.add(i)
                    cards.append(self.dictionary.card(i))
            gloss.append({"source": seg["text"], "options": options[:4], "exact": seg["exact"],
                          "classifier": seg.get("classifier", False)})
        parts = [g["options"][0].lower() if g["options"] else f"[{g['source']}]"
                 for g in gloss if not g["classifier"]]
        draft = " ".join(parts)
        draft = draft[:1].upper() + draft[1:]
        try:
            machine = self.models.translate(text, direction)
            error = None
        except Exception as exc:  # mô hình hỏng không được làm sập cả web
            machine, error = None, f"Không chạy được mô hình: {exc}"
        return {"direction": direction, "machine": machine, "machine_error": error,
                "model_available": self.models.available(direction), "draft": draft, "gloss": gloss,
                "entries": cards, "examples": self.corpus.similar(text, src)}


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status: int, body: bytes, kind: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def json(self, data: dict, status: int = 200) -> None:
            self.send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                self.send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/status":
                self.json(app.status())
            else:
                self.json({"error": "Không có trang này."}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if self.path != "/api/translate":
                return self.json({"error": "Không có trang này."}, HTTPStatus.NOT_FOUND)
            try:
                length = min(int(self.headers.get("Content-Length", 0)), 100_000)
                body = json.loads(self.rfile.read(length) or b"{}")
                text, direction = str(body.get("text", "")), body.get("direction", "vi2ede")
            except (ValueError, json.JSONDecodeError):
                return self.json({"error": "Dữ liệu gửi lên không hợp lệ."}, HTTPStatus.BAD_REQUEST)
            if direction not in DIRECTIONS:
                return self.json({"error": "Hướng dịch không hợp lệ."}, HTTPStatus.BAD_REQUEST)
            if not text.strip():
                return self.json({"error": "Hãy nhập nội dung cần dịch."}, HTTPStatus.BAD_REQUEST)
            self.json(app.translate(text, direction))

        def log_message(self, fmt: str, *args) -> None:
            pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    app = App()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(app))
    print(f"Mở http://{args.host}:{args.port} — Ctrl+C để dừng.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng.")


if __name__ == "__main__":
    main()
