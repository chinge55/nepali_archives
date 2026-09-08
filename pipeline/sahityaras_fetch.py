#!/usr/bin/env python3
"""Fetch pinned, text-only snapshots of the Sahitya Ras catalogue.

The catalogue is the source of truth for repository URLs and branches.  Each
repository is resolved to a commit, downloaded from GitHub's codeload endpoint,
and unpacked only into the EPUB/source files useful for review.  A JSON snapshot
records the commit, source archive hash, and every cached file hash so a later
run can resume safely and detect source changes.

This script deliberately does not interpret or publish literary content.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import shutil
import subprocess
import tarfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOGUE = ROOT / "plans" / "sahityaras-catalogue.csv"
DEFAULT_CACHE = ROOT / ".ingest-work" / "sahityaras" / "catalogue"
SNAPSHOT_NAME = "snapshot.json"
RETRIES = 4


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def request(url: str, *, accept: str = "application/vnd.github+json") -> bytes:
    """GET a public URL with bounded retry/backoff for transient responses."""
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            req = Request(url, headers={"Accept": accept, "User-Agent": "nepali-archive-sahityaras-fetch"})
            with urlopen(req, timeout=45) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            last = exc
            if isinstance(exc, HTTPError) and exc.code not in {408, 429, 500, 502, 503, 504}:
                break
            if attempt + 1 < RETRIES:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"GET failed after {RETRIES} attempts: {url}: {last}")


def repo_parts(url: str) -> tuple[str, str]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise ValueError(f"expected public GitHub URL: {url}")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2 or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        raise ValueError(f"invalid GitHub repository URL: {url}")
    return parts[0], parts[1].removesuffix(".git")


def resolve_commit(owner: str, repo: str, branch: str) -> str:
    try:
        data = json.loads(request(f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}").decode("utf-8"))
        commit = data.get("sha")
    except RuntimeError:
        # The unauthenticated API is rate limited; git smart HTTP is a fallback.
        result = subprocess.run(["git", "ls-remote", f"https://github.com/{owner}/{repo}.git", f"refs/heads/{branch}"], check=True, capture_output=True, text=True)
        commit = result.stdout.split()[0] if result.stdout.split() else None
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError(f"GitHub response did not contain a commit SHA for {owner}/{repo}@{branch}")
    return commit


def source_member(name: str) -> bool:
    """Return whether a tar member belongs in a text/source snapshot."""
    # GitHub tarballs have a single top-level <repo>-<sha>/ directory.
    parts = name.split("/")
    if len(parts) < 2 or any(part in {"", ".", ".."} for part in parts):
        return False
    rel = "/".join(parts[1:])
    if PurePosixPath(rel).is_absolute():
        return False
    return (
        rel == "LICENSE.md"
        or (rel.startswith("src/EPUB/") and rel.count("/") == 2 and rel.endswith(".xhtml"))
        or rel == ".gitattributes"
        or rel in {"src/mimetype", "src/META-INF/container.xml"}
        or rel in {"src/EPUB/content.opf", "src/EPUB/nav.xhtml", "src/EPUB/toc.ncx"}
        or (rel.startswith("src/EPUB/text/") and rel.endswith((".xhtml", ".html", ".xml")))
    )


def file_inventory(package: Path) -> list[dict]:
    records = []
    for path in sorted(p for p in package.rglob("*") if p.is_file()):
        rel = path.relative_to(package).as_posix()
        data = path.read_bytes()
        records.append({"path": rel, "size": len(data), "sha256": sha256(data)})
    return records


def validate_cached_snapshot(target: Path, snapshot: dict, owner: str, repo: str, branch: str) -> None:
    if snapshot.get('repository') != f'{owner}/{repo}' or snapshot.get('branch') != branch:
        raise RuntimeError('cache snapshot repository or branch mismatch')
    commit = snapshot.get('commit')
    if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise RuntimeError('cache snapshot has invalid commit')
    records = snapshot.get('files')
    if not isinstance(records, list) or not records:
        raise RuntimeError('cache snapshot has no file inventory')
    expected = {}
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError('cache snapshot has malformed file record')
        rel = record.get('path')
        size = record.get('size')
        digest = record.get('sha256')
        if not isinstance(rel, str) or PurePosixPath(rel).is_absolute() or any(part in {'', '.', '..'} for part in rel.split('/')):
            raise RuntimeError('cache snapshot has unsafe file path')
        if rel in expected or not isinstance(size, int) or size < 0 or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise RuntimeError('cache snapshot has invalid or duplicate file record')
        expected[rel] = (size, digest)
    actual = {}
    for path in target.rglob('*'):
        if path.name == SNAPSHOT_NAME and path == target / SNAPSHOT_NAME:
            continue
        if path.is_symlink():
            raise RuntimeError('cache contains symlink or non-file entry')
        if path.is_dir():
            continue
        if not path.is_file():
            raise RuntimeError('cache contains symlink or non-file entry')
        rel = path.relative_to(target).as_posix()
        data = path.read_bytes()
        actual[rel] = (len(data), sha256(data))
    if actual != expected:
        raise RuntimeError('cache file inventory mismatch')

def fetch_one(row: dict, cache: Path, *, delay: float, force: bool = False, revision: str | None = None) -> dict:
    owner, repo = repo_parts(row["source_repository_url"])
    if revision is not None and not re.fullmatch(r'[0-9a-f]{40}',revision):
        raise ValueError('Pinned revision must be a full commit SHA')
    slug = repo
    target = cache / slug
    existing = target / SNAPSHOT_NAME
    if target.is_symlink():
        raise RuntimeError(f"cache target is a symlink: {target}")
    if existing.is_file() and not force:
        try:
            snapshot = json.loads(existing.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            raise RuntimeError(f"invalid cache snapshot: {existing}") from exc
        validate_cached_snapshot(target, snapshot, owner, repo, row["default_branch"])
        if revision is not None and snapshot['commit'] != revision:
            raise RuntimeError('Cached revision differs from the reviewed manifest')
        return snapshot | {"cached": True}

    commit = revision or resolve_commit(owner, repo, row["default_branch"])
    archive_url = f"https://codeload.github.com/{owner}/{repo}/tar.gz/{commit}"
    archive = request(archive_url, accept="application/octet-stream")
    archive_hash = sha256(archive)
    fresh = target.with_name(target.name + ".partial")
    if fresh.is_symlink() or target.is_symlink():
        raise RuntimeError(f"cache extraction root is a symlink: {fresh}")
    if fresh.exists():
        shutil.rmtree(fresh)
    fresh.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        members = [m for m in tar.getmembers() if m.isfile() and source_member(m.name)]
        rels = [m.name.split("/", 1)[1] for m in members]
        if len(rels) != len(set(rels)):
            raise RuntimeError(f"duplicate source package path in {owner}/{repo}@{commit}")
        if not members:
            raise RuntimeError(f"no source package files found in {owner}/{repo}@{commit}")
        for member in members:
            rel = member.name.split("/", 1)[1]
            destination = fresh / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            if source is None:
                raise RuntimeError(f"unable to read archive member {member.name}")
            destination.write_bytes(source.read())
    snapshot = {
        "schema_version": 1,
        "title": row["source_title"],
        "author": row["source_author"],
        "repository": f"{owner}/{repo}",
        "repository_url": row["source_repository_url"],
        "branch": row["default_branch"],
        "commit": commit,
        "archive_sha256": archive_hash,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": file_inventory(fresh),
    }
    (fresh / SNAPSHOT_NAME).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if target.exists():
        shutil.rmtree(target)
    fresh.rename(target)
    if delay:
        time.sleep(delay)
    return snapshot | {"cached": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--manifest", type=Path, help="Reproduce exact revisions from a reviewed catalogue manifest")
    parser.add_argument("--delay", type=float, default=0.5, help="seconds between uncached repositories")
    parser.add_argument("--force", action="store_true", help="refresh packages even when a valid snapshot exists")
    args = parser.parse_args()
    rows = list(csv.DictReader(args.catalogue.open(encoding="utf-8", newline="")))
    if len(rows) != 66:
        raise SystemExit(f"expected 66 catalogue rows, found {len(rows)}")
    revisions = {}
    if args.manifest:
        books = json.loads(args.manifest.read_text(encoding='utf-8'))['books']
        revisions = {b['repository_url']: b['revision'] for b in books}
        if len(revisions) != len(books) or set(revisions) != {r['source_repository_url'] for r in rows}:
            raise SystemExit('Pinned manifest does not match the catalogue repositories')
    args.cache.mkdir(parents=True, exist_ok=True)
    results = []
    for index, row in enumerate(rows, 1):
        print(f"[{index}/{len(rows)}] {row['source_repository_url']}", flush=True)
        results.append(fetch_one(row, args.cache, delay=args.delay, force=args.force, revision=revisions.get(row['source_repository_url'])))
    manifest = {
        "schema_version": 1,
        "catalogue": str(args.catalogue.relative_to(ROOT)) if args.catalogue.is_relative_to(ROOT) else args.catalogue.as_posix(),
        "catalogue_sha256": sha256(args.catalogue.read_bytes()),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "packages": [{key: value for key, value in result.items() if key in {"repository", "branch", "commit", "archive_sha256", "source", "files", "cached"}} for result in results],
    }
    (args.cache / SNAPSHOT_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"cached {len(results)} repositories in {args.cache}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
