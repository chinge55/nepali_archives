#!/usr/bin/env python3
"""Fetch public Sahitya Ras source-edition PDFs into an ignored cache."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib, json, re
from pathlib import Path
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENDPOINT = "https://sahityaras.com/download.php?book={book}&format=pdf"
USER_AGENT = "nepali-archive-sahityaras-pdf-fetch/1"

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _books(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    books = data.get("books") if isinstance(data, dict) else data
    if not isinstance(books, list):
        raise ValueError("manifest must contain a books list")
    for book in books:
        if not isinstance(book, dict) or (not isinstance(book.get("id"), str) or not re.fullmatch(r"[a-z0-9_-]+", book["id"])):
            raise ValueError("each book requires an id")
    return books

def _fetch(url: str, timeout: int) -> tuple[int, str, bytes]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.headers.get("Content-Type", ""), response.read()
    except HTTPError as exc:
        return exc.code, "", str(exc).encode("utf-8", errors="replace")
    except (URLError, TimeoutError) as exc:
        return 0, "", str(exc).encode("utf-8", errors="replace")

def fetch_book(book: dict, output: Path, *, timeout: int, force: bool) -> dict:
    slug = book["id"]
    pdf_url = book.get("pdf_url") or ENDPOINT.format(book=slug)
    row = {"book": slug, "title": book.get("title"),
           "source_url": book.get("source_url") or book.get("page_url"),
           "pdf_url": pdf_url, "checked_at": datetime.now(timezone.utc).isoformat()}
    destination = output / f"{slug}.pdf"
    expected_hash = book.get("sha256") if isinstance(book.get("sha256"), str) else None
    expected_pages = book.get("page_count") if isinstance(book.get("page_count"), int) else None
    if destination.exists() and not force:
        data = destination.read_bytes(); digest = _sha256(data)
        if data.startswith(b"%PDF-") and (expected_hash is None or digest == expected_hash):
            row.update({"status": "cached", "http_status": 200, "bytes": len(data),
                        "sha256": digest, "page_count": expected_pages})
            return row
        # Preserve the previous cache file if fetching or hash verification fails.
    status, content_type, data = _fetch(pdf_url, timeout)
    row.update({"http_status": status, "content_type": content_type, "response_bytes": len(data)})
    if status != 200 or not data.startswith(b"%PDF-"):
        row["status"] = "unavailable" if status in (404, 410) else "invalid"
        row["response_sha256"] = _sha256(data)
        return row
    digest = _sha256(data)
    if expected_hash is not None and digest != expected_hash:
        row.update({"status": "hash-mismatch", "sha256": digest, "bytes": len(data)})
        return row
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output, prefix=f".{slug}.", suffix=".tmp", delete=False) as tmp:
        tmp.write(data); temporary = Path(tmp.name)
    temporary.replace(destination)
    row.update({"status": "fetched", "bytes": len(data), "sha256": digest, "page_count": expected_pages})
    return row

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("sources/sahityaras/catalogue.json"),
                        help="JSON manifest with books[].id and optional pdf_url/sha256/page_count")
    parser.add_argument("--output", type=Path, required=True, help="ignored PDF cache directory")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--force", action="store_true", help="redownload valid cached files")
    args = parser.parse_args(argv)
    if args.timeout < 1: parser.error("--timeout must be positive")
    books = _books(args.manifest); args.output.mkdir(parents=True, exist_ok=True)
    rows = [fetch_book(book, args.output, timeout=args.timeout, force=args.force) for book in books]
    rows.sort(key=lambda row: row["book"])
    result = {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
              "manifest": str(args.manifest), "endpoint": ENDPOINT, "books": rows}
    (args.output / "downloads.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"total": len(rows), "fetched": sum(r["status"] == "fetched" for r in rows),
                      "cached": sum(r["status"] == "cached" for r in rows),
                      "failed": sum(r["status"] not in {"fetched", "cached"} for r in rows)}))
    return 0 if all(r["status"] in {"fetched", "cached"} for r in rows) else 1

if __name__ == "__main__": raise SystemExit(main())
