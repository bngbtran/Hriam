#!/usr/bin/env python3
"""Cào Kinh Thánh hai bản Việt và Ê Đê từ kinhthanh.httlvn.org. Bước ghép câu nằm ở realign.py.

    python scripts/bible_scraper.py inspect --book sa --chapter 1
    python scripts/bible_scraper.py crawl [--limit N]

Xem docs/HUONG_DAN.md để biết chi tiết.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message="urllib3 v2")
import requests  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from bs4.element import Tag  # noqa: E402

BASE_URL = "https://kinhthanh.httlvn.org"
VERSIONS = {"ede": "RRB", "vi": "VI1934"}
DELAY = 1.5  # giây giữa hai lần tải, để không làm quá tải server
MAX_RETRIES = 5
TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (compatible; NLP-course-research-crawler)"

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "raw" / "bible_html"
DATA_DIR = ROOT / "data" / "interim"

# Thứ tự chuẩn của 66 sách, dùng để gán mã USFM cho mã sách của trang.
USFM_BOOKS = """GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA
PRO ECC SNG ISA JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL
MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM HEB JAS
1PE 2PE 1JN 2JN 3JN JUD REV""".split()

SELAH_RE = re.compile(r"\(\s*S[êe]\s*-?\s*la\s*\)", re.IGNORECASE)
NUMBER_RE = re.compile(r"\d+")

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT
_last_fetch = 0.0


# ---------------------------------------------------------------- tải trang
def active_version(soup: BeautifulSoup) -> str | None:
    """Mã bản mà trang thực sự hiển thị (mục đang bị disable trong menu chọn bản)."""
    for item in soup.select("li.disabled, li.dropdown-item.disabled"):
        bold = item.find("b")
        if bold:
            return bold.get_text(strip=True).strip("()")
    return None


def fetch(url: str) -> str:
    global _last_fetch
    for attempt in range(1, MAX_RETRIES + 1):
        wait = DELAY - (time.time() - _last_fetch)
        if wait > 0:
            time.sleep(wait)
        _last_fetch = time.time()
        try:
            resp = session.get(url, timeout=TIMEOUT)
            if resp.status_code == 200:
                resp.encoding = "utf-8"
                return resp.text
            error = f"HTTP {resp.status_code}"
            if resp.status_code in (400, 401, 403, 404):
                raise RuntimeError(f"{error} tại {url}")
        except requests.RequestException as exc:
            error = str(exc)
        backoff = DELAY * 2**attempt
        print(f"  ! lỗi ({error}), thử lại sau {backoff:.0f}s [{attempt}/{MAX_RETRIES}]", flush=True)
        time.sleep(backoff)
    raise RuntimeError(f"Không tải được {url} sau {MAX_RETRIES} lần thử")


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def get_page(url: str, cache_path: Path, version: str, need_verses: bool) -> str:
    """Trả về HTML từ cache, hoặc tải mới. Chỉ lưu cache khi trang hợp lệ."""
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")
    html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")
    shown = active_version(soup)
    if shown != version:
        raise RuntimeError(f"Trang trả về bản {shown!r} thay vì {version!r}: {url}")
    if need_verses and not soup.select(".bible-read span.verse"):
        raise RuntimeError(f"Trang không có câu nào, có thể HTML đã đổi: {url}")
    write_atomic(cache_path, html)
    return html


def book_index(version: str) -> dict[str, list[int]]:
    """{mã sách: [các chương]}, giữ đúng thứ tự trên trang. Bỏ chương 0 (lời giới thiệu)."""
    html = get_page(f"{BASE_URL}/?v={version}", CACHE_DIR / version / "_index.html", version, False)
    soup = BeautifulSoup(html, "html.parser")
    books: dict[str, set[int]] = {}
    for link in soup.select('a[href*="/doc-kinh-thanh/"]'):
        match = re.match(r"(?:https?://[^/]+)?/doc-kinh-thanh/([^/?]+)/(\d+)", link["href"])
        if match and int(match[2]) > 0:
            books.setdefault(match[1], set()).add(int(match[2]))
    return {book: sorted(chapters) for book, chapters in books.items()}


def book_mapping(books: dict[str, list[int]]) -> dict[str, str]:
    if len(books) != len(USFM_BOOKS):
        print(f"CẢNH BÁO: dò được {len(books)} sách (kỳ vọng {len(USFM_BOOKS)})", file=sys.stderr)
    return dict(zip(books, USFM_BOOKS))


# ------------------------------------------------------------- tách câu
def is_verse_marker(tag: Tag) -> bool:
    """<sup> chứa số câu, ví dụ <sup>4</sup> hoặc <sup>4-5</sup>."""
    return tag.name == "sup" and bool(NUMBER_RE.search(tag.get_text()))


def clean_text(text: str) -> str:
    text = SELAH_RE.sub(" ", text)
    text = text.replace("⚓", " ").replace(" ", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return unicodedata.normalize("NFC", text)


def parse_chapter(html: str, book: str, chapter: int) -> list[dict]:
    """Danh sách câu {start, end, text}. Các span cùng số câu được nối lại."""
    soup = BeautifulSoup(html, "html.parser")
    class_re = re.compile(rf"^{re.escape(book)}_{chapter}_(\d+)$")
    verses: list[dict] = []
    for span in soup.select(".bible-read span.verse"):
        for anchor in span.find_all("a"):
            anchor.decompose()
        start = end = None
        for sup in span.find_all("sup"):
            if is_verse_marker(sup) and start is None:
                numbers = [int(n) for n in NUMBER_RE.findall(sup.get_text())]
                start, end = numbers[0], numbers[-1]
            sup.decompose()
        if start is None:  # đoạn nối tiếp câu trước: lấy số câu từ class
            for cls in span.get("class", []):
                match = class_re.match(cls)
                if match:
                    start = end = int(match[1])
        if start is None:
            continue
        for br in span.find_all("br"):
            br.replace_with(" ")
        text = clean_text(span.get_text())
        if verses and verses[-1]["start"] <= start <= verses[-1]["end"]:
            verses[-1]["text"] = f'{verses[-1]["text"]} {text}'.strip()
            verses[-1]["end"] = max(verses[-1]["end"], end)
        else:
            verses.append({"start": start, "end": end, "text": text})
    return verses


# ------------------------------------------------------------------ lệnh
def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")


def cmd_crawl(args) -> None:
    all_books: dict[str, str] = {}
    for lang, version in VERSIONS.items():
        books = book_index(version)
        mapping = book_mapping(books)
        all_books = all_books or mapping
        if mapping != all_books:
            print(f"CẢNH BÁO: danh sách sách của {version} khác bản đầu tiên", file=sys.stderr)
        jobs = [(b, c) for b, chapters in books.items() for c in chapters]
        if args.limit:
            jobs = jobs[: args.limit]
        print(f"[{version}] {len(books)} sách, {len(jobs)} chương", flush=True)
        rows: list[dict] = []
        for i, (book, chapter) in enumerate(jobs, 1):
            cache_path = CACHE_DIR / version / book / f"{chapter}.html"
            url = f"{BASE_URL}/doc-kinh-thanh/{book}/{chapter}?v={version}"
            html = get_page(url, cache_path, version, True)
            for verse in parse_chapter(html, book, chapter):
                rows.append({"book": mapping[book], "chapter": chapter, **verse})
            if i % 25 == 0 or i == len(jobs):
                print(f"  {version}: {i}/{len(jobs)} ({book} {chapter})", flush=True)
        write_jsonl(DATA_DIR / f"{lang}.jsonl", rows)
        print(f"[{version}] {len(rows)} câu -> data/interim/{lang}.jsonl", flush=True)
    write_atomic(DATA_DIR / "books.json", json.dumps(all_books, ensure_ascii=False, indent=2) + "\n")
    print("Xong.", flush=True)


def cmd_inspect(args) -> None:
    for lang, version in VERSIONS.items():
        cache_path = CACHE_DIR / version / args.book / f"{args.chapter}.html"
        url = f"{BASE_URL}/doc-kinh-thanh/{args.book}/{args.chapter}?v={version}"
        verses = parse_chapter(get_page(url, cache_path, version, True), args.book, args.chapter)
        print(f"--- {version}: {len(verses)} câu")
        for verse in verses[: args.show]:
            print(f'{verse["start"]}-{verse["end"]}: {verse["text"]}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    crawl = sub.add_parser("crawl", help="tải và tách câu")
    crawl.add_argument("--limit", type=int, help="chỉ cào N chương đầu mỗi bản")
    crawl.set_defaults(func=cmd_crawl)
    inspect = sub.add_parser("inspect", help="xem thử cách tách câu của một chương")
    inspect.add_argument("--book", required=True)
    inspect.add_argument("--chapter", type=int, required=True)
    inspect.add_argument("--show", type=int, default=5)
    inspect.set_defaults(func=cmd_inspect)
    args = parser.parse_args()
    try:
        args.func(args)
    except RuntimeError as exc:
        sys.exit(f"LỖI: {exc}\nChạy lại đúng lệnh này để tiếp tục từ chỗ dừng.")


if __name__ == "__main__":
    main()
