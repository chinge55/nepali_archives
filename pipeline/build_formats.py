#!/usr/bin/env python3
"""
build_formats.py — Stage 2 of the Nepali Archives pipeline: text.txt -> reader.html

Turns the extracted text.txt of each work into a clean, self-contained,
readable HTML page (one file, no external assets, works offline). EPUB is
generated too when `pandoc` or `ebook-convert` is available on PATH.

This stage NEVER alters the words of the text. It only wraps them for reading:
paragraphs are kept as written, blank lines become stanza/paragraph breaks, and
single line breaks (important for verse) are preserved.

Usage:
    python3 pipeline/build_formats.py archives/authors/devkota/munamadan
    python3 pipeline/build_formats.py --all
"""

import argparse
import html
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_ROOT = REPO_ROOT / "archives"

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — {author}</title>
<meta name="author" content="{author}">
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: "Noto Serif Devanagari", "Mukta", Georgia, serif;
    max-width: 42rem; margin: 0 auto; padding: 2rem 1.25rem 6rem;
    line-height: 1.9; font-size: 1.15rem; color: #1a1a1a; background: #fbfaf7;
  }}
  @media (prefers-color-scheme: dark) {{
    body {{ color: #e6e3dc; background: #15140f; }}
    a {{ color: #9bc0ff; }}
  }}
  header {{ border-bottom: 1px solid #ccc4; padding-bottom: 1rem; margin-bottom: 2rem; }}
  h1 {{ font-size: 1.9rem; margin: 0 0 .25rem; }}
  .byline {{ font-size: 1.1rem; opacity: .8; margin: 0; }}
  .meta {{ font-size: .85rem; opacity: .65; margin-top: .75rem; }}
  .downloads {{ font-size: .9rem; margin-top: .5rem; }}
  .downloads a {{ margin-right: 1rem; }}
  .work {{ white-space: pre-wrap; }}     /* preserve verse line breaks */
  .work p {{ margin: 0 0 1.4rem; white-space: pre-wrap; }}
  footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #ccc4;
            font-size: .8rem; opacity: .6; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <p class="byline">{author}</p>
  <p class="meta">{meta_line}</p>
  <p class="downloads">{downloads}</p>
</header>
<main class="work">
{body}
</main>
<footer>
  <p>{rights_line}</p>
  <p>Nepali Archives — free, public-domain Nepali literature. Source: {source}</p>
</footer>
</body>
</html>
"""


def text_to_html_body(text: str) -> str:
    """Blank-line-separated blocks become <p>; inner newlines are preserved."""
    blocks = [b.strip("\n") for b in text.replace("\r\n", "\n").split("\n\n")]
    paras = [f"<p>{html.escape(b)}</p>" for b in blocks if b.strip()]
    return "\n".join(paras)


def meta_year(meta: dict) -> str:
    fp = meta.get("first_published") or {}
    bits = []
    if fp.get("bs"):
        bits.append(f"{fp['bs']} BS")
    if fp.get("ad"):
        bits.append(f"{fp['ad']} AD")
    return " / ".join(bits)


def build_epub(work_dir: Path, meta: dict, html_path: Path) -> str | None:
    epub_path = work_dir / "reader.epub"
    title = meta.get("title", "")
    author = meta.get("author", {}).get("name", "")
    lang = meta.get("language", "ne")
    if shutil.which("pandoc"):
        cmd = ["pandoc", str(html_path), "-o", str(epub_path),
               "--metadata", f"title={title}", "--metadata", f"author={author}",
               "--metadata", f"lang={lang}"]
    elif shutil.which("ebook-convert"):
        cmd = ["ebook-convert", str(html_path), str(epub_path),
               "--title", title, "--authors", author, "--language", lang]
    else:
        return None
    res = subprocess.run(cmd, capture_output=True, text=True)
    return "reader.epub" if res.returncode == 0 and epub_path.exists() else None


def process_work(work_dir: Path) -> dict:
    meta_path = work_dir / "metadata.json"
    txt_path = work_dir / "text.txt"
    name = work_dir.name
    if not meta_path.exists():
        return {"name": name, "status": "skipped", "reason": "no metadata.json"}
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not txt_path.exists():
        return {"name": name, "status": "skipped", "reason": "no text.txt (run extract first / needs OCR)"}

    text = txt_path.read_text(encoding="utf-8")
    author = meta.get("author", {})
    source = meta.get("source", {})
    rights = meta.get("rights", {})

    downloads = [f'<a href="{source.get("pdf")}">PDF</a>'] if source.get("pdf") else []
    downloads.append('<a href="text.txt">Plain text</a>')

    page = PAGE_TEMPLATE.format(
        lang=meta.get("language", "ne"),
        title=html.escape(meta.get("title", name)),
        author=html.escape(author.get("name", "")),
        meta_line=html.escape(" · ".join(filter(None, [
            ", ".join(meta.get("genre", [])) or None, meta_year(meta) or None,
        ]))),
        downloads=" ".join(downloads),
        body=text_to_html_body(text),
        rights_line=html.escape(
            f"Rights: {rights.get('status', 'unknown')}"
            + (f" — {rights['basis']}" if rights.get("basis") else "")),
        source=html.escape(source.get("url") or source.get("name") or "—"),
    )
    html_path = work_dir / "reader.html"
    html_path.write_text(page, encoding="utf-8")

    # Record which formats exist. `updated` is author-controlled metadata, NOT a build
    # side-effect, so build_formats no longer stamps it — this keeps the repo churn-free
    # when reader.* are regenerated. Write metadata back only if formats actually changed.
    fmts = meta.setdefault("formats", {})
    before = dict(fmts)
    fmts["html"] = "reader.html"
    epub = build_epub(work_dir, meta, html_path)
    if epub:
        fmts["epub"] = epub
    if fmts != before:
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {"name": name, "status": "built", "epub": bool(epub)}


def main():
    ap = argparse.ArgumentParser(description="Build reader HTML/EPUB from extracted text.")
    ap.add_argument("work_dir", nargs="?")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.all:
        targets = sorted(p.parent for p in ARCHIVE_ROOT.rglob("metadata.json"))
    elif args.work_dir:
        targets = [Path(args.work_dir).resolve()]
    else:
        ap.error("provide a work directory or --all")

    for r in [process_work(d) for d in targets]:
        epub = "  +epub" if r.get("epub") else ""
        reason = f"  — {r['reason']}" if r.get("reason") else ""
        print(f"  {r['name']}: {r['status']}{epub}{reason}")
    if not shutil.which("pandoc") and not shutil.which("ebook-convert"):
        print("\n(note: no pandoc/ebook-convert found — EPUB skipped. `apt install pandoc` to enable.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
