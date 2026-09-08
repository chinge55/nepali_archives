"""Safe, deterministic extraction of page ranges from source PDFs.

PyMuPDF is deliberately imported only when slicing or auditing is requested;
the ordinary archive pipeline does not require the optional dependency.
"""

from __future__ import annotations

import hashlib
import io
import math
from pathlib import Path
from typing import Any


def _fitz():
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - exercised by callers
        raise RuntimeError("PDF slicing requires the optional PyMuPDF dependency") from exc
    return fitz


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value



def _citation_rects(page, scope, fitz):
    """Resolve one visible bracketed numeral citation inside a reviewed scope."""
    expanded = fitz.Rect(scope)
    expanded.x0 -= 2; expanded.y0 -= 2; expanded.x1 += 2; expanded.y1 += 2
    chars = []
    for block in page.get_text("rawdict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                chars.extend(span.get("chars", []))
    candidates = []
    digits = set("0123456789०१२३४५६७८९")
    i = 0
    while i < len(chars):
        if chars[i].get("c") != "[":
            i += 1
            continue
        j = i + 1
        while j < len(chars) and chars[j].get("c") in digits:
            j += 1
        if j > i + 1 and j < len(chars) and chars[j].get("c") == "]":
            group = chars[i:j + 1]
            boxes = [fitz.Rect(ch["bbox"]) for ch in group]
            union = boxes[0]
            for box in boxes[1:]:
                union |= box
            center = fitz.Point((union.x0 + union.x1) / 2, (union.y0 + union.y1) / 2)
            if expanded.contains(center):
                candidates.append((i, j, group, boxes))
            i = j + 1
        else:
            i += 1
    if len(candidates) != 1:
        raise ValueError("citation redaction must identify exactly one bracketed numeral")
    start, end, group, boxes = candidates[0]
    target_indexes = set(range(start, end + 1))
    protected = [fitz.Rect(ch["bbox"]) for n, ch in enumerate(chars) if n not in target_indexes]
    resolved = []
    for box in boxes:
        # Use the glyph hit box itself. Adjacent body glyphs are protected by
        # positive-area intersection checks; touching edges are safe and common
        # in the source PDF's extracted coordinates.
        tiny = fitz.Rect(box)
        if tiny.is_empty or any(tiny.intersects(other) for other in protected):
            raise ValueError("citation redaction overlaps protected text")
        resolved.append(tiny)
    return resolved

def _validate_plan(source: Path, pages: list[dict[str, Any]], fitz):
    if not isinstance(pages, list) or not pages:
        raise ValueError("pages must be a non-empty list")
    src = fitz.open(str(source))
    try:
        seen: set[int] = set()
        normalized = []
        for item in pages:
            if not isinstance(item, dict):
                raise ValueError("each page plan must be an object")
            number = _positive_int(item.get("page"), "page")
            if number > src.page_count:
                raise ValueError(f"page {number} is outside source ({src.page_count} pages)")
            if number in seen:
                raise ValueError(f"duplicate page {number}")
            seen.add(number)
            raw_redactions = item.get("redactions", [])
            if raw_redactions is None:
                raw_redactions = []
            if not isinstance(raw_redactions, list):
                raise ValueError("redactions must be a list")
            page = src.load_page(number - 1)
            rects = []
            for redaction in raw_redactions:
                if not isinstance(redaction, dict) or not isinstance(redaction.get("reason"), str) or not redaction["reason"].strip():
                    raise ValueError("each redaction requires a non-empty reason")
                coords = redaction.get("rect")
                if not isinstance(coords, (list, tuple)) or len(coords) != 4:
                    raise ValueError("redaction rect must contain four coordinates")
                if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in coords):
                    raise ValueError("redaction coordinates must be finite numbers")
                x0, y0, x1, y1 = map(float, coords)
                bounds = page.rect
                if not (x0 < x1 and y0 < y1) or x0 < bounds.x0 or y0 < bounds.y0 or x1 > bounds.x1 or y1 > bounds.y1:
                    raise ValueError(f"invalid redaction rectangle on page {number}")
                kind = redaction.get("kind", "full")
                if kind not in {"full", "citation"}:
                    raise ValueError("redaction kind must be full or citation")
                scope = fitz.Rect(x0, y0, x1, y1)
                resolved = (_citation_rects(page, scope, fitz)
                            if kind == "citation" else [scope])
                rects.extend((kind, rect, redaction["reason"].strip()) for rect in resolved)
            normalized.append((number, rects))
        return src, normalized
    except Exception:
        src.close()
        raise


