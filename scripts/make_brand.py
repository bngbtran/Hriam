#!/usr/bin/env python3
"""Sinh bộ nhận diện Hriăm (web/assets/brand/*.svg) theo lối dệt thổ cẩm Ê Đê.

    python scripts/make_brand.py

Thổ cẩm được dệt trên lưới sợi, nên mọi hình đều là bậc thang. Mỗi hoạ tiết dưới đây là một
"bản vẽ" theo ô lưới; sửa bản vẽ rồi chạy lại để đổi nhận diện. Căn cứ: docs/BRAND.md.

Ký hiệu màu:
  .  chàm đen (nền)   i  chàm   r  đỏ   y  vàng nghệ   w  trắng sợi bông   b  xanh   (cách) trong suốt
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "assets" / "brand"
FONT_DIR = ROOT / "scripts" / ".fonts"      # phông tải về để đổi chữ trong logo thành nét vẽ, không đưa lên git
FONTS = {
    "display": "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts/NotoSerifDisplay/hinted/ttf/NotoSerifDisplay-SemiBold.ttf",
    "sans": "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts/NotoSans/hinted/ttf/NotoSans-SemiBold.ttf",
}
TAGLINE = "DỊCH VIỆT – Ê ĐÊ"
PALETTE = {
    ".": ("Chàm đen", "#161722"),
    "i": ("Chàm", "#2A3566"),
    "r": ("Đỏ", "#A8281E"),
    "y": ("Vàng nghệ", "#E2A72E"),
    "w": ("Trắng sợi bông", "#F3EDE1"),
    "b": ("Xanh", "#3D5A9E"),
}
COLORS = {k: v[1] for k, v in PALETTE.items()}

# Chữ H dệt: hai dải sọc đỏ viền trắng, giữa là quả trám.
MARK = """
...............
.wrw.......wrw.
.wrw.......wrw.
.wrw.......wrw.
.wrw...y...wrw.
.wrw..yry..wrw.
.wrw.yrwry.wrw.
.wrwyrw.wrywrw.
.wrw.yrwry.wrw.
.wrw..yry..wrw.
.wrw...y...wrw.
.wrw.......wrw.
.wrw.......wrw.
.wrw.......wrw.
...............
"""

# Hoạ tiết có trong tư liệu về thổ cẩm Ê Đê (xem docs/BRAND.md). Hình là cách điệu, không chép mẫu cụ thể.
MOTIFS = {
    "qua-tram": ("Quả trám", """
...y...
..yry..
.yrwry.
yrw.wry
.yrwry.
..yry..
...y...
"""),
    "rua": ("Rùa", """
.....y.....
....yyy....
.y..yry..y.
.yy.rrr.yy.
..yrrwrry..
...rwywr...
..yrrwrry..
.yy.rrr.yy.
.y..yry..y.
....yyy....
.....y.....
"""),
    "than-lan": ("Thằn lằn", """
....w....
...www...
w...w...w
.w..w..w.
..wwwww..
....w....
....w....
..wwwww..
.w..w..w.
w...w...w
....w....
...w.....
..w......
"""),
    "chuon-chuon": ("Chuồn chuồn", """
.....r.....
....rrr....
yyy..r..yyy
.yyyyryyyy.
yyy..r..yyy
.....r.....
.....r.....
.....r.....
.....r.....
"""),
    "rang-cua": ("Răng cưa", """
