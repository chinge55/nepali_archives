#!/usr/bin/env python3
"""
validate.py — pre-merge checks for contributions (run in CI on every pull request,
see .github/workflows/validate.yml). Catches the common mistakes BEFORE a human looks:
malformed metadata, slug/id mismatches, empty/garbled text, and out-of-policy rights.

Build artifacts (reader.html/epub, index.json, the font subset, site/) are NOT in the
repo — CI regenerates them — so a contribution is just metadata.json + text.txt + source.
This script validates exactly those sources.

    python3 pipeline/validate.py        # exits non-zero (with a report) on any problem

Needs jsonschema (`pip install jsonschema`); everything else is stdlib.
"""
import json
import hashlib
import re
import sys
import argparse
from pathlib import Path

try:
    import jsonschema
except ImportError:
    sys.exit("validate.py needs jsonschema:  pip install jsonschema")

ROOT = Path(__file__).resolve().parent.parent
AUTHORS = ROOT / "archives" / "authors"
SCHEMA = json.loads((ROOT / "metadata.schema.json").read_text(encoding="utf-8"))

SLUG_RE = re.compile(r"^[a-z0-9_-]+$")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
PUBLISHABLE_RIGHTS = {"public-domain", "permission-granted"}


def _safe_pdf_path(work: Path, filename: object) -> tuple[Path | None, str | None]:
    """Resolve a metadata PDF filename without permitting symlink/path escape."""
    if not isinstance(filename, str) or not filename or Path(filename).is_absolute():
        return None, "PDF filename must be a relative path"
    candidate = work / filename
    try:
        if candidate.resolve().parent != work.resolve() and not candidate.resolve().is_relative_to(work.resolve()):
            return None, "PDF path escapes the work directory"
    except OSError as exc:
        return None, f"cannot resolve PDF path: {exc}"
    if candidate.is_symlink():
        return None, "PDF path must not be a symlink"
    if not candidate.is_file():
        return None, "PDF file is missing or not a regular file"
    try:
        if not candidate.resolve().is_relative_to(work.resolve()):
            return None, "PDF symlink resolves outside the work directory"
    except OSError as exc:
        return None, f"cannot resolve PDF path: {exc}"
    return candidate, None


def validate_pdf_editions(work: Path, metadata: dict) -> list[str]:
    """Validate local PDF provenance declared by one metadata object.

    This intentionally uses byte checks only; page-count extraction belongs to
    the optional PDF review tooling and the declared count is the source of
    truth for section-range validation.
    """
    errors: list[str] = []
    source = metadata.get("source")
    if not isinstance(source, dict):
        return errors

    formats = metadata.get("formats")
    primary = formats.get("pdf") if isinstance(formats, dict) else None
    if primary is not None:
        path, problem = _safe_pdf_path(work, primary)
        if problem:
            errors.append(f"formats.pdf: {problem}")
        else:
            try:
                with path.open('rb') as handle:
                    if handle.read(5) != b"%PDF-":
                        errors.append("formats.pdf: file does not have a PDF signature")
            except OSError as exc:
                errors.append(f"formats.pdf: cannot read file: {exc}")

    editions = source.get("pdf_editions")
    if editions is None:
        return errors
    if not isinstance(editions, list):
        return ["source.pdf_editions must be an array"]
    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    for index, edition in enumerate(editions):
        prefix = f"source.pdf_editions[{index}]"
        if not isinstance(edition, dict):
            errors.append(f"{prefix}: edition must be an object")
            continue
        edition_id = edition.get("id")
        if isinstance(edition_id, str):
            if edition_id in seen_ids:
                errors.append(f"{prefix}: duplicate edition id '{edition_id}'")
            seen_ids.add(edition_id)
        filename = edition.get("file")
        if isinstance(filename, str):
            if filename in seen_files:
                errors.append(f"{prefix}: duplicate edition file '{filename}'")
            seen_files.add(filename)
        path, problem = _safe_pdf_path(work, filename)
        if problem:
            errors.append(f"{prefix}.file: {problem}")
            path = None
        data = None
        if path is not None:
            try:
                data = path.read_bytes()
                if data[:5] != b"%PDF-":
                    errors.append(f"{prefix}.file: file does not have a PDF signature")
            except OSError as exc:
                errors.append(f"{prefix}.file: cannot read file: {exc}")
        expected_hash = edition.get("sha256")
        if isinstance(expected_hash, str) and re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            if data is not None and hashlib.sha256(data).hexdigest() != expected_hash:
                errors.append(f"{prefix}.sha256: hash does not match file")
        elif expected_hash is not None:
            errors.append(f"{prefix}.sha256: must be a lowercase SHA-256 hex digest")
        page_count = edition.get("page_count")
        valid_count = isinstance(page_count, int) and not isinstance(page_count, bool) and page_count >= 1
        if not valid_count and page_count is not None:
            errors.append(f"{prefix}.page_count: must be a positive integer")
        sections = edition.get("sections", [])
        if sections is None:
            sections = []
        if not isinstance(sections, list):
            errors.append(f"{prefix}.sections: must be an array")
            continue
        for section_index, section in enumerate(sections):
            sp = f"{prefix}.sections[{section_index}]"
            if not isinstance(section, dict):
                errors.append(f"{sp}: section must be an object")
                continue
            start, end = section.get("page_start"), section.get("page_end")
            if not (valid_count and isinstance(start, int) and not isinstance(start, bool)
                    and isinstance(end, int) and not isinstance(end, bool)
                    and 1 <= start <= end <= page_count):
                errors.append(f"{sp}: page range must satisfy 1 <= page_start <= page_end <= page_count")
    return errors


