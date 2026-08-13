#!/usr/bin/env python3
"""Fail when generated HTML points at a missing internal file."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit


LINK_ATTRIBUTES = {"href", "src"}
SKIPPED_SCHEMES = {"data", "http", "https", "mailto", "tel", "javascript"}


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in LINK_ATTRIBUTES and value:
                self.links.append((name, value))


def resolve_link(site: Path, document: Path, value: str) -> Path | None:
    parsed = urlsplit(value)
    if parsed.scheme.lower() in SKIPPED_SCHEMES or parsed.netloc:
        return None
    if not parsed.path:
        return document
    path = Path(unquote(parsed.path))
    if parsed.path.startswith("/"):
        target = site / str(path).lstrip("/")
    else:
        target = document.parent / path
    if parsed.path.endswith("/"):
        target /= "index.html"
    return target.resolve()


def find_broken_links(site: Path) -> list[str]:
    site = Path(site).resolve()
    problems = []
    for document in sorted(site.rglob("*.html")):
        parser = LinkParser()
        parser.feed(document.read_text(encoding="utf-8"))
        for attribute, value in parser.links:
            target = resolve_link(site, document, value)
            if target is None:
                continue
            try:
                target.relative_to(site)
            except ValueError:
                problems.append(
                    f"{document.relative_to(site)}: {attribute} escapes site: {value}"
                )
                continue
            if not target.exists():
                problems.append(
                    f"{document.relative_to(site)}: missing {attribute} {value}"
                )
    return problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("site", nargs="?", type=Path, default=Path("site"))
    args = parser.parse_args()
    problems = find_broken_links(args.site)
    if problems:
        print("\n".join(problems))
        raise SystemExit(f"broken internal links: {len(problems)}")
    html_files = sum(1 for _ in args.site.rglob("*.html"))
    print(f"internal-link audit passed ({html_files} HTML files)")


if __name__ == "__main__":
    main()
