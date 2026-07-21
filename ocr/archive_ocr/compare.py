"""Text comparison: normalization, line alignment, CER.

This is the measurement core, formalized from the hand-run benchmark of
2026-07-21 (see ocr/README.md). Two hard-won rules live here:

* ZWNJ/ZWJ are stripped before any comparison — they are engine idiom
  (Tesseract emits them, VLMs don't), invisible in print, and comparing
  them silently biases scores toward whichever engine produced the
  reference text.
* Margin श्लोक numbers that layout-aware engines inline into a verse line
  ("३७ सुषुप्त विपिन…") are split off before line matching, so a layout
  choice is never counted as a reading error.
"""
from __future__ import annotations

import re

from .models import LineDisagreement

_ZERO_WIDTH = re.compile(r"[‌‍]")
_LEADING_NUMERAL = re.compile(r"^[०-९0-9]{1,4}\s+")
_MIN_LINE_CHARS = 6  # shorter lines are page furniture / bare numerals


def normalize_line(line: str) -> str:
    line = _ZERO_WIDTH.sub("", line).strip()
    return _LEADING_NUMERAL.sub("", line)


def content_lines(text: str) -> list[str]:
    lines = (normalize_line(l) for l in text.splitlines())
    return [l for l in lines if len(l) > _MIN_LINE_CHARS]


def edit_distance(a: str, b: str, cap: int | None = None) -> int:
    """Levenshtein distance; stops early at `cap` when given."""
    if a == b:
        return 0
    if cap is not None and abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        best = len(b) + i
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
            best = min(best, cur[-1])
        if cap is not None and best > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def best_match(line: str, candidates: list[str]) -> tuple[str | None, int]:
    """The candidate line closest to `line`, within a sane tolerance."""
    tolerance = max(3, len(line) // 4)
    found, found_d = None, tolerance + 1
    for cand in candidates:
        if abs(len(cand) - len(line)) > max(15, len(line) // 2):
            continue
        d = edit_distance(line, cand, cap=found_d)
        if d < found_d:
            found, found_d = cand, d
    return found, found_d if found is not None else tolerance + 1


def score_against(reference: str, hypothesis: str) -> tuple[int, int, int, float]:
    """(lines, exact, matched, cer%) of hypothesis lines vs a reference text.

    CER is computed only over matched lines: unmatched lines are usually a
    structural difference (dropped furniture, split lines), not misreads,
    and folding them into CER would swamp the character signal.
    """
    ref_lines = content_lines(reference)
    hyp_lines = content_lines(hypothesis)
    exact = matched = err_chars = base_chars = 0
    ref_set = set(ref_lines)
    for line in hyp_lines:
        if line in ref_set:
            exact += 1
            base_chars += len(line)
            continue
        cand, d = best_match(line, ref_lines)
        if cand is not None:
            matched += 1
            err_chars += d
            base_chars += max(len(line), len(cand))
    cer = 100.0 * err_chars / base_chars if base_chars else 0.0
    return len(hyp_lines), exact, matched, round(cer, 2)


def disagreements(page: int, engine_a: str, text_a: str,
                  engine_b: str, text_b: str) -> tuple[int, int, list[LineDisagreement]]:
    """Line-level differences between two engines on one page.

    Returns (total_a_lines, agreeing, diffs). Agreement means an exact
    normalized match — those lines are near-certain and skip review.
    """
    lines_a = content_lines(text_a)
    lines_b = content_lines(text_b)
    set_b = set(lines_b)
    agree = 0
    diffs: list[LineDisagreement] = []
    for line in lines_a:
        if line in set_b:
            agree += 1
            continue
        cand, d = best_match(line, lines_b)
        diffs.append(LineDisagreement(
            page=page, engine_a=engine_a, engine_b=engine_b,
            line_a=line, line_b=cand or "(no matching line)",
            distance=d if cand is not None else -1))
    return len(lines_a), agree, diffs
