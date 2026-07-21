"""PDF handling: page count and page rendering, via poppler CLI tools.

Rendering matches the proven archive workflow (process-book-archive skill):
300 dpi PNG, `pg-` prefix, zero-padded page numbers.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


def page_count(pdf: Path) -> int:
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True,
                         text=True, check=True).stdout
    m = re.search(r"^Pages:\s+(\d+)", out, re.M)
    if not m:
        raise ValueError(f"pdfinfo gave no page count for {pdf}")
    return int(m.group(1))


def render_pages(pdf: Path, out_dir: Path, dpi: int,
                 first: int | None = None, last: int | None = None) -> list[Path]:
    """Render pages to out_dir/pg-NNN.png and return the image paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["pdftoppm", "-r", str(dpi), "-png"]
    if first is not None:
        cmd += ["-f", str(first)]
    if last is not None:
        cmd += ["-l", str(last)]
    cmd += [str(pdf), str(out_dir / "pg")]
    subprocess.run(cmd, check=True, capture_output=True)
    images = sorted(out_dir.glob("pg-*.png"))
    if not images:
        raise RuntimeError(f"pdftoppm produced no pages for {pdf}")
    return images