def slice_pdf(source: Path, pages: list[dict[str, Any]], *, title: str, author: str) -> bytes:
    """Return a sanitized PDF containing the requested source pages.

    Pages are 1-based and may be discontiguous, but may not repeat. Redaction
    rectangles are source-page coordinates; the underlying text/image content
    is removed before serialization.
    """
    fitz = _fitz()
    source = Path(source)
    src, normalized = _validate_plan(source, pages, fitz)
    out = fitz.open()
    try:
        last_index = len(normalized) - 1
        for index, (number, _rects) in enumerate(normalized):
            out.insert_pdf(src, from_page=number - 1, to_page=number - 1,
                           links=False, annots=False, widgets=False,
                           final=(index == last_index))
        # Apply redactions after insertion, using the corresponding output page.
        for out_index, (_number, rects) in enumerate(normalized):
            page = out.load_page(out_index)
            for _kind, rect, _reason in rects:
                page.add_redact_annot(rect, fill=(1, 1, 1))
            if rects:
                page.apply_redactions(images=2, graphics=2, text=0)
            # Defensive scrub for any objects introduced by source-page content.
            for link in list(page.get_links()):
                page.delete_link(link)
            for annot in list(page.annots() or []):
                page.delete_annot(annot)
        out.scrub(attached_files=True, clean_pages=False, embedded_files=True,
                  hidden_text=False, javascript=True, metadata=True,
                  redactions=True, redact_images=2, remove_links=True,
                  reset_fields=True, reset_responses=True, thumbnails=True,
                  xml_metadata=True)
        out.set_metadata({"format": "PDF 1.7", "title": str(title), "author": str(author),
                          "subject": "", "keywords": "", "creator": "", "producer": "",
                          "creationDate": "", "modDate": ""})
        buffer = io.BytesIO()
        out.save(buffer, garbage=4, clean=0, deflate=1, deflate_images=1,
                 no_new_id=True, incremental=False, encryption=fitz.PDF_ENCRYPT_NONE,
                 preserve_metadata=True)
        return buffer.getvalue()
    finally:
        out.close()
        src.close()


def audit_pdf(path: Path) -> dict[str, Any]:
    """Return stable basic facts for a generated PDF."""
    fitz = _fitz()
    data = Path(path).read_bytes()
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        annotations = 0
        links = 0
        for page in doc:
            annotations += sum(1 for _ in (page.annots() or []))
            links += len(page.get_links())
        # Inspect parsed PDF dictionaries so ordinary text such as “/JS” in
        # a content stream cannot be mistaken for document JavaScript.
        javascript = 0
        actions = 0
        action_keys = {"OpenAction", "AA", "Launch", "SubmitForm", "GoToR"}
        javascript_keys = {"JavaScript", "JS"}
        for xref in range(1, doc.xref_length()):
            try:
                keys = set(doc.xref_get_keys(xref))
            except Exception:
                continue
            javascript += len(keys & javascript_keys)
            actions += len(keys & action_keys)
            if "S" in keys:
                try:
                    value = doc.xref_get_key(xref, "S")[1]
                except Exception:
                    value = ""
                if any(token in value for token in ("JavaScript", "Launch", "SubmitForm", "GoToR")):
                    actions += 1
        return {"page_count": doc.page_count, "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data), "annotations": annotations, "links": links,
                "attachments": len(doc.embfile_names()), "javascript": javascript,
                "actions": actions}
    finally:
        doc.close()
