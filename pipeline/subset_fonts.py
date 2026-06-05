#!/usr/bin/env python3
"""
subset_fonts.py — shrink the self-hosted fonts to only the glyphs the site uses.

Reads the rendered glyphs from site/ (build the site first), subsets the FULL
fonts in assets/fonts-full/ down to just those glyphs — keeping ALL OpenType
layout features so Devanagari conjuncts still shape correctly — and writes the
smaller woff2 into assets/fonts/ (which build_site.py copies into the site).

The subset is therefore coupled to the current content. After adding works that
introduce new glyphs, re-run:
    python3 pipeline/build_site.py        # render current content
    python3 pipeline/subset_fonts.py      # re-subset to it
    python3 pipeline/build_site.py        # rebuild with the smaller fonts

Needs (local only, NOT needed in CI): pip install fonttools brotli
"""
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
FULL = ROOT / "assets" / "fonts-full"      # full source fonts
OUT = ROOT / "assets" / "fonts"            # subset output (used by build_site)


def used_chars() -> set:
    files = list(SITE.glob("**/*.html"))
    if not files:
        sys.exit("site/ has no HTML — run `python3 pipeline/build_site.py` first.")
    chars = set()
    for f in files:
        t = f.read_text(encoding="utf-8")
        t = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
        t = re.sub(r"<[^>]+>", " ", t)              # strip tags
        t = re.sub(r"&[a-z]+;|&#\d+;", " ", t)      # strip entities
        chars |= set(t)
    chars |= {"‌", "‍", " "}          # ZWNJ, ZWJ, nbsp
    return {c for c in chars if ord(c) >= 0x20}


def main():
    if not FULL.exists():
        sys.exit(f"missing {FULL} — the full source fonts.")
    chars = "".join(sorted(used_chars()))
    tmp = ROOT / ".used_glyphs.tmp"
    tmp.write_text(chars, encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    tb = ta = 0
    for src in sorted(FULL.glob("*.woff2")):
        dst = OUT / src.name
        subprocess.run(
            ["pyftsubset", str(src), f"--output-file={dst}", "--flavor=woff2",
             f"--text-file={tmp}", "--layout-features=*", "--unicodes=U+200C-200D"],
            check=True)
        b, a = src.stat().st_size, dst.stat().st_size
        tb += b; ta += a
        print(f"  {src.name}: {b//1024} KB -> {a//1024} KB")
    tmp.unlink()
    print(f"  total {tb//1024} KB -> {ta//1024} KB "
          f"({(1-ta/tb)*100:.0f}% smaller) over {len(chars)} glyphs")


if __name__ == "__main__":
    main()
