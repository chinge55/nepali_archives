"""Deterministic coordinator actions for preflight and local ensemble OCR."""
from __future__ import annotations

import time
from pathlib import Path

from . import jobs, pdf, storage
from .book_workflow import BookWorkflow, InvalidTransition, WorkflowError, sha256_file
from .models import JobStatus


def complete_preflight(
    workflow: BookWorkflow,
    run_id: str,
    claim_token: str,
) -> dict[str, object]:
    run = workflow.load_run(run_id)
    source = Path(run.source_path)
    if not source.is_file() or sha256_file(source) != run.source_sha256:
        raise WorkflowError("source PDF changed or disappeared after initialization")
    if not workflow.is_known_author(run.author_id):
        raise InvalidTransition("author onboarding is incomplete")
    pages = pdf.page_count(source)
    if pages < 1:
        raise WorkflowError("source PDF has no pages")
    report = {
        "source_path": str(source),
        "source_sha256": run.source_sha256,
        "pages": pages,
        "author_id": run.author_id,
        "author_known": True,
        "same_source_runs": [
            other.id
            for other in workflow.find_by_source(run.source_sha256)
            if other.id != run.id
        ],
    }
    workflow.complete_task(
        run_id, "preflight", claim_token, result=report
    )
    return report


def complete_ocr(
    workflow: BookWorkflow,
    run_id: str,
    claim_token: str,
) -> dict[str, object]:
    """Reuse a bound job or run the local ensemble, then complete OCR."""
    workflow.renew_claim(run_id, "ocr", claim_token, lease_seconds=86_400)
    run = workflow.load_run(run_id)
    job_id = run.ocr_job_id
    if job_id is None:
        if workflow.ocr_jobs_root != storage.jobs_root().resolve():
            raise WorkflowError(
                "automatic OCR uses configured OCR_WORK_DIR; attach a job for custom roots"
            )
        source = Path(run.source_path)
        submitted = jobs.submit(
            source.read_bytes(),
            source.name,
            ["ensemble"],
            dpi=300,
        )
        job_id = submitted.id
        while True:
            current = storage.load_job(job_id)
            if current is None:
                raise WorkflowError("submitted OCR job disappeared")
            if current.status in {JobStatus.done, JobStatus.failed}:
                break
            time.sleep(2)
        if current.status != JobStatus.done:
            raise WorkflowError(current.error or "ensemble OCR failed")
        workflow.set_ocr_job(run_id, job_id)
    else:
        # Revalidates exact source, 300 dpi, ensemble success, and page coverage.
        workflow.set_ocr_job(run_id, job_id)
    workflow.complete_task(run_id, "ocr", claim_token)
    completed = workflow.load_run(run_id)
    return {
        "run_id": run_id,
        "ocr_job_id": completed.ocr_job_id,
        "reused": run.ocr_job_id is not None,
    }


__all__ = ["complete_ocr", "complete_preflight"]