def validate_authors(authors: Path = AUTHORS) -> tuple[int, int, list[str]]:
    """Validate the canonical authors tree or an isolated staged mirror."""
    errors: list[str] = []
    seen: dict[str, set] = {}        # author dir -> ids (uniqueness within an author)
    nworks = 0

    for meta_path in sorted(authors.glob("*/*/metadata.json")):
        work = meta_path.parent
        author_dir, slug = work.parent.name, work.name
        try:
            rel = work.relative_to(ROOT)
        except ValueError:
            rel = work
        nworks += 1

        def err(msg):
            errors.append(f"{rel}: {msg}")

        try:
            m = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            err(f"metadata.json is not valid JSON: {e}")
            continue
        if not isinstance(m, dict):
            err("metadata.json must contain an object")
            continue

        try:
            jsonschema.validate(m, SCHEMA)
        except jsonschema.ValidationError as e:
            err(f"metadata fails schema: {e.message} (at /{'/'.join(map(str, e.path))})")

        # slug / id conventions: dir name == id == [a-z0-9_-]; author dir == author.id
        if not SLUG_RE.match(slug):
            err(f"directory name '{slug}' must match [a-z0-9_-]")
        if m.get("id") != slug:
            err(f"id '{m.get('id')}' must equal the directory name '{slug}'")
        a_id = m["author"].get("id") if isinstance(m.get("author"), dict) else None
        if a_id != author_dir:
            err(f"author.id '{a_id}' must equal the author directory '{author_dir}'")
        ids = seen.setdefault(author_dir, set())
        if slug in ids:
            err(f"duplicate id '{slug}' within author '{author_dir}'")
        ids.add(slug)

        # text.txt present, non-empty, actually Devanagari
        tp = work / "text.txt"
        if not tp.exists():
            err("missing text.txt")
        else:
            t = tp.read_text(encoding="utf-8", errors="replace").strip()
            if not t:
                err("text.txt is empty")
            elif not DEVANAGARI.search(t):
                err("text.txt contains no Devanagari — is this the right file?")

        # rights gate: only public-domain / permission-granted works may be published
        status = m["rights"].get("status") if isinstance(m.get("rights"), dict) else None
        if status not in PUBLISHABLE_RIGHTS:
            err(f"rights.status '{status}' is not publishable — must be one of "
                f"{sorted(PUBLISHABLE_RIGHTS)} (see Rights.md / CONTRIBUTING.md)")

        for pdf_error in validate_pdf_editions(work, m):
            err(pdf_error)

    return nworks, len(seen), errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate archive source contributions.")
    ap.add_argument("--authors-root", type=Path, default=AUTHORS,
                    help="alternate staged archives/authors tree")
    args = ap.parse_args(argv)
    nworks, nauthors, errors = validate_authors(args.authors_root.resolve())
    print(f"validated {nworks} works across {nauthors} authors")
    if errors:
        print(f"\n✗ {len(errors)} problem(s) found:\n")
        for e in errors:
            print(f"  ✗ {e}")
        print("\nSee CONTRIBUTING.md for the conventions.")
        return 1
    print("✓ all contribution checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
