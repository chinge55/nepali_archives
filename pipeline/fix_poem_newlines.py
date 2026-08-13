#!/usr/bin/env python3
"""
fix_poem_newlines.py — re-extract Kavita Kosh works from their preserved source
HTML with correct verse line-breaking.

The first pass converted each <br> to "\n" *and* kept the literal newline that
follows it in the page source, doubling every line break: every verse line ended
up blank-line-separated and stanza breaks were indistinguishable from line
breaks. This re-extracts from each work's extracted/*.html, collapsing "<br> +
trailing whitespace" into a single newline, so:
  single "\n"  = verse line within a stanza
  blank line   = stanza break
Text is still preserved verbatim (proofread stays false).
"""
import json, re, sys
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DEVK = ROOT / "archives/authors/devkota"
KK = Path("/tmp/kk")

def clean_poem_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    c = soup.select_one("#mw-content-text") or soup
    parts = []
    for el in c.select("div.poem"):
        s = re.sub(r'<br\s*/?>\s*', '\n', str(el))   # br + trailing whitespace -> ONE newline
        txt = BeautifulSoup(s, "lxml").get_text()
        lines = [re.sub(r'[ \t ​]+', ' ', ln).strip() for ln in txt.split('\n')]
        block = re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()
        if block:
            parts.append(block)
    return '\n\n'.join(parts).strip()

CANTO = ["प्रथम","द्वितीय","तृतीय","चतुर्थ","पञ्चम","षष्ठम","सप्तम","अष्टम","नवम",
         "दशम","एकादश","द्वादश","त्रयोदश","चतुर्दश","पञ्चदश","षोडश","सप्तदश",
         "अष्टदश","एकोनविस","विंस","एकविंस"]

def reextract(d: Path) -> int:
    """Returns new char count, or -1 if skipped."""
    meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
    if "Kavita Kosh" not in (meta.get("source", {}).get("name") or ""):
        return -1

    if d.name == "munamadan":
        order = json.load(open(KK / "containers.json"))["मुना मदन"]
        leaves = json.load(open(KK / "leaves.json"))
        secs = []
        for i, u in enumerate(order, 1):
            f = d / "extracted" / f"section_{i:02d}.html"
            if not f.exists():
                continue
            title = re.sub(r"\s*/\s*मुना मदन\s*$", "",
                           leaves[u]["title"].replace(" / लक्ष्मीप्रसाद देवकोटा", "")).strip().strip("‘’\"")
            secs.append(f"{title}\n\n{clean_poem_text(f.read_text(encoding='utf-8',errors='replace'))}")
        text = "\n\n\n".join(secs)
    elif d.name == "prithviraj_chauhan":
        secs = []
        for i in range(1, 22):
            f = d / "extracted" / f"canto_{i:02d}.html"
            if not f.exists():
                continue
            secs.append(f"{CANTO[i-1]} सर्ग\n\n{clean_poem_text(f.read_text(encoding='utf-8',errors='replace'))}")
        text = "\n\n\n".join(secs)
    else:
        f = d / "extracted" / "index.html"
        if not f.exists():
            return -1
        text = clean_poem_text(f.read_text(encoding="utf-8", errors="replace"))

    (d / "text.txt").write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    return len(re.findall(r"[ऀ-ॿ]", text))

def main():
    fixed = skipped = 0
    for d in sorted(DEVK.iterdir()):
        if not d.is_dir():
            continue
        n = reextract(d)
        if n < 0:
            skipped += 1
        else:
            fixed += 1
    print(f"re-extracted {fixed} Kavita Kosh works; skipped {skipped} (non-KK)")

if __name__ == "__main__":
    sys.exit(main())
