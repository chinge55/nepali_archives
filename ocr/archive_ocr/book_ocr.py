"""Integrity checks binding a page-OCR job to one persistent book run."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import storage
from .book_workflow import BookRun, WorkflowError, sha256_file
from .models import Job, JobStatus


@dataclass(frozen=True)
class ValidatedOcrJob:
    job_id: str
    directory: Path
    pages: tuple[Path, ...]
    page_numbers: tuple[int, ...]
    review_path: Path


def validate_ocr_job(
    run: BookRun, job_id: str, jobs_root: Path | None = None
) -> ValidatedOcrJob:
    """Require a complete 300-dpi ensemble job for the exact run source."""
    root = jobs_root or storage.jobs_root()
    directory = root / job_id
    job_file = directory / "job.json"
    if not job_file.is_file():
        raise WorkflowError(f"unknown OCR job: {job_id}")
    job = Job.model_validate_json(job_file.read_bytes())
    if job.status != JobStatus.done:
        raise WorkflowError(f"OCR job is not complete: {job.status.value}")
    if job.dpi != 300:
        raise WorkflowError(f"OCR job must use 300 dpi, got {job.dpi}")
    if "ensemble" not in job.engines:
        raise WorkflowError("OCR job must include the ensemble engine")
    engine_run = next(
        (item for item in job.runs if item.engine == "ensemble"),
        None,
    )
    if engine_run is None or engine_run.error:
        raise WorkflowError("ensemble OCR run is absent or failed")
    source = directory / "source.pdf"
    if not source.is_file() or sha256_file(source) != run.source_sha256:
        raise WorkflowError("OCR job source does not match the book PDF checksum")
    pages = tuple(sorted((directory / "pages").glob("pg-*.png")))
    if not pages or job.page_count != len(pages) or engine_run.pages_done != len(pages):
        raise WorkflowError("OCR job page coverage is incomplete")
    numbers = tuple(int(path.stem.split("-")[1]) for path in pages)
    if numbers != tuple(range(1, len(pages) + 1)):
        raise WorkflowError("OCR job pages are not a complete one-based sequence")
    for image in pages:
        text = directory / "ocr" / "ensemble" / f"{image.stem}.txt"
        if not text.is_file():
            raise WorkflowError(f"ensemble text is missing for {image.name}")
    review = directory / "ocr" / "ensemble" / "review.json"
    if not review.is_file():
        raise WorkflowError("ensemble review.json is missing")
    return ValidatedOcrJob(job_id, directory, pages, numbers, review)


__all__ = ["ValidatedOcrJob", "validate_ocr_job"]
