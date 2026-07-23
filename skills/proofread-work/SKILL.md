---
name: proofread-work
description: >-
  Proofread a work's text.txt against its source and flip text.proofread to true —
  the archive's one remaining pre-public gate (faithful OCR/scrape-error fixes
  ONLY, never modernize). Use when asked to proofread/verify a work, or to work
  through the proofreading backlog. Read AGENTS.md first.
---

# Proofread a work (the pre-public gate)

Every work starts `text.proofread: false`. Proofreading = comparing `text.txt` against
its **source of truth** and fixing transcription defects — nothing else.

**Cardinal rule: preserve, don't rewrite.** Fix only OCR/scrape errors. Period/variant
spellings stay as printed (जूवा, गौरीशंकर, एक् मन्, गर्‍या). If the print itself is odd
(manuscript lacunae, irregular numbering), it stays — note it in `description`.

## 1. Open the source

- **Scanned PDF** (`source.pdf`): render pages 300 dpi —
  `pdftoppm -r 300 -png -f A -l B <pdf> /tmp/<slug>/pg` — and read the images
  (the page image is the source of truth, not the OCR).
- **Web** (`source.url` / `extracted/index.html`): use the saved HTML (provenance
  copy) — the live page may have changed.
- Cross-check candidates for classics: Wikisource, the print scan if both exist.

## 2. Compare systematically

Work section-by-section (per सर्ग/canto/essay — never skim). For long verse works,
fan out one agent per section (or, without subagent support, one sequential pass per
section) with the page images + that section of text.txt, returning corrections;
verse can ALSO be checked structurally first:

- **stanza/श्लोक numbering contiguous 1..N per section** (printed gaps = lacunae, keep);
- no page furniture leaked (running headers, `N / शीर्षक` footers, page numbers);
- headings have a blank line after them; colophon lines (`वि.सं. …`) intact at the end.

Known OCR traps to look for: ब/व and श/ष/स swaps, dropped/garbled halant (एक्→एक),
numerals misread as letters (२→र, ३→3), danda variants (।। vs ॥ — keep as printed),
merged/split lines at page breaks, nukta and ँ/ं confusion.

## 3. Record + flip the flag

Apply fixes to `text.txt`. Then in `metadata.json`: set `text.proofread: true` and
bump `updated` (author-controlled — builds don't stamp it). If quality was reassessed,
adjust `text.quality`. Note real source anomalies in `description`, not inline.

## 4. Validate + ship

`python3 pipeline/validate.py`, eyeball the rendered page if structure changed
(`verify-site-change` skill), then the `ship` skill. Commit message: what was fixed
(counts/classes of errors), source compared against, "proofread: true".
