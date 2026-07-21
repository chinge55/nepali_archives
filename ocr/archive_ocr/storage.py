"""Job artifact layout on disk. One directory per job, everything inside:

    <work_dir>/jobs/<job_id>/
        source.pdf                  the uploaded document
        job.json                    Job model (status, engines, timings)
        pages/pg-001.png ...        rendered page images (source of truth)
        ocr/<engine>/pg-001.txt ... one text file per page per engine

Plain files, atomic json writes, no database: a job directory is complete,
portable and inspectable by hand. Server restarts lose nothing.
"""
from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path

from .config import settings
from .models import Job


def jobs_root() -> Path:
    root = settings.work_dir / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def new_job_id(source_name: str) -> str:
    """Readable, sortable, collision-safe: <slug>-<6 hex>."""
    slug = re.sub(r"[^a-z0-9]+", "-", Path(source_name).stem.lower()).strip("-")[:40]
    return f"{slug or 'job'}-{secrets.token_hex(3)}"


def job_dir(job_id: str) -> Path:
    return jobs_root() / job_id


def pages_dir(job_id: str) -> Path:
    return job_dir(job_id) / "pages"


def engine_dir(job_id: str, engine: str) -> Path:
    return job_dir(job_id) / "ocr" / engine


def save_job(job: Job) -> None:
    """Atomic write so a crash mid-save never corrupts job.json."""
    path = job_dir(job.id) / "job.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(job.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_job(job_id: str) -> Job | None:
    path = job_dir(job_id) / "job.json"
    if not path.exists():
        return None
    return Job.model_validate(json.loads(path.read_text(encoding="utf-8")))


def list_jobs() -> list[Job]:
    jobs = [j for d in jobs_root().iterdir() if d.is_dir()
            and (j := load_job(d.name)) is not None]
    return sorted(jobs, key=lambda j: j.created_at, reverse=True)


def page_image_paths(job_id: str) -> list[Path]:
    return sorted(pages_dir(job_id).glob("pg-*.png"))


def page_text(job_id: str, engine: str, page: int) -> str | None:
    for width in (3, 2):  # pdftoppm zero-pads to 3 digits for books >= 100 pp
        path = engine_dir(job_id, engine) / f"pg-{page:0{width}d}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
    return None


def engine_page_numbers(job_id: str, engine: str) -> list[int]:
    return sorted(int(p.stem.split("-")[1]) for p in
                  engine_dir(job_id, engine).glob("pg-*.txt"))
