"""Job orchestration: submit -> render -> run engines -> done.

Execution model: a single-worker thread pool. OCR jobs are GPU/CPU heavy
and strictly sequential per book anyway; one at a time keeps the machine
responsive and the code simple. State transitions are persisted to
job.json at every step, so `GET /jobs/{id}` is always truthful and a
server restart loses nothing (an interrupted job just shows its last
persisted state).
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import pdf, storage
from .config import settings
from .engines import get_engine
from .models import EngineRun, Job, JobStatus

log = logging.getLogger("archive_ocr")

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr-job")


def submit(source: bytes, source_name: str, engines: list[str],
           dpi: int | None = None,
           first_page: int | None = None, last_page: int | None = None) -> Job:
    """Persist the upload, create the job, queue it for execution."""
    for name in engines:
        get_engine(name)  # unknown engine -> KeyError before anything is written
    job = Job(id=storage.new_job_id(source_name), source_name=source_name,
              engines=engines, dpi=dpi or settings.dpi)
    job_dir = storage.job_dir(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "source.pdf").write_bytes(source)
    storage.save_job(job)
    _executor.submit(_run, job.id, first_page, last_page)
    return job


def _run(job_id: str, first_page: int | None, last_page: int | None) -> None:
    job = storage.load_job(job_id)
    if job is None:
        return
    source = storage.job_dir(job_id) / "source.pdf"
    try:
        job.status = JobStatus.rendering
        storage.save_job(job)
        job.page_count = pdf.page_count(source)
        images = pdf.render_pages(source, storage.pages_dir(job_id), job.dpi,
                                  first_page, last_page)

        job.status = JobStatus.running
        storage.save_job(job)
        for name in job.engines:
            run = EngineRun(engine=name)
            job.runs.append(run)
            started = time.monotonic()
            try:
                get_engine(name).ocr_pages(images, storage.engine_dir(job_id, name))
                run.pages_done = len(images)
            except Exception as exc:  # noqa: BLE001 — a failed engine must not kill the job
                run.error = str(exc)
                log.exception("engine %s failed on job %s", name, job_id)
            run.seconds = round(time.monotonic() - started, 1)
            storage.save_job(job)

        ran_ok = [r for r in job.runs if r.error is None]
        job.status = JobStatus.done if ran_ok else JobStatus.failed
        if not ran_ok:
            job.error = "every engine failed — see runs[].error"
    except Exception as exc:  # noqa: BLE001 — job-level failure
        job.status = JobStatus.failed
        job.error = str(exc)
        log.exception("job %s failed", job_id)
    storage.save_job(job)
