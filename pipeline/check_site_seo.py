#!/usr/bin/env python3
"""Audit built HTML titles, descriptions, canonicals, and sitemap completeness."""
import argparse
from pathlib import Path
from sitegen.seo import audit_site


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    args = parser.parse_args()
    if not (args.site / "index.html").is_file():
        parser.error("site must contain a built index.html")
    errors, report = audit_site(args.site)
    for error in errors:
        print(error)
    print(f"SEO audit: {report['html_pages']} HTML pages, {report['indexable_pages']} indexable pages, {len(errors)} errors")
    # A useful description has no universal character minimum, especially across
    # scripts. Surface short descriptions for review rather than padding prose.
    if report["short_descriptions"]:
        print(f"Review: {len(report['short_descriptions'])} indexable descriptions under 100 characters")
        for path in report["short_descriptions"]:
            print(f"  {path}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
