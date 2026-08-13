#!/usr/bin/env python3
"""Remove executable and personal site furniture from archived HTML sources.

The archive preserves the page needed to verify a literary transcription, not
an executable copy of the surrounding website. This pass preserves source
content while removing:

* script, noscript, and iframe elements;
* public reader-comment sections, which can contain third-party personal data.
* trailing horizontal whitespace left behind by removed elements.

Run with no arguments to sanitize extracted HTML files in place, or with
--check to fail when a tracked capture still needs sanitizing.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVES = REPO_ROOT / "archives"

EXECUTABLE = re.compile(
    r"<(?P<tag>script|noscript|iframe)\b[^>]*>.*?</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)
SELF_CLOSING_EXECUTABLE = re.compile(
    r"<(?:script|noscript|iframe)\b[^>]*/\s*>",
    re.IGNORECASE | re.DOTALL,
)
COMMENTS = re.compile(
    r"<div\b(?=[^>]*\bid=[\"']comments[\"'])[^>]*>"
    r".*?</div>\s*<!--\s*\.comments-area\s*-->",
    re.IGNORECASE | re.DOTALL,
)


def sanitize(html: str) -> str:
    html = COMMENTS.sub(
        "\n<!-- Reader comments removed from the archival source copy. -->", html
    )
    html = EXECUTABLE.sub("", html)
    html = SELF_CLOSING_EXECUTABLE.sub("", html)
    return re.sub(r"[ \t]+(?=\r?$)", "", html, flags=re.MULTILINE)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report only; write nothing")
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()

    paths = args.paths or sorted(
        path for path in ARCHIVES.rglob("*.html") if "extracted" in path.parts
    )
    changed: list[Path] = []
    for path in paths:
        original = path.read_text(encoding="utf-8", errors="replace")
        clean = sanitize(original)
        if clean == original:
            continue
        changed.append(path)
        if not args.check:
            path.write_text(clean, encoding="utf-8")

    action = "need sanitizing" if args.check else "sanitized"
    print(f"{len(changed)} HTML source files {action}")
    if args.check and changed:
        for path in changed[:20]:
            print(path.relative_to(REPO_ROOT))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
