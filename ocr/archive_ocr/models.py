"""Pydantic models — the shared vocabulary of the OCR infrastructure.

Everything the API returns and everything persisted to job.json is one of
these models, so the on-disk format and the wire format never drift apart.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, Enum):
    queued = "queued"
    rendering = "rendering"      # PDF -> page PNGs
    running = "running"          # engines reading pages
    done = "done"
    failed = "failed"


class EngineRun(BaseModel):
    """One engine's pass over a job's pages."""
    engine: str
    pages_done: int = 0
    seconds: float = 0.0
    error: str | None = None


class Job(BaseModel):
    """A digitization job: one source PDF, rendered once, read by N engines."""
    id: str
    source_name: str
    status: JobStatus = JobStatus.queued
    created_at: datetime = Field(default_factory=utcnow)
    engines: list[str]
    dpi: int
    page_count: int | None = None
    runs: list[EngineRun] = []
    error: str | None = None


class PageText(BaseModel):
    """One engine's reading of one page."""
    page: int
    engine: str
    text: str


class LineDisagreement(BaseModel):
    """Two engines read the same printed line differently.

    These are the adjudication queue: a human (or later, an arbitration
    agent) resolves them against the page image. Everything the engines
    agree on is near-certain and needs no review.
    """
    page: int
    engine_a: str
    engine_b: str
    line_a: str
    line_b: str
    distance: int
    oov_a: list[str] = []   # line_a tokens unknown to the Nepali lexicon
    oov_b: list[str] = []


class PageReview(BaseModel):
    page: int
    lines: int
    agreeing: int
    review: list[LineDisagreement]


class ReviewReport(BaseModel):
    """The ensemble engine's confidence artifact (review.json)."""
    primary: str
    shadow: str
    lines: int
    agreeing: int
    pages: list[PageReview]
