#!/usr/bin/env python3
"""Chạy web Hriăm kèm mô hình dịch đã train, trên máy có mô hình.

    conda activate msa
    python scripts/serve_model.py                 # mở http://127.0.0.1:8000
    python scripts/serve_model.py --port 8080 --preload

Web (thư mục web/) tự nhận ra mô hình qua /api/health và hiện bản dịch máy cả câu.
Khi deploy web tĩnh (Vercel...) không có server này, web vẫn chạy như cũ: tra từ, ghép nghĩa, tìm câu.

Mô hình mỗi chiều lấy theo thứ tự: runs/<hướng>-noi/best (scripts/train_daily.py), rồi runs/<hướng>/best
(scripts/train.py). Hoặc chỉ định: --ede2vi <thư mục> --vi2ede <thư mục>.

API (để web khác gọi được, có bật CORS):
  GET  /api/health      -> {"models": {"ede2vi": true, "vi2ede": false}}
  POST /api/translate   {"text": "...", "direction": "ede2vi"} -> {"output": "...", "seconds": 0.8}
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DIRECTIONS = ("ede2vi", "vi2ede")
MAX_CHARS = 1000
MAX_LINES = 20

sys.path.insert(0, str(ROOT / "scripts"))


def find_model(direction: str, given: str | None) -> Path | None:
    candidates = [Path(given)] if given else [ROOT / "runs" / f"{direction}-noi" / "best",
                                              ROOT / "runs" / direction / "best"]
    return next((p for p in candidates if (p / "config.json").exists()), None)


class Models:
    """Nạp mô hình khi cần lần đầu; một khoá cho mỗi lần dịch vì GPU chỉ chạy một mô hình một lúc."""

    def __init__(self, paths: dict[str, Path | None], beams: int):
        self.paths, self.beams = paths, beams
        self.loaded: dict[str, object] = {}
        self.lock = threading.Lock()

    def available(self) -> dict[str, bool]:
        return {d: self.paths[d] is not None for d in DIRECTIONS}

    def translate(self, text: str, direction: str) -> str:
        with self.lock:
            if direction not in self.loaded:
                from translate import Translator
                print(f"Nạp mô hình {direction}: {self.paths[direction]}", flush=True)
                self.loaded[direction] = Translator(str(self.paths[direction]), direction, self.beams)
            lines = [line for line in text.splitlines() if line.strip()][:MAX_LINES]
            return "\n".join(self.loaded[direction](lines))


def make_handler(models: Models):
    class Handler(SimpleHTTPRequestHandler):
        def end_headers(self) -> None:
            if self.path.startswith("/api/"):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def send_json(self, data: dict, status: int = 200) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()

        def do_GET(self) -> None:
            if self.path.split("?")[0] == "/api/health":
                return self.send_json({"models": models.available()})
            super().do_GET()

        def do_POST(self) -> None:
            if self.path.split("?")[0] != "/api/translate":
                return self.send_json({"error": "Không có trang này."}, HTTPStatus.NOT_FOUND)
            try:
                length = min(int(self.headers.get("Content-Length", 0)), 20_000)
                body = json.loads(self.rfile.read(length) or b"{}")
                text, direction = str(body.get("text", ""))[:MAX_CHARS], body.get("direction")
            except (ValueError, json.JSONDecodeError):
                return self.send_json({"error": "Dữ liệu gửi lên không hợp lệ."}, HTTPStatus.BAD_REQUEST)
            if direction not in DIRECTIONS:
                return self.send_json({"error": "Hướng dịch không hợp lệ."}, HTTPStatus.BAD_REQUEST)
            if not models.available()[direction]:
                return self.send_json({"error": f"Chưa có mô hình {direction}."}, HTTPStatus.NOT_FOUND)
            if not text.strip():
                return self.send_json({"error": "Hãy nhập nội dung cần dịch."}, HTTPStatus.BAD_REQUEST)
            started = time.time()
            try:
                output = models.translate(text, direction)
            except Exception as exc:  # lỗi mô hình không được làm sập server
                return self.send_json({"error": f"Mô hình lỗi: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send_json({"output": output, "direction": direction, "seconds": round(time.time() - started, 2)})

        def log_message(self, fmt: str, *args) -> None:
            if self.path.startswith("/api/translate"):
                super().log_message(fmt, *args)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 để máy khác trong mạng truy cập")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--ede2vi", help="thư mục mô hình Ê Đê → Việt")
    parser.add_argument("--vi2ede", help="thư mục mô hình Việt → Ê Đê")
    parser.add_argument("--beams", type=int, default=4)
    parser.add_argument("--preload", action="store_true", help="nạp mô hình ngay khi khởi động")
    args = parser.parse_args()

    paths = {d: find_model(d, getattr(args, d)) for d in DIRECTIONS}
    for d, p in paths.items():
        print(f"{d}: {p.relative_to(ROOT) if p and p.is_relative_to(ROOT) else p or 'chưa có mô hình'}", flush=True)
    if not any(paths.values()):
        sys.exit("LỖI: không thấy mô hình nào trong runs/. Hãy train trước: python scripts/train_daily.py ede2vi")
    if not (WEB / "data" / "dictionary.json").exists():
        sys.exit("LỖI: thiếu web/data. Hãy chạy: python scripts/export_web_data.py")
    models = Models(paths, args.beams)
    if args.preload:
        for d, p in paths.items():
            if p:
                models.translate("a", d)
    server = ThreadingHTTPServer((args.host, args.port), partial(make_handler(models), directory=str(WEB)))
    print(f"Mở http://{args.host}:{args.port} — Ctrl+C để dừng.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng.")


if __name__ == "__main__":
    main()
