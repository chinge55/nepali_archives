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
import re
import sys
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


def main() -> int:
    errors: list[str] = []
    seen: dict[str, set] = {}        # author dir -> ids (uniqueness within an author)
    nworks = 0

    for meta_path in sorted(AUTHORS.glob("*/*/metadata.json")):
        work = meta_path.parent
        author_dir, slug = work.parent.name, work.name
        rel = work.relative_to(ROOT)
        nworks += 1

        def err(msg):
            errors.append(f"{rel}: {msg}")

        try:
            m = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            err(f"metadata.json is not valid JSON: {e}")
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
        a_id = (m.get("author") or {}).get("id")
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
        status = (m.get("rights") or {}).get("status")
        if status not in PUBLISHABLE_RIGHTS:
            err(f"rights.status '{status}' is not publishable — must be one of "
                f"{sorted(PUBLISHABLE_RIGHTS)} (see Rights.md / CONTRIBUTING.md)")

    print(f"validated {nworks} works across {len(seen)} authors")
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
