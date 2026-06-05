#!/usr/bin/env python3
"""
ocr.py — OCR stage of the Nepali Archives pipeline: scanned PDF -> text.txt

For works flagged `text.ocr_status == "needs-ocr"` (image-only scans with no
usable text layer), this rasterizes each page and runs Tesseract with the
Nepali model, then writes text.txt and updates metadata.

Run inside the conda env that has tesseract + pytesseract + pdf2image:
    conda activate archive_env

Usage:
    # Validate quality on a few pages first (writes nothing):
    python3 pipeline/ocr.py archives/authors/devkota/shakuntala --pages 20-23 --preview

    # Full run for one work:
    python3 pipeline/ocr.py archives/authors/devkota/shakuntala

    # Every work still flagged needs-ocr:
    python3 pipeline/ocr.py --all

Options:
    --pages A-B   Only OCR pages A..B (1-based, inclusive). Useful for sampling.
    --dpi N       Rasterization DPI (default 300).
    --lang CODE   Tesseract language(s), default 'nep'. Use 'nep+eng' for mixed.
    --preview     Print OCR'd text to stdout; do not write files or metadata.
    --force       OCR even if ocr_status is not 'needs-ocr'.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_ROOT = REPO_ROOT / "archives"
DEFAULT_LANG = "nep"


def _import_deps():
    try:
        import pytesseract  # noqa: F401
        from pdf2image import convert_from_path  # noqa: F401
    except ImportError as e:
        sys.exit(
            f"Missing OCR dependency: {e.name}. Activate the env first:\n"
            "    conda activate archive_env\n"
            "and ensure tesseract + pytesseract + pdf2image are installed."
        )
    import pytesseract
    from pdf2image import convert_from_path
    return pytesseract, convert_from_path


def parse_pages(spec, total):
    if not spec:
        return 1, total
    if "-" in spec:
        a, b = spec.split("-", 1)
        return int(a), int(b)
    n = int(spec)
    return n, n


def ocr_work(work_dir: Path, pages_spec=None, dpi=300, lang=DEFAULT_LANG,
             preview=False, force=False):
    pytesseract, convert_from_path = _import_deps()

    meta_path = work_dir / "metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    status = meta.get("text", {}).get("ocr_status")
    if status != "needs-ocr" and not force:
        return {"name": work_dir.name, "status": "skipped",
                "reason": f"ocr_status={status} (use --force to override)"}

    pdf_name = meta.get("source", {}).get("pdf") or meta.get("formats", {}).get("pdf")
    pdf = work_dir / pdf_name
    if not pdf.exists():
        return {"name": work_dir.name, "status": "error", "reason": f"missing {pdf_name}"}

    total = meta.get("pages") or 0
    first, last = parse_pages(pages_spec, total)

    print(f"  OCR {work_dir.name}: pages {first}-{last} @ {dpi}dpi, lang={lang}",
          file=sys.stderr)

    chunks = []
    for page in range(first, last + 1):
        images = convert_from_path(str(pdf), dpi=dpi, first_page=page, last_page=page)
        if not images:
            continue
        txt = pytesseract.image_to_string(images[0], lang=lang)
        chunks.append(txt.rstrip())
        print(f"    page {page}: {len(txt.strip())} chars", file=sys.stderr)

    text = ("\n\n".join(chunks)).strip() + "\n"

    if preview:
        print(text)
        return {"name": work_dir.name, "status": "preview",
                "reason": f"{len(text)} chars, pages {first}-{last}"}

    # Only treat as a complete OCR when the whole work was processed.
    full_run = pages_spec is None or (first == 1 and last >= total)
    (work_dir / "text.txt").write_text(text, encoding="utf-8")
    meta.setdefault("text", {})
    meta["text"]["extraction_method"] = "ocr"
    if full_run:
        meta["text"]["ocr_status"] = "ocr-done"
        meta["text"]["quality"] = meta["text"].get("quality") or "fair"
    meta.setdefault("formats", {})["txt"] = "text.txt"
    meta["updated"] = date.today().isoformat()
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    return {"name": work_dir.name, "status": "ocr-done" if full_run else "partial",
            "reason": f"{len(text)} chars"}


def main():
    ap = argparse.ArgumentParser(description="OCR scanned PDFs into text.txt.")
    ap.add_argument("work_dir", nargs="?")
    ap.add_argument("--all", action="store_true",
                    help="Every work flagged needs-ocr.")
    ap.add_argument("--pages", help="Page range A-B (1-based, inclusive).")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--lang", default=DEFAULT_LANG)
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.all:
        targets = []
        for mp in ARCHIVE_ROOT.rglob("metadata.json"):
            meta = json.loads(mp.read_text(encoding="utf-8"))
            if meta.get("text", {}).get("ocr_status") == "needs-ocr":
                targets.append(mp.parent)
        targets.sort()
    elif args.work_dir:
        targets = [Path(args.work_dir).resolve()]
    else:
        ap.error("provide a work directory or --all")

    for d in targets:
        r = ocr_work(d, pages_spec=args.pages, dpi=args.dpi, lang=args.lang,
                     preview=args.preview, force=args.force)
        if not args.preview:
            reason = f"  — {r['reason']}" if r.get("reason") else ""
            print(f"  {r['name']}: {r['status']}{reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
