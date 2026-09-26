"""Generates app icons and the default link-preview image.
Run: pipeline/.venv/bin/python tools/make_icons.py   (needs pillow, fonttools)"""
from __future__ import annotations

import io
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
BOARD, FLAP_HI, FLAP, AMBER, INK, DIM, SKY = "#121720", "#262e3d", "#1c2330", "#ffb547", "#f4f0e6", "#8d97a8", "#ecf0f5"


# Full TTFs (SIL OFL 1.1) — the web subsets are split into latin/latin-ext, Pillow needs one file with Polish glyphs.
DISPLAY = (ROOT / "tools" / "fonts" / "BigShoulders.ttf").read_bytes()
TEXT = (ROOT / "tools" / "fonts" / "Figtree.ttf").read_bytes()


def font(data: bytes, size: int, weight: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(io.BytesIO(data), size)
    try:
        f.set_variation_by_axes([weight])
    except OSError:
        pass
    return f


def tile(draw: ImageDraw.ImageDraw, box, ch: str, size: int, color: str, radius: int) -> None:
    x0, y0, x1, y1 = box
    mid = (y0 + y1) // 2
    draw.rounded_rectangle(box, radius=radius, fill=FLAP)
    draw.rounded_rectangle((x0, y0, x1, mid), radius=radius, fill=FLAP_HI, corners=(True, True, False, False))
    f = font(DISPLAY, size, 900)
    draw.text(((x0 + x1) / 2, (y0 + y1) / 2 + size * 0.02), ch, font=f, fill=color, anchor="mm")
    draw.line((x0, mid, x1, mid), fill="#05070a", width=max(2, int((y1 - y0) // 60)))


def app_icon(px: int, maskable: bool = False) -> Image.Image:
    img = Image.new("RGB", (px, px), BOARD)
    d = ImageDraw.Draw(img)
    pad = px * (0.24 if maskable else 0.17)
    w = px - 2 * pad
    h = w * 1.18
    x0, y0 = pad, (px - h) / 2
    tile(d, (x0, y0, x0 + w, y0 + h), "W", int(h * 0.86), AMBER, int(px * 0.05))
    return img


def og_image() -> Image.Image:
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), BOARD)
    d = ImageDraw.Draw(img)
    word = "WYPAD"
    tw, th, gap = 150, 200, 14
    x = (W - (len(word) * tw + (len(word) - 1) * gap)) / 2
    for i, ch in enumerate(word):
        tile(d, (x + i * (tw + gap), 150, x + i * (tw + gap) + tw, 150 + th), ch, 176, AMBER if i == 0 else INK, 12)
    d.text((W / 2, 440), "Tanie city breaki z Poznania i okolic", font=font(TEXT, 44, 700), fill=INK, anchor="mm")
    d.text((W / 2, 500), "Lot, bagaż i nocleg dla 2 osób w jednej cenie. Codziennie rano.", font=font(TEXT, 30, 500), fill=DIM, anchor="mm")
    return img


def svg_icon() -> str:
    f = TTFont(io.BytesIO(DISPLAY))
    gs = f.getGlyphSet(location={"wght": 900})
    name = f.getBestCmap()[ord("W")]
    pen = SVGPathPen(gs)
    gs[name].draw(pen)
    bp = BoundsPen(gs)
    gs[name].draw(bp)
    xmin, ymin, xmax, ymax = bp.bounds
    gw, gh = xmax - xmin, ymax - ymin
    s = 40 / gh
    tx = 32 - (xmin + gw / 2) * s
    ty = 32 + (ymin + gh / 2) * s
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            f'<rect width="64" height="64" rx="12" fill="{BOARD}"/>'
            f'<rect x="10" y="6" width="44" height="52" rx="5" fill="{FLAP}"/>'
            f'<path d="M15 6h34a5 5 0 0 1 5 5v21H10V11a5 5 0 0 1 5-5z" fill="{FLAP_HI}"/>'
            f'<path transform="translate({tx:.2f} {ty:.2f}) scale({s:.5f} {-s:.5f})" fill="{AMBER}" d="{pen.getCommands()}"/>'
            f'<rect x="10" y="31.5" width="44" height="1.5" fill="#05070a"/></svg>\n')


if __name__ == "__main__":
    icons = SITE / "icons"
    app_icon(192).save(icons / "icon-192.png", optimize=True)
    app_icon(512).save(icons / "icon-512.png", optimize=True)
    app_icon(512, maskable=True).save(icons / "icon-maskable-512.png", optimize=True)
    app_icon(180).save(icons / "apple-touch-icon.png", optimize=True)
    og_image().save(icons / "og-default.png", optimize=True)
    (icons / "icon.svg").write_text(svg_icon())
    print("icons written to", icons)
