"""Fail-closed extraction of numbered members from one reviewed XHTML body.

The source document is first processed by :func:`extract_document`, so the
member parser inherits its structure, note, and source-conservation checks. It
then selects complete printed-number sections from the extracted text. The
returned HTML capture is a reconstructed excerpt containing only the selected
member lines; it is provenance-safe for a member work, but callers must retain
the original XHTML as the source input and record that reconstruction.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from sahityaras_ingest import SourceError
from sahityaras_text import LiteraryText, extract_document

_NUMBER_LINE = re.compile(r"(?m)^([०-९]+)\s*$")
_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _number(value: str) -> int:
    return int(value.translate(_DIGITS))


def _capture(title: str, text: str) -> bytes:
    ns = "http://www.w3.org/1999/xhtml"
    ET.register_namespace("", ns)
    root = ET.Element(f"{{{ns}}}html", {"lang": "ne"})
    head = ET.SubElement(root, f"{{{ns}}}head")
    ET.SubElement(head, f"{{{ns}}}meta", {"charset": "utf-8"})
    ET.SubElement(head, f"{{{ns}}}title").text = title
    body = ET.SubElement(root, f"{{{ns}}}body")
    heading = ET.SubElement(body, f"{{{ns}}}div", {"class": "chapter-title"})
    heading.text = title
    for block in text.rstrip("\n").split("\n\n"):
        paragraph = ET.SubElement(body, f"{{{ns}}}p")
        lines = block.splitlines()
        for index, line in enumerate(lines):
            if index:
                ET.SubElement(paragraph, f"{{{ns}}}br")
            paragraph.append(ET.Element(f"{{{ns}}}span"))
            paragraph[-1].text = line
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def extract_member(data: bytes, numbers: list[int], expected_total: int,
                   fallback_title: str) -> LiteraryText:
    """Return one contiguous numbered-member excerpt from reviewed XHTML.

    ``numbers`` must be a unique ascending contiguous range (so ``[4, 5]`` is
    valid). Every printed heading from 1 through ``expected_total`` must occur
    exactly once as a standalone Devanagari-number line. Missing, duplicated,
    reordered, empty, unsupported, or note-bearing source content fails closed.
    """
    if not isinstance(expected_total, int) or isinstance(expected_total, bool) or expected_total < 1:
        raise SourceError("expected_total must be positive")
    if not numbers or any(isinstance(n, bool) or not isinstance(n, int) for n in numbers):
        raise SourceError("numbers must be non-empty integers")
    if numbers != sorted(set(numbers)) or numbers != list(range(numbers[0], numbers[-1] + 1)):
        raise SourceError("numbers must be a unique ascending contiguous range")
    if numbers[0] < 1 or numbers[-1] > expected_total:
        raise SourceError("requested member number is outside expected sequence")
    source = extract_document(data, notes_approved=False, fallback_title=fallback_title)
    matches = list(_NUMBER_LINE.finditer(source.text))
    sequence = [_number(match.group(1)) for match in matches]
    expected = list(range(1, expected_total + 1))
    if sequence != expected:
        raise SourceError(f"member heading sequence drift: expected {expected}, got {sequence}")
    if source.text[:matches[0].start()].strip():
        raise SourceError("unaccounted text before the first member")
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source.text)
        if not source.text[match.end():end].strip():
            raise SourceError("numbered member has no literary body")
    starts = {n: match.start() for n, match in zip(sequence, matches)}
    selected_start = starts[numbers[0]]
    selected_end = starts[numbers[-1] + 1] if numbers[-1] < expected_total else len(source.text)
    selected = source.text[selected_start:selected_end].strip("\n")
    if not selected.strip() or not any(line.strip() for line in selected.splitlines()[1:]):
        raise SourceError("selected member has no literary body")
    title = fallback_title.strip()
    if not title:
        raise SourceError("fallback_title is required")
    text = selected + "\n"
    return LiteraryText(title, text, _capture(title, text), 0, source.continuation_count)
