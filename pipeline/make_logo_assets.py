#!/usr/bin/env python3
"""Regenerate the derived logo assets in assets/logo/ from the designer sources.

Sources (drop-in, two inks on transparency: near-black #1e1e1e + gold #a67c2d):
    final-logo.png              the न mark (header brand, light mode)
    logo-pressed.png            the mark, pressed/hover frame
    homepage-button*.png        designer wordmark exports (kept, currently unused —
                                the header renders the site name as live text)

Derived (what this script writes):
    favicon-48.png / favicon-180.png   mark centred on an opaque light square
    final-logo-dark.png / logo-pressed-dark.png   mark recolored to the dark
                                       theme palette (fg #e7e3da, accent #e0b65f)

Local-only (needs PIL, like subset_fonts.py — not run in CI; build_site.py just
copies the pre-built files). Rerun after replacing any source PNG.
"""
from pathlib import Path

from PIL import Image

LOGO = Path(__file__).resolve().parent.parent / "assets" / "logo"

LIGHT_BG = (251, 250, 247, 255)   # site --bg (light)
DARK_INK = (231, 227, 218)        # site --fg (dark)
DARK_GOLD = (224, 182, 95)        # site --accent (dark)
SRC_GOLD = (166, 124, 45)
SRC_INK = (25, 25, 25)


def dist(c, ref):
    return sum((a - b) ** 2 for a, b in zip(c, ref))


def recolor_dark(src_name, dst_name):
    src = Image.open(LOGO / src_name).convert("RGBA")
    out = Image.new("RGBA", src.size)
    for y in range(src.height):
        for x in range(src.width):
            r, g, b, a = src.getpixel((x, y))
            if a == 0:
                continue
            ink = DARK_GOLD if dist((r, g, b), SRC_GOLD) < dist((r, g, b), SRC_INK) else DARK_INK
            out.putpixel((x, y), (*ink, a))
    out.save(LOGO / dst_name)
    print("wrote", dst_name)


def favicon(size, dst_name):
    mark = Image.open(LOGO / "final-logo.png").convert("RGBA")
    pad = round(size * 0.12)
    box = size - 2 * pad
    scale = box / max(mark.size)
    m = mark.resize((round(mark.width * scale), round(mark.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), LIGHT_BG)
    canvas.paste(m, ((size - m.width) // 2, (size - m.height) // 2), m)
    canvas.convert("RGB").save(LOGO / dst_name)
    print("wrote", dst_name)


if __name__ == "__main__":
    recolor_dark("final-logo.png", "final-logo-dark.png")
    recolor_dark("logo-pressed.png", "logo-pressed-dark.png")
    favicon(48, "favicon-48.png")
    favicon(180, "favicon-180.png")
