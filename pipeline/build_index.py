#!/usr/bin/env python3
"""build_index.py — regenerate archives/index.json from every work's metadata.json.

index.json is the catalogue build_site.py reads (it needs each work's `path`,
`id`, and `collection`; it re-reads everything else from metadata.json). Nothing
else writes index.json, so run this after adding/editing/removing any work:

    python3 pipeline/build_index.py            # writes archives/index.json
    python3 pipeline/build_index.py --check     # dry-run -> /tmp/index_check.json (no write)

Mapping rules (kept faithful to the existing catalogue):
  author      = metadata author.name_roman
  collection  = list parsed from the description's "From the collection X; Y."
                (terse phrasing required; None if absent)
  source      = metadata source.name ONLY when source.url is set (web origin),
                else null (print/OCR works carry their source.name in metadata)
  formats     = [k for k in (pdf,txt,html,epub) if metadata.formats[k]]
  works order = by author dir (alphabetical), then by slug (dir name)
Output uses indent=1 (matches the committed file — keeps diffs clean).
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCH = ROOT / "archives"
TODAY = __import__("datetime").date.today().isoformat()

_COLL = re.compile(r"From the collection ([^.]+)\.")

def collection_of(desc):
    if not desc:
        return None
    m = _COLL.search(desc)
    return [c.strip() for c in m.group(1).split(";")] if m else None

def entry(meta, wd):
    src = meta.get("source") or {}
    fmts = meta.get("formats") or {}
    return {
        "id": meta["id"],
        "title": meta["title"],
        "title_roman": meta.get("title_roman"),
        "author": meta["author"].get("name_roman"),
        "genre": meta.get("genre", []),
        "collection": collection_of(meta.get("description")),
        "rights": meta["rights"]["status"],
        "proofread": meta["text"].get("proofread", False),
        "source": src.get("name") if src.get("url") else None,
        "path": str(wd.relative_to(ROOT)),
        "formats": [k for k in ("pdf", "txt", "html", "epub") if fmts.get(k)],
    }

def build():
    works = []
    for author in sorted(p.name for p in (ARCH / "authors").iterdir() if p.is_dir()):
        adir = ARCH / "authors" / author
        for wd in sorted(p for p in adir.iterdir() if p.is_dir()):
            mp = wd / "metadata.json"
            if mp.exists():
                works.append(entry(json.loads(mp.read_text(encoding="utf-8")), wd))
    return {"archive": "Nepali Archives", "generated": TODAY,
            "count": len(works), "works": works}

if __name__ == "__main__":
    idx = build()
    out = Path("/tmp/index_check.json") if "--check" in sys.argv else ARCH / "index.json"
    out.write_text(json.dumps(idx, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out}: {idx['count']} works")
