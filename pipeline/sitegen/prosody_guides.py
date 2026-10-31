"""Short, optional reading guides, separate from the preserved literary texts."""

import json
from pathlib import Path
from urllib.parse import urlsplit

from prosody import published_metres

from .text import esc


def load_guides(root, metres):
    guides = json.loads((Path(root) / "assets/chhanda/guides.json").read_text(encoding="utf-8"))["guides"]
    if set(guides) != set(metres):
        raise ValueError("Reading guides must cover the metre catalogue and free verse")
    for identifier, guide in guides.items():
        if (not guide.get("description") or not guide.get("structure")
                or not guide.get("reading") or not all(isinstance(s, str) and s.strip() for s in guide["reading"])):
            raise ValueError(f"Incomplete reading guide: {identifier}")
        groups = guide.get("groups", [])
        patterns = [metres[identifier]["pattern"]] if "pattern" in metres[identifier] else metres[identifier].get("patterns", [])
        if patterns and (not groups or any(type(n) is not int or n < 1 for n in groups)
                         or any(sum(groups) != len(pattern) for pattern in patterns)):
            raise ValueError(f"Reading groups disagree with metre pattern: {identifier}")
        for reference in guide.get("references", []):
            if urlsplit(reference["url"]).scheme != "https" or not reference.get("label"):
                raise ValueError(f"Invalid guide reference: {identifier}")
        example = guide.get("example", {})
        if (not example.get("work", "").startswith("archives/authors/")
                or not example.get("lines") or len(example["lines"]) > 2
                or not example.get("note")
                or len(example.get("reading", [])) != len(example["lines"])
                or any("".join(groups) != line for groups, line in zip(example["reading"], example["lines"]))):
            raise ValueError(f"Invalid reading example: {identifier}")
    return guides


def _pattern_html(metre, guide):
    patterns = [metre["pattern"]] if "pattern" in metre else metre.get("patterns", [])
    rows = []
    for pattern in patterns:
        offset, groups = 0, []
        for size in guide["groups"]:
            chunk = pattern[offset:offset + size]
            groups.append('<span>' + " ".join("ग" if w == "G" else "ल" for w in chunk) + '</span>')
            offset += size
        rows.append('<p class="metre-pattern" aria-label="लघु–गुरुको क्रम">' + '<span aria-hidden="true">·</span>'.join(groups) + '</p>')
    return "".join(rows)


def _example_html(identifier, guide, catalogue):
    example = guide["example"]
    record = next((row for row in catalogue.records if row[0]["path"] == example["work"]), None)
    # A smaller deployment may omit the example work; the guide still stands alone.
    if record is None:
        return ""
    work, meta, text = record
    annotation = catalogue.extras[work["path"]]["prosody"]
    if identifier not in published_metres(annotation):
        raise ValueError(f"Example work is no longer reviewed in {identifier}: {work['path']}")
    excerpt = "\n".join(example["lines"])
    if excerpt not in text:
        raise ValueError(f"Reading example differs from source text: {identifier}")
    href = Path(work["path"]).relative_to("archives").as_posix() + "/"
    if annotation["kind"] == "mixed":
        for target in catalogue.extras[work["path"]].get("prosody_targets", []):
            if target["metre"] == identifier and excerpt in text[text.index(target["start"]):text.index(target["end"]) + len(target["end"])]:
                href = target["url"]
                break
        else:
            raise ValueError(f"Reading example is outside the reviewed passage: {identifier}")
    reading = "".join('<p class="metre-reading">' + ' <span class="reading-divider">│</span> '.join(esc(chunk) for chunk in chunks) + '</p>'
                      for chunks in example["reading"])
    return ('<div class="metre-example"><h3>पढेर हेर्नुहोस्</h3>'
            f'<blockquote>{esc(excerpt)}</blockquote>'
            f'<p class="metre-citation">{esc(meta["author"]["name"])} · <a href="../../{esc(href)}">{esc(meta["title"])} →</a></p>'
            f'<h4>पढ्ने अभ्यास</h4>{reading}<p class="metre-example-note">{esc(example["note"])}</p></div>')


def metre_guide(identifier, metre, guide, catalogue):
    reading = "".join(f'<li>{esc(tip)}</li>' for tip in guide["reading"])
    patterns = _pattern_html(metre, guide)
    legend = ('<p class="metre-legend">ल = लघु (१ मात्रा), ग = गुरु (२ मात्रा)। '
              'यहाँ अक्षर भनेको उच्चारणको एकाइ हो।</p>') if metre["kind"] != "free-verse" else ""
    references = " · ".join(f'<a href="{esc(ref["url"])}">{esc(ref["label"])}</a>' for ref in guide.get("references", []))
    sources = f'<p class="metre-references">थप पढ्न: {references}</p>' if references else ""
    writer = (f'<p class="metre-write"><a class="prosody-write" href="../../kavita-lekhan/?metre={esc(metre["writer"])}">यस छन्दमा कविता लेख्नुहोस् →</a></p>'
              if metre.get("writer") else "")
    return ('<details class="metre-guide" id="chhanda-parichaya">'
            '<summary>यस छन्दबारे र पढ्ने तरिका</summary><div class="metre-guide-body">'
            f'<p>{esc(guide["description"])}</p><p><b>बनोट:</b> {esc(guide["structure"])}</p>'
            f'{patterns}{legend}<h3>कसरी पढ्ने?</h3><ul>{reading}</ul>'
            f'{_example_html(identifier, guide, catalogue)}{sources}{writer}</div></details>')
