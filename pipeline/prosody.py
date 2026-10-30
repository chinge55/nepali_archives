"""Reviewed metrical annotations, independent of literary text and genre."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from datetime import date
import re

ROOT = Path(__file__).resolve().parent.parent
POETIC_GENRES = {"kavita", "balkavita", "git", "bhajan", "gazal", "mahakavya", "khandakavya"}
FREE_VERSE = {"id": "muktachhanda", "name": "मुक्तछन्द", "kind": "free-verse"}


def load_metres(root: Path = ROOT) -> dict[str, dict]:
    path = Path(root) / "assets/chhanda/catalogue.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data["metres"]
    result = {entry["id"]: entry for entry in entries}
    if len(result) != len(entries) or FREE_VERSE["id"] in result:
        raise ValueError("duplicate or reserved metre id")
    for identifier, entry in result.items():
        if not re.fullmatch(r"[a-z0-9_-]+", identifier) or not entry.get("name"):
            raise ValueError("invalid metre catalogue entry")
        if "pattern" in entry and not re.fullmatch(r"[LG]{6,40}", entry["pattern"]):
            raise ValueError(f"invalid pattern for {identifier}")
        if "patterns" in entry:
            patterns = entry["patterns"]
            if ("pattern" in entry or not isinstance(patterns, list) or len(patterns) < 2
                    or not all(isinstance(p, str) and re.fullmatch(r"[LG]{6,40}", p) for p in patterns)
                    or len(set(patterns)) != len(patterns) or len({len(p) for p in patterns}) != 1):
                raise ValueError(f"invalid alternative patterns for {identifier}")
    return result


def text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_prosody(work: Path, metadata: dict, *, metres=None) -> list[str]:
    annotation = metadata.get("prosody")
    if annotation is None:
        return []
    if not isinstance(annotation, dict):
        return ["prosody must be an object"]
    errors = []
    metres = load_metres() if metres is None else metres
    genre = (metadata.get("genre") or [""])[0]
    if genre not in POETIC_GENRES:
        errors.append("prosody is only supported on poetic works")
    text_path = Path(work) / "text.txt"
    if not text_path.is_file():
        return errors + ["prosody requires text.txt"]
    text = text_path.read_text(encoding="utf-8")
    if annotation.get("text_sha256") != text_digest(text):
        errors.append("prosody text_sha256 is stale; review the annotation after text changes")
    kind = annotation.get("kind")
    status = annotation.get("status")
    if not isinstance(kind, str) or not isinstance(status, str):
        return errors + ["prosody kind and status must be strings"]
    identifiers = annotation.get("metres", [])
    if not isinstance(identifiers, list) or not all(isinstance(i, str) for i in identifiers):
        return errors + ["prosody.metres must be an array"]
    if len(set(identifiers)) != len(identifiers):
        errors.append("prosody.metres contains duplicates")
    for identifier in identifiers:
        if identifier not in metres:
            errors.append(f"prosody contains unknown metre {identifier!r}")
    if status == "reviewed":
        if kind == "single" and len(identifiers) != 1:
            errors.append("reviewed single-metre work requires exactly one metre")
        if kind == "mixed" and len(identifiers) < 2:
            errors.append("reviewed mixed work requires at least two metres")
        if kind == "free-verse" and identifiers:
            errors.append("free verse cannot have named metre tags")
        if kind == "unresolved":
            errors.append("unresolved prosody cannot be marked reviewed")
        if not annotation.get("evidence"):
            errors.append("reviewed prosody requires evidence")
    if status not in {"reviewed", "uncertain"}:
        errors.append("invalid prosody status")
    if kind not in {"single", "mixed", "free-verse", "unresolved"}:
        errors.append("invalid prosody kind")
    if "review_note" in annotation and (not isinstance(annotation["review_note"], str) or not annotation["review_note"].strip()):
        errors.append("prosody.review_note must be a nonempty string")
    try:
        date.fromisoformat(annotation.get("reviewed", ""))
    except (ValueError, TypeError):
        errors.append("prosody.reviewed must be an ISO date")
    passages = annotation.get("passages", [])
    if not isinstance(passages, list) or not all(isinstance(p, dict) for p in passages):
        return errors + ["prosody.passages must be an array of objects"]
    evidence_records = annotation.get("evidence", [])
    if not isinstance(evidence_records, list) or not all(isinstance(e, dict) for e in evidence_records):
        return errors + ["prosody.evidence must be an array of objects"]
    if kind != "mixed" and passages:
        errors.append("located passages are reserved for mixed works")
    passage_ids, starts, passage_metres = set(), set(), set()
    ranges = []
    for passage in passages:
        identifier = passage.get("id", "")
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-z0-9_-]+", identifier):
            errors.append("invalid prosody passage id")
            continue
        if not isinstance(passage.get("label"), str) or not passage["label"].strip():
            errors.append("prosody passage requires a label")
        if identifier in passage_ids:
            errors.append(f"duplicate prosody passage id {identifier!r}")
        passage_ids.add(identifier)
        metre = passage.get("metre")
        if not isinstance(metre, str):
            errors.append("passage metre must be an identifier")
            continue
        passage_metres.add(metre)
        if metre not in identifiers:
            errors.append(f"passage metre {metre!r} is absent from prosody.metres")
        start, end = passage.get("start", ""), passage.get("end", "")
        if not isinstance(start, str) or not isinstance(end, str):
            errors.append("passage start and end must be strings")
            continue
        lines = text.splitlines()
        if not start or start not in lines or lines.count(start) != 1:
            errors.append(f"passage {identifier!r} requires a unique complete starting line")
        if start in starts:
            errors.append("prosody passages must have distinct starting lines")
        starts.add(start)
        if not end or end not in lines or lines.count(end) != 1:
            errors.append(f"passage {identifier!r} requires a unique complete ending line")
        elif start in lines:
            if lines.index(end) < lines.index(start):
                errors.append(f"passage {identifier!r} ends before it starts")
            else:
                ranges.append((lines.index(start), lines.index(end)))
    if status == "reviewed" and kind == "mixed" and passage_metres != set(identifiers):
        errors.append("each mixed-work metre needs a located passage")
    for previous, current in zip(sorted(ranges), sorted(ranges)[1:]):
        if current[0] <= previous[1]:
            errors.append("reviewed metre passages must not overlap")
    source = metadata.get("source") or {}
    formats = metadata.get("formats") or {}
    if not isinstance(source, dict) or not isinstance(formats, dict):
        return errors + ["prosody requires valid source and formats objects"]
    editions = source.get("pdf_editions", [])
    if not isinstance(editions, list):
        return errors + ["prosody requires a valid source edition list"]
    editions = [e for e in editions if isinstance(e, dict)]
    known_files = {name for name in [source.get("html"), source.get("pdf"), formats.get("pdf")] if isinstance(name, str)}
    known_files.update(e["file"] for e in editions if isinstance(e.get("file"), str))
    text_info = metadata.get("text")
    if isinstance(text_info, dict) and text_info.get("extraction_method") == "manual":
        known_files.add("text.txt")
    source_hashes = {}
    for evidence in evidence_records:
        filename = evidence.get("file", "")
        if not isinstance(filename, str):
            errors.append("prosody evidence filename must be a string")
            continue
        html_root = Path(work) / source["html"] if isinstance(source.get("html"), str) else None
        in_html_tree = html_root is not None and html_root.is_dir() and (Path(work) / filename).resolve().is_relative_to(html_root.resolve())
        if filename not in known_files and not in_html_tree:
            errors.append("prosody evidence must refer to a declared source")
        candidate = Path(work) / filename
        if not filename or Path(filename).is_absolute() or candidate.is_symlink() or not candidate.resolve().is_relative_to(Path(work).resolve()) or not candidate.is_file():
            errors.append("prosody evidence file must be an existing file within the work")
        else:
            try:
                if filename not in source_hashes:
                    source_hashes[filename] = hashlib.sha256(candidate.read_bytes()).hexdigest()
                if evidence.get("sha256") != source_hashes[filename]:
                    errors.append("prosody evidence sha256 does not match its source file")
            except OSError:
                errors.append("cannot read prosody evidence file")
        if not isinstance(evidence.get("basis"), str) or evidence["basis"] not in {"source-label", "metrical-reading", "editorial-reading"}:
            errors.append("invalid prosody evidence basis")
        page_start, page_end = evidence.get("page_start"), evidence.get("page_end")
        if page_start is not None or page_end is not None:
            valid = all(isinstance(p, int) and not isinstance(p, bool) for p in (page_start, page_end))
            bound = next((e["page_count"] for e in editions if e.get("file") == filename and isinstance(e.get("page_count"), int)), None)
            if not valid or not 1 <= page_start <= page_end or bound is not None and page_end > bound:
                errors.append("invalid prosody evidence page range")
        if not evidence.get("locator") or not evidence.get("note"):
            errors.append("prosody evidence requires a locator and review note")
    return errors


def published_prosody(metadata: dict, text: str) -> dict | None:
    annotation = metadata.get("prosody")
    if not isinstance(annotation, dict) or annotation.get("status") != "reviewed":
        return None
    if annotation.get("text_sha256") != text_digest(text):
        return None
    if annotation.get("kind") not in {"single", "mixed", "free-verse"}:
        return None
    return annotation


def published_metres(annotation: dict | None) -> list[str]:
    if not annotation:
        return []
    return [FREE_VERSE["id"]] if annotation["kind"] == "free-verse" else annotation["metres"]


def annotation_anchors(annotation: dict | None, text: str) -> dict[str, str]:
    return {p["start"]: "chhanda-" + p["id"] for p in (annotation or {}).get("passages", []) if p["start"] in text.splitlines()}
