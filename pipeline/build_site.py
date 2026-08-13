#!/usr/bin/env python3
"""Build the Nepali Archives static reader site.

The implementation lives in pipeline/sitegen/. This file intentionally remains
the stable command-line entry point used by contributors and CI.
"""

import argparse
from datetime import date
from pathlib import Path
import sys


PIPELINE = Path(__file__).resolve().parent
ROOT = PIPELINE.parent
sys.path.insert(0, str(PIPELINE))
sys.path.insert(
    0, str(ROOT / "roman_nepali_transliteration" / "pipeline")
)

from translit_keys import key_romanize, normalize, word_keys

from sitegen.builder import build as build_site
from sitegen.context import BuildContext, BuildStats


def normalize_key(word: str) -> str:
    """Return the typing tool's primary normalized Roman key."""
    return normalize(key_romanize(word))


def build(
    archive_base: str = "",
    *,
    output_dir: Path | None = None,
    build_date: date | None = None,
) -> BuildStats:
    """Build the site and preserve the historical command's status output."""
    context = BuildContext.for_root(
        ROOT,
        output_dir=output_dir,
        archive_base=archive_base,
        build_date=build_date,
    )
    result = build_site(
        context,
        normalize_key=normalize_key,
        translit_word_keys=word_keys,
    )
    print(
        f"built {context.site.relative_to(ROOT) if context.site.is_relative_to(ROOT) else context.site}/ : "
        f"{result.pages} pages ({result.works} works), "
        f"search index {result.search_index_bytes // 1024} KB"
    )
    if archive_base:
        print(
            f"  downloads -> {archive_base.rstrip('/')}/  "
            "(lean site; files served from the archive store)"
        )
    else:
        print(
            "  downloads bundled into site (self-contained). "
            "Pass --archive-base <url> to serve files from S3/R2 instead."
        )
    return result


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "date must use YYYY-MM-DD"
        ) from error


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--archive-base",
        default="",
        help="Public base URL of uploaded archive files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory (default: site/).",
    )
    parser.add_argument(
        "--date",
        type=parse_date,
        help="Build date in Nepal time for deterministic previews/tests.",
    )
    arguments = parser.parse_args()
    build(
        arguments.archive_base,
        output_dir=arguments.output,
        build_date=arguments.date,
    )


if __name__ == "__main__":
    main()
