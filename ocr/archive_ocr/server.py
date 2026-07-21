"""FastAPI server — the OCR service: a PDF goes in, text comes out.

    python -m archive_ocr serve        # API on :8100

Deliberately small: submit a job, watch its status, fetch the text.
Quality tooling (gold pages, engine comparison) lives offline in
compare.py / tests — not in the service surface. No auth yet
(single-operator); routes are shaped so auth can wrap later.
"""
from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from . import jobs, storage
from .engines import ENGINES
from .models import Job, PageText, ReviewReport

app = FastAPI(
    title="नेपाली अभिलेख OCR",
    description="Digitization service for the Nepali Archives.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    engines = {name: dict(zip(("available", "detail"), engine.available()))
               for name, engine in ENGINES.items()}
    return {"ok": any(e["available"] for e in engines.values()), "engines": engines}


@app.post("/jobs", response_model=Job, status_code=201)
async def create_job(
    file: UploadFile = File(..., description="source PDF"),
    engines: str = Form("ensemble", description="comma-separated engine names"),
    dpi: int | None = Form(None),
    first_page: int | None = Form(None),
    last_page: int | None = Form(None),
) -> Job:
    names = [e.strip() for e in engines.split(",") if e.strip()]
    try:
        return jobs.submit(await file.read(), file.filename or "upload.pdf",
                           names, dpi, first_page, last_page)
    except KeyError as exc:
        raise HTTPException(422, str(exc)) from None


@app.get("/jobs", response_model=list[Job])
def list_jobs() -> list[Job]:
    return storage.list_jobs()


def _job_or_404(job_id: str) -> Job:
    job = storage.load_job(job_id)
    if job is None:
        raise HTTPException(404, f"no such job: {job_id}")
    return job


@app.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    return _job_or_404(job_id)


@app.get("/jobs/{job_id}/pages/{page}", response_model=PageText)
def get_page(job_id: str, page: int, engine: str = "ensemble") -> PageText:
    _job_or_404(job_id)
    text = storage.page_text(job_id, engine, page)
    if text is None:
        raise HTTPException(404, f"no page {page} for engine {engine}")
    return PageText(page=page, engine=engine, text=text)


@app.get("/jobs/{job_id}/text")
def get_text(job_id: str, engine: str = "ensemble") -> dict:
    """The whole document in page order — the service's main deliverable."""
    _job_or_404(job_id)
    numbers = storage.engine_page_numbers(job_id, engine)
    if not numbers:
        raise HTTPException(404, f"no output for engine {engine}")
    text = "\n".join(storage.page_text(job_id, engine, n) or "" for n in numbers)
    return {"job_id": job_id, "engine": engine, "pages": len(numbers), "text": text}


@app.get("/jobs/{job_id}/review", response_model=ReviewReport)
def get_review(job_id: str) -> ReviewReport:
    """The ensemble's confidence artifact: which lines need human eyes."""
    _job_or_404(job_id)
    path = storage.engine_dir(job_id, "ensemble") / "review.json"
    if not path.exists():
        raise HTTPException(404, "no review.json — job did not run the ensemble engine")
    return ReviewReport.model_validate_json(path.read_text(encoding="utf-8"))
