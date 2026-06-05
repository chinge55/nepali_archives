#!/usr/bin/env python3
"""
extract.py — Stage 1 of the Nepali Archives pipeline: PDF -> text.txt

Reads a work directory containing a source PDF and metadata.json, extracts the
text layer with `pdftotext`, and writes text.txt alongside it. Detects
image-only PDFs (no usable text layer) and flags them as needing OCR instead of
writing an empty file.

Dependencies: Poppler's `pdftotext` and `pdfinfo` on PATH. No Python packages.

Usage:
    python3 pipeline/extract.py archives/authors/devkota/munamadan
    python3 pipeline/extract.py --all                 # walk the whole archive
    python3 pipeline/extract.py --all --dry-run        # report only, write nothing
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_ROOT = REPO_ROOT / "archives"

# A work is considered to have a real text layer if at least this many
# Devanagari codepoints come out. Image-only scans extract ~0.
MIN_DEVANAGARI_CHARS = 200
DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def pdf_page_count(pdf: Path):
    res = run(["pdfinfo", str(pdf)])
    for line in res.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    return None


def extract_text(pdf: Path) -> str:
    """Extract text preserving line breaks (important for verse)."""
    res = run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"])
    if res.returncode != 0:
        raise RuntimeError(f"pdftotext failed for {pdf.name}: {res.stderr.strip()}")
    return res.stdout


def devanagari_count(text: str) -> int:
    return len(DEVANAGARI_RE.findall(text))


def process_work(work_dir: Path, dry_run: bool = False) -> dict:
    meta_path = work_dir / "metadata.json"
    if not meta_path.exists():
        return {"dir": str(work_dir), "status": "skipped", "reason": "no metadata.json"}

    raw = meta_path.read_text(encoding="utf-8").strip()
    if not raw:
        return {"dir": str(work_dir), "status": "skipped", "reason": "empty metadata.json"}
    meta = json.loads(raw)

    pdf_name = meta.get("source", {}).get("pdf") or meta.get("formats", {}).get("pdf")
    if not pdf_name:
        return {"dir": str(work_dir), "status": "skipped", "reason": "no source pdf in metadata"}
    pdf = work_dir / pdf_name
    if not pdf.exists():
        return {"dir": str(work_dir), "status": "error", "reason": f"missing pdf {pdf_name}"}

    text = extract_text(pdf)
    dev = devanagari_count(text)
    pages = pdf_page_count(pdf)

    result = {"dir": str(work_dir), "devanagari_chars": dev, "pages": pages}

    if dev < MIN_DEVANAGARI_CHARS:
        # Image-only scan: don't write a junk text file; flag for OCR.
        result["status"] = "needs-ocr"
        meta.setdefault("text", {})
        meta["text"]["ocr_status"] = "needs-ocr"
        meta["text"]["extraction_method"] = None
    else:
        result["status"] = "extracted"
        txt_path = work_dir / "text.txt"
        if not dry_run:
            txt_path.write_text(text, encoding="utf-8")
        meta.setdefault("text", {})
        meta["text"]["extraction_method"] = "pdf-text-layer"
        if meta["text"].get("ocr_status") in (None, "needs-ocr", "none"):
            meta["text"]["ocr_status"] = "embedded-ocr"
        meta.setdefault("formats", {})
        meta["formats"]["txt"] = "text.txt"

    if pages:
        meta["pages"] = pages
    meta["updated"] = date.today().isoformat()

    if not dry_run:
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return result


def find_work_dirs(root: Path):
    return sorted(p.parent for p in root.rglob("metadata.json"))


def main():
    ap = argparse.ArgumentParser(description="Extract text from archive PDFs.")
    ap.add_argument("work_dir", nargs="?", help="A single work directory to process.")
    ap.add_argument("--all", action="store_true", help="Process every work under archives/.")
    ap.add_argument("--dry-run", action="store_true", help="Report only; write nothing.")
    args = ap.parse_args()

    if args.all:
        targets = find_work_dirs(ARCHIVE_ROOT)
    elif args.work_dir:
        targets = [Path(args.work_dir).resolve()]
    else:
        ap.error("provide a work directory or --all")

    if not targets:
        print("No work directories found.", file=sys.stderr)
        return 1

    rows = [process_work(d, dry_run=args.dry_run) for d in targets]
    width = max(len(Path(r["dir"]).name) for r in rows)
    for r in rows:
        name = Path(r["dir"]).name.ljust(width)
        extra = ""
        if "devanagari_chars" in r:
            extra = f"  ({r['devanagari_chars']} देवनागरी chars, {r.get('pages')} pp)"
        reason = f"  — {r['reason']}" if r.get("reason") else ""
        print(f"  {name}  {r['status']}{extra}{reason}")
    if args.dry_run:
        print("\n(dry run — no files written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
