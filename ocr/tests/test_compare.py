#!/usr/bin/env python3
"""Spec for the comparison core (repo convention: plain asserts, exit 0 = pass).

Run: python3 ocr/tests/test_compare.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from archive_ocr.compare import (content_lines, disagreements, edit_distance,
                                 normalize_line, score_against)

bad = []


def check(cond, msg):
    if not cond:
        bad.append(msg)


# normalization: ZWNJ is engine idiom, margin numerals are layout
check(normalize_line("गर्छन्‌") == "गर्छन्", "ZWNJ must be stripped")
check(normalize_line("३७ सुषुप्त विपिन") == "सुषुप्त विपिन",
      "inlined margin numeral must be split off")
check(normalize_line("  मेरो नाम  ") == "मेरो नाम", "whitespace trim")

# content_lines drops furniture-sized fragments
lines = content_lines("१७\nसाना-तिना नदी-नाला नाम-शेष बने सब ।\n\n२२\n")
check(lines == ["साना-तिना नदी-नाला नाम-शेष बने सब ।"], f"content_lines: {lines}")

# edit distance basics + the real confusion pair from the benchmark
check(edit_distance("झल्कन्छन्", "झल्कन्छन्") == 0, "identity distance")
check(edit_distance("झल्कन्छन्", "रुल्कन्छन्") == 2, "झ->रु is 2 char edits")
check(edit_distance("abc", "xbc", cap=0) == 1, "cap overshoot returns cap+1")

# score_against: identical text is 100% exact, 0 CER
n, exact, matched, cer = score_against("मेरो नाम हो साथी\nयस्तै छ मेरो हाल ।",
                                       "मेरो नाम हो साथी\nयस्तै छ मेरो हाल ।")
check((n, exact, cer) == (2, 2, 0.0), f"perfect score: {(n, exact, cer)}")

# one-char misread lands in matched with a small CER, not in exact
n, exact, matched, cer = score_against("अदृष्टले पोषित शिशु झैँ ऐतिहासिक",
                                       "अदृष्टले पोषित शिशु कैं ऐतिहासिक")
check(exact == 0 and matched == 1 and 0 < cer < 15, f"near-miss: {cer}")

# disagreements: agreement is exact-normalized-match, diffs carry both readings
total, agree, diffs = disagreements(
    30, "surya", "सुषुप्त विपिन महीरुहमा महान्\nप्रबलपक्ष सहसा प्रभंजन गरुडवेग",
    "tesseract", "सुष्प्त विपिन महीरुहमा महान्‌\nप्रबलपक्ष सहसा प्रभंजन गरुडवेग")
check((total, agree, len(diffs)) == (2, 1, 1), f"diff shape: {(total, agree, len(diffs))}")
check(diffs[0].line_b.startswith("सुष्प्त"), "diff carries the other engine's reading")

# ensemble combine: agreement passes through, disagreement -> review with OOV notes
from archive_ocr.engines.ensemble import combine
pr = combine(30,
             "अदृष्टले पोषित शिशु कैं ऐतिहासिक शक्तिको,\nजसले बनाउनु छ धूलिढेर दरबार",
             "अदृष्टले पोषित शिशु झैँ ऐतिहासिक शक्तिको,\nजसले बनाउनु छ धूलिढेर दरबार")
check(pr.lines == 2 and pr.agreeing == 1 and len(pr.review) == 1,
      f"combine shape: {pr.lines}/{pr.agreeing}/{len(pr.review)}")
check("कैं" in pr.review[0].oov_a, "misread token must be OOV-flagged")

if bad:
    print("FAIL")
    for b in bad:
        print(" ", b)
    raise SystemExit(1)
print("OK: compare.py spec passes")