r.....r.....
.r...r.r...r
..r.r...r.r.
...r.....r..
"""),
}


def grid(art: str, fill: str = ".") -> list[str]:
    rows = art.strip("\n").splitlines()
    width = max(len(r) for r in rows)
    return [r.ljust(width, fill) for r in rows]


def rects(rows: list[str], unit: float, ox: float = 0, oy: float = 0) -> str:
    """Gộp các ô cùng màu liền nhau trên một hàng thành một hình chữ nhật cho file gọn."""
    out = []
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            ch, end = row[x], x
            while end < len(row) and row[end] == ch:
                end += 1
            if ch in COLORS:
                out.append(f'<rect x="{ox + x * unit:g}" y="{oy + y * unit:g}" width="{(end - x) * unit:g}" '
                           f'height="{unit:g}" fill="{COLORS[ch]}"/>')
            x = end
    return "".join(out)


def svg(width: float, height: float, body: str, label: str | None = None) -> str:
    aria = f' role="img" aria-label="{label}"' if label else ' aria-hidden="true"'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" '
            f'viewBox="0 0 {width:g} {height:g}" shape-rendering="crispEdges"{aria}>{body}</svg>\n')


def paste(canvas: list[list[str]], art: list[str], x: int, y: int) -> None:
    for dy, row in enumerate(art):
        for dx, ch in enumerate(row):
            if ch != " ":
                canvas[y + dy][x + dx] = ch


def hem() -> list[str]:
    """Dải gấu váy: sọc đỏ, hàng chấm trắng, rùa xen quả trám, sọc vàng, răng cưa, sọc đỏ."""
    width = 24
    rows: list[str] = ["r" * width, "r" * width, "." * width, ("w." * width)[:width], "." * width]
    band = [["."] * width for _ in range(13)]
    paste(band, grid(MOTIFS["rua"][1]), 0, 1)
    paste(band, grid(MOTIFS["qua-tram"][1]), 14, 3)
    rows += ["".join(r) for r in band]
    rows += ["." * width, "y" * width, "." * width]
    zig = grid(MOTIFS["rang-cua"][1])
    rows += [(r * 2)[:width] for r in zig]
    rows += ["." * width, "r" * width, "r" * width]
    return rows


def stripe() -> list[str]:
    """Sọc ngang như phần giữa thân áo nam: đỏ đậm, xen chỉ trắng, vàng, xanh."""
    return ["r", "r", "r", "w", "r", "r", "y", ".", "b", ".", "y", "r", "r", "w", "r", "r", "r"]


def texture() -> str:
    """Lưới chéo rất mờ cho nền chàm, gợi các đường chéo trên váy."""
    size, unit, cells = 48, 2, []
    for y in range(0, size, unit):
        for x in range(0, size, unit):
            i, j = x // unit, y // unit
            if (i + j) % 12 == 0 or (i - j) % 12 == 0:
                cells.append(f'<rect x="{x}" y="{y}" width="{unit}" height="{unit}"/>')
    return svg(size, size, f'<g fill="#F3EDE1" fill-opacity="0.05">{"".join(cells)}</g>')


def mark_body(unit: float = 4) -> tuple[str, float]:
    rows = grid(MARK)
    side = len(rows) * unit
    body = (f'<rect width="{side:g}" height="{side:g}" rx="{side * 0.2:g}" fill="{COLORS["."]}"/>'
            + rects(rows, unit))
    return body, side


def font_file(kind: str) -> Path:
    path = FONT_DIR / Path(FONTS[kind]).name
    if not path.exists():
        FONT_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Tải phông {path.name}…")
        urllib.request.urlretrieve(FONTS[kind], path)
    return path


def text_path(kind: str, text: str, size: float, x: float, baseline: float, tracking: float = 0) -> tuple[str, float]:
    """Đổi chữ thành nét vẽ SVG để logo hiển thị giống nhau ở mọi nơi, kể cả khi chèn bằng <img>."""
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont
    font = TTFont(font_file(kind))
    glyphs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font["hmtx"]
    scale = size / font["head"].unitsPerEm
    parts, cursor = [], x
    for ch in text:
        name = cmap.get(ord(ch), ".notdef")
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, cursor, baseline)))
        parts.append(pen.getCommands())
        cursor += hmtx[name][0] * scale + tracking
    return " ".join(p for p in parts if p), cursor - tracking


def logo(text_color: str, sub_color: str) -> tuple[str, float]:
    body, side = mark_body()
    scale = 64 / side
    name, end1 = text_path("display", "Hriăm", 36, 80, 40, -0.5)
    tag, end2 = text_path("sans", TAGLINE, 10.5, 82, 58, 2.2)
    width = round(max(end1, end2) + 4)
    return (f'<g transform="scale({scale:g})">{body}</g>'
            f'<path d="{name}" fill="{text_color}"/><path d="{tag}" fill="{sub_color}"/>'), width


def icon(art: str) -> str:
    """Hoạ tiết trên nền trong suốt cho nền sáng: sợi trắng đổi thành chàm để còn thấy."""
    rows = [r.replace(".", " ").replace("w", ".") for r in grid(art)]
    return svg(len(rows[0]) * 4, len(rows) * 4, rects(rows, 4))


def colors_css() -> str:
    names = {".": "cham", "i": "cham-xanh", "r": "do", "y": "vang", "w": "nga", "b": "xanh"}
    lines = [f"  --{names[k]}: {hexcode};  /* {label} */" for k, (label, hexcode) in PALETTE.items()]
    return ("/* Bảng màu Hriăm, sinh bởi scripts/make_brand.py. Không sửa tay: sửa PALETTE trong script. */\n"
            ":root {\n" + "\n".join(lines) + "\n}\n")


def og_image(path: Path) -> None:
    """Ảnh xem trước khi chia sẻ link (1200 × 630): nền chàm, biểu tượng, tên, dải gấu váy."""
    from PIL import Image, ImageDraw, ImageFont

    def rgb(ch: str) -> tuple[int, int, int]:
        h = COLORS[ch].lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    def paint(draw, rows, unit, ox, oy):
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch in COLORS:
                    draw.rectangle([ox + x * unit, oy + y * unit, ox + (x + 1) * unit - 1, oy + (y + 1) * unit - 1],
                                   fill=rgb(ch))

    w, h = 1200, 630
    im = Image.new("RGB", (w, h), rgb("."))
    draw = ImageDraw.Draw(im)
    texture_color = tuple(round(a * 0.95 + b * 0.05) for a, b in zip(rgb("."), rgb("w")))
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            i, j = x // 4, y // 4
            if (i + j) % 12 == 0 or (i - j) % 12 == 0:
                draw.rectangle([x, y, x + 3, y + 3], fill=texture_color)
    hem_rows = hem()
    unit = 5
    band = len(hem_rows) * unit
    for ox in range(0, w, len(hem_rows[0]) * unit):
        paint(draw, hem_rows, unit, ox, h - band)
    mark = grid(MARK)
    paint(draw, mark, 14, 96, 120)
    display = ImageFont.truetype(str(font_file("display")), 132)
    sans = ImageFont.truetype(str(font_file("sans")), 30)
    draw.text((340, 118), "Hriăm", font=display, fill=rgb("w"))
    x = 346
    for ch in TAGLINE:
        draw.text((x, 300), ch, font=sans, fill=rgb("y"))
        x += draw.textlength(ch, font=sans) + 6
    body = ImageFont.truetype(str(font_file("sans")), 34)
    draw.text((96, 380), "Tra từ điển và tìm câu song ngữ Việt – Ê Đê", font=body, fill=rgb("w"))
    im.save(path, optimize=True)


def write(name: str, content: str) -> None:
    (OUT / name).write_text(content, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in ("pattern.svg", "thin.svg"):
        (OUT / old).unlink(missing_ok=True)

    body, side = mark_body()
    write("mark.svg", svg(side, side, body, "Hriăm"))
    write("favicon.svg", svg(side, side, body, "Hriăm"))
    for name, colors in (("logo.svg", (COLORS["."], COLORS["r"])), ("logo-dark.svg", (COLORS["w"], COLORS["y"]))):
        body_logo, width = logo(*colors)
        write(name, svg(width, 64, body_logo, "Hriăm – Dịch Việt – Ê Đê"))
    write("colors.css", colors_css())

    rows = hem()
    write("hem.svg", svg(len(rows[0]) * 3, len(rows) * 3, rects(rows, 3)))
    rows = [c * 8 for c in stripe()]
    write("stripe.svg", svg(len(rows[0]), len(rows), rects(rows, 1)))
    write("texture.svg", texture())

    for key, (_, art) in MOTIFS.items():
        rows = grid(art)
        pad = 1
        w, h = (len(rows[0]) + 2 * pad) * 4, (len(rows) + 2 * pad) * 4
        bg = f'<rect width="{w}" height="{h}" fill="{COLORS["."]}"/>'
        write(f"motif-{key}.svg", svg(w, h, bg + rects(rows, 4, pad * 4, pad * 4), MOTIFS[key][0]))
        write(f"icon-{key}.svg", icon(art))
    og_image(OUT / "og.png")

    for path in sorted(p for p in OUT.iterdir() if p.suffix in {".svg", ".css", ".png"}):
        print(f"{path.name:24s} {path.stat().st_size:6d} byte")


if __name__ == "__main__":
    main()
