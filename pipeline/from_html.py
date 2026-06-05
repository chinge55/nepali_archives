#!/usr/bin/env python3
"""
from_html.py — Stage 1 (web sources): scraped HTML -> text.txt

For born-digital works captured as an HTML page (e.g. a blog/anthology post),
this isolates the article body, strips site chrome (nav, sidebars, share/like
widgets, related posts, comments), and writes clean text.txt preserving
paragraph and chapter structure. No OCR; the text is already Unicode.

Needs BeautifulSoup: `pip install beautifulsoup4 lxml` (in conda env archive_env).

Usage:
    python3 pipeline/from_html.py archives/authors/devkota/champa
    python3 pipeline/from_html.py archives/authors/devkota/champa --preview
    python3 pipeline/from_html.py --all          # every work whose source has html

The source HTML path is read from metadata.json -> source.html. The article
container is auto-detected (.entry-content / <article> / .post-content /
<main>); override with --selector if a site needs it.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_ROOT = REPO_ROOT / "archives"

# Preferred article containers, best first.
CONTENT_SELECTORS = [".entry-content", "article", ".post-content",
                     ".td-post-content", "main"]

# Elements / regions that are site chrome, not the work.
JUNK_SELECTORS = [
    "script", "style", "noscript", "nav", "header", "footer", "form",
    ".sharedaddy", ".jp-relatedposts", "#jp-post-flair", ".sd-block",
    ".sd-sharing", ".robots-nocontent", ".entry-utility", ".entry-meta",
    ".comments", "#comments", ".comment-respond", ".wp-block-buttons",
    ".addtoany_share_save_container", ".post-navigation",
]

# Block tags whose text becomes its own paragraph. <br> inside is kept as a
# line break (matters for verse embedded in prose).
BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "blockquote", "p", "li", "pre"]

# Boilerplate lines to drop even if they survive container selection.
BOILERPLATE_RE = re.compile(
    r"^(share this|like this|loading|advertisement|continue reading|"
    r"leave a (reply|comment)|related posts?|प्रतिक्रिया|सेयर|"
    r"read .* in pdf|please let us know|click here to|"
    r"नेपाली साहित्य लेखन सहयोगी)\b", re.IGNORECASE)


def block_text(el) -> str:
    """Text of one block element, with <br> -> newline."""
    for br in el.find_all("br"):
        br.replace_with("\n")
    txt = el.get_text()
    # Normalise whitespace within each line; keep intentional line breaks.
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in txt.split("\n")]
    return "\n".join(ln for ln in lines if ln).strip()


def is_leaf_block(el):
    """A block with no nested block of interest -> emit it directly."""
    return el.find(BLOCK_TAGS) is None


def extract(html: str, selector: str | None):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    container = None
    for sel in ([selector] if selector else CONTENT_SELECTORS):
        if sel:
            container = soup.select_one(sel)
        if container:
            break
    if container is None:
        container = soup.body or soup

    for sel in JUNK_SELECTORS:
        for node in container.select(sel):
            node.decompose()

    blocks = []
    for el in container.find_all(BLOCK_TAGS):
        if not is_leaf_block(el):
            continue
        t = block_text(el)
        if not t or BOILERPLATE_RE.match(t):
            continue
        blocks.append(t)

    # De-duplicate consecutive identical blocks (some themes repeat the title).
    out, prev = [], None
    for b in blocks:
        if b != prev:
            out.append(b)
        prev = b
    return ("\n\n".join(out)).strip() + "\n"


def process_work(work_dir: Path, selector=None, preview=False):
    meta_path = work_dir / "metadata.json"
    if not meta_path.exists():
        return {"name": work_dir.name, "status": "skipped", "reason": "no metadata.json"}
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    html_rel = meta.get("source", {}).get("html")
    if not html_rel:
        return {"name": work_dir.name, "status": "skipped", "reason": "no source.html"}
    html_path = work_dir / html_rel
    if not html_path.exists():
        return {"name": work_dir.name, "status": "error", "reason": f"missing {html_rel}"}

    text = extract(html_path.read_text(encoding="utf-8", errors="replace"), selector)
    dev = len(re.findall(r"[ऀ-ॿ]", text))

    if preview:
        print(text)
        return {"name": work_dir.name, "status": "preview", "reason": f"{dev} देवनागरी chars"}

    (work_dir / "text.txt").write_text(text, encoding="utf-8")
    meta.setdefault("text", {})
    meta["text"]["extraction_method"] = "html"
    if meta["text"].get("ocr_status") in (None, "needs-ocr", "none"):
        meta["text"]["ocr_status"] = "born-digital"
    meta.setdefault("formats", {})["txt"] = "text.txt"
    meta["updated"] = date.today().isoformat()
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    return {"name": work_dir.name, "status": "extracted", "reason": f"{dev} देवनागरी chars"}


def main():
    ap = argparse.ArgumentParser(description="Extract work text from scraped HTML.")
    ap.add_argument("work_dir", nargs="?")
    ap.add_argument("--all", action="store_true",
                    help="Every work whose metadata has source.html.")
    ap.add_argument("--selector", help="CSS selector for the article container.")
    ap.add_argument("--preview", action="store_true",
                    help="Print extracted text; write nothing.")
    args = ap.parse_args()

    if args.all:
        targets = []
        for mp in ARCHIVE_ROOT.rglob("metadata.json"):
            meta = json.loads(mp.read_text(encoding="utf-8"))
            if meta.get("source", {}).get("html"):
                targets.append(mp.parent)
        targets.sort()
    elif args.work_dir:
        targets = [Path(args.work_dir).resolve()]
    else:
        ap.error("provide a work directory or --all")

    for d in targets:
        r = process_work(d, selector=args.selector, preview=args.preview)
        if not args.preview:
            reason = f"  — {r['reason']}" if r.get("reason") else ""
            print(f"  {r['name']}: {r['status']}{reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
