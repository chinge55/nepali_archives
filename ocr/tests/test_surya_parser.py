#!/usr/bin/env python3
"""Surya output parser spec — this parser broke once (folder-mode layout),
so its behavior is pinned here with a fixture shaped like real results.json.

Run: python3 ocr/tests/test_surya_parser.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from archive_ocr.engines.surya import blocks_to_text

bad = []


def check(cond, msg):
    if not cond:
        bad.append(msg)


page = {
    "blocks": [
        {"html": "<p block-type='Text'>जरूर साथी म पागल !<br>यस्तै छ मेरो हाल ।</p>"},
        {"html": "<h2>१</h2>"},
        {"html": ""},                                  # empty block: dropped
        {"html": "<p>क &amp; ख &lt;तीन&gt;</p>"},       # entities unescaped
        {"text": "plain-text block"},                  # text fallback
    ],
    "image_bbox": [0, 0, 100, 100],
}

out = blocks_to_text(page)
lines = out.splitlines()
check(lines == ["जरूर साथी म पागल !", "यस्तै छ मेरो हाल ।", "१",
                "क & ख <तीन>", "plain-text block"], f"parsed lines: {lines}")
check(out.endswith("\n"), "page text ends with newline")
check(blocks_to_text({"blocks": []}) == "\n", "empty page yields empty text")

if bad:
    print("FAIL")
    for b in bad:
        print(" ", b)
    raise SystemExit(1)
print("OK: surya parser spec passes")
