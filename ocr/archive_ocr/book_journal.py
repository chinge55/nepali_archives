"""Durable journal and repository lock for crash-safe book promotion."""
from __future__ import annotations

import fcntl
import json
import os
import secrets
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


@contextmanager
def promotion_lock(repo_root: Path) -> Iterator[None]:
    lock_path = repo_root / ".git" / "ocr-book-promotion.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def journal_path(run_root: Path) -> Path:
    return run_root / "promotion-journal.json"


def load_journal(run_root: Path) -> dict[str, Any] | None:
    path = journal_path(run_root)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_journal(run_root: Path, payload: dict[str, Any]) -> None:
    path = journal_path(run_root)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(5)}.tmp")
    data = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


__all__ = ["journal_path", "load_journal", "promotion_lock", "write_journal"]
