"""Ensemble engine — the archive's scanning formula (2026-07-21 benchmark):

    Surya-2 reads the page (best accuracy: 86% exact lines / ~0.8% CER vs
    gold, ~3x fewer character errors than Tesseract).
    Tesseract shadows it (fails *differently* — e.g. it reads झैँ where
    Surya confuses झ→क).
    Lines both agree on are near-certain. Lines they disagree on become
    the REVIEW QUEUE (review.json beside the text), annotated with
    lexicon out-of-vocabulary tokens to help rank likely misreads.

The final text is Surya's reading VERBATIM — the ensemble never silently
substitutes (a shadow engine can be confidently wrong too). Corrections
happen at adjudication, against the page image, by a human or an
arbitration agent working through review.json.
"""
from __future__ import annotations

from pathlib import Path

from ..compare import disagreements
from ..config import settings
from ..lexicon import oov_tokens
from ..models import PageReview, ReviewReport
from .base import OcrEngine

PRIMARY = settings.primary_engine
SHADOW = settings.shadow_engine


def combine(page: int, primary_text: str, shadow_text: str) -> PageReview:
    """Pure combine step for one page: primary vs shadow -> review entries."""
    total, agree, diffs = disagreements(page, PRIMARY, primary_text,
                                        SHADOW, shadow_text)
    for d in diffs:
        d.oov_a = oov_tokens(d.line_a)
        d.oov_b = oov_tokens(d.line_b)
    return PageReview(page=page, lines=total, agreeing=agree, review=diffs)


class EnsembleEngine(OcrEngine):
    name = "ensemble"

    def _engines(self) -> tuple[OcrEngine, OcrEngine]:
        from . import get_engine  # late import: registry contains this module
        return get_engine(PRIMARY), get_engine(SHADOW)

    def available(self) -> tuple[bool, str]:
        parts = []
        for engine in self._engines():
            ok, detail = engine.available()
            if not ok:
                return False, f"{engine.name} unavailable: {detail}"
            parts.append(engine.name)
        return True, f"{PRIMARY} (text) + {SHADOW} (shadow) -> review.json"

    def ocr_pages(self, images: list[Path], out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        primary, shadow = self._engines()

        # sub-engine artifacts go to sibling dirs, so the standard layout
        # (ocr/<engine>/pg-NNN.txt) holds and both raw readings stay queryable
        primary_dir = out_dir.parent / PRIMARY
        shadow_dir = out_dir.parent / SHADOW
        primary.ocr_pages(images, primary_dir)
        shadow.ocr_pages(images, shadow_dir)

        pages: list[PageReview] = []
        for image in images:
            page_no = int(image.stem.split("-")[1])
            primary_text = (primary_dir / f"{image.stem}.txt").read_text(encoding="utf-8")
            shadow_text = (shadow_dir / f"{image.stem}.txt").read_text(encoding="utf-8")
            # deliverable text = primary reading, verbatim
            (out_dir / f"{image.stem}.txt").write_text(primary_text, encoding="utf-8")
            pages.append(combine(page_no, primary_text, shadow_text))

        report = ReviewReport(
            primary=PRIMARY, shadow=SHADOW,
            lines=sum(p.lines for p in pages),
            agreeing=sum(p.agreeing for p in pages),
            pages=pages)
        (out_dir / "review.json").write_text(
            report.model_dump_json(indent=2), encoding="utf-8")
