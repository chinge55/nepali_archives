"""Explicit build inputs and deterministic output inspection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path


def npt_today() -> date:
    """Return today's date in Nepal time without requiring a timezone database."""
    return (datetime.now(timezone.utc) + timedelta(hours=5, minutes=45)).date()


@dataclass(frozen=True)
class BuildContext:
    """All paths and variable inputs used by one site build."""

    root: Path
    archives: Path
    site: Path
    archive_base: str = ""
    build_date: date = date.min

    @classmethod
    def for_root(
        cls,
        root: Path,
        *,
        output_dir: Path | None = None,
        archive_base: str = "",
        build_date: date | None = None,
    ) -> "BuildContext":
        root = Path(root).resolve()
        site = Path(output_dir).resolve() if output_dir else root / "site"
        return cls(
            root=root,
            archives=root / "archives",
            site=site,
            archive_base=archive_base,
            build_date=build_date or npt_today(),
        )


@dataclass(frozen=True)
class BuildStats:
    """Facts returned by a successful build and printed by the CLI."""

    pages: int
    works: int
    authors: int
    genres: int
    collections: int
    search_index_bytes: int


@dataclass(frozen=True)
class OutputManifest:
    """Content-only manifest of a generated tree."""

    files: tuple[dict[str, object], ...]
    total_bytes: int
    sha256: str


def output_manifest(root: Path) -> OutputManifest:
    """Hash every generated file in stable path order.

    Timestamps and filesystem metadata are deliberately excluded so manifests
    compare generated content rather than the machine that produced it.
    """
    root = Path(root)
    rows: list[dict[str, object]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        data = path.read_bytes()
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    encoded = json.dumps(
        rows, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return OutputManifest(
        files=tuple(rows),
        total_bytes=sum(int(row["size"]) for row in rows),
        sha256=hashlib.sha256(encoded).hexdigest(),
    )
