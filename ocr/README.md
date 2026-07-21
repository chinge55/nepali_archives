# ocr/ — digitization infrastructure

The archive's OCR service: a PDF goes in, page text comes out, through a
standardized pipeline instead of ad-hoc scripts. Engines are pluggable;
Surya-2 is the default (it beat both raw Tesseract *and* the shipped text
of प्रमिथस p.30 in the 2026-07-21 benchmark — see `gold/pramithas/`).

## Design

```
PDF ──render──▶ pages/*.png ──engine A──▶ ocr/A/*.txt ─┐
   (pdftoppm,      (source                             ├─▶ disagreements ──▶ adjudication
    300 dpi)        of truth)  ──engine B──▶ ocr/B/*.txt ─┘   (the only lines a human
                                                               or agent must review)
```

- **Engines are plugins** (`archive_ocr/engines/`): `tesseract` (classical
  baseline, fails *differently* from VLMs — that diversity is the point),
  `surya` (Surya-2 VLM via llama.cpp/Vulkan; the vLLM/docker path needs
  CUDA ≥ 13 which this machine's driver lacks), and **`ensemble` — the
  default and the archive's scanning formula**: Surya's text verbatim,
  Tesseract as shadow, disagreeing lines written to `review.json` with
  lexicon-OOV annotation (the adjudication queue; verified to catch 4/4
  known Surya errors on the gold page). The ensemble never auto-corrects —
  a shadow can be confidently wrong; fixes happen at adjudication against
  the scan. Adding an engine = one module + one registry line.
- **Jobs are directories** (`/mnt/disk_sda2/sangam/ocr_jobs/jobs/<id>/`):
  source.pdf + job.json + pages/ + ocr/<engine>/. No database; a job dir is
  complete, portable, hand-inspectable. All heavy artifacts live on the
  free disk (never `~` — it's nearly full).
- **Comparison is centralized** (`compare.py`) with the two benchmark
  lessons baked in: ZWNJ/ZWJ stripped before comparing (engine idiom, not
  print), and inlined margin श्लोक numbers split off (layout choice, not a
  misread).
- **Gold pages** (`gold/<book>/pg-NNN.txt`, tracked in git) are the only
  legitimate accuracy reference. Scoring engines against unproofread
  pipeline output flatters whichever engine produced it — we measured
  exactly that failure. Gold convention: exactly what is printed, no
  furniture, margin numbers on their own line, no ZWNJ, never modernize.

## Run

```bash
# server env (tiny): conda ocr_env — fastapi/uvicorn only; engines bring their own envs
~/miniconda3/envs/ocr_env/bin/python -m pip install -r ocr/requirements.txt   # once

cd ocr
~/miniconda3/envs/ocr_env/bin/python -m archive_ocr health    # engine availability
~/miniconda3/envs/ocr_env/bin/python -m archive_ocr serve     # API on :8100
~/miniconda3/envs/ocr_env/bin/python -m archive_ocr run book.pdf --first 20 --last 24

python3 tests/test_compare.py        # judgment core: normalize, CER, combine
python3 tests/test_storage.py        # ids, persistence, page padding
python3 tests/test_surya_parser.py   # surya results.json parsing (regression-pinned)
~/miniconda3/envs/ocr_env/bin/python tests/test_api.py   # API contract + failure paths
```

## API (no auth yet — single-operator; routes shaped so auth can wrap later)

| Route | What |
|---|---|
| `GET /health` | engine availability with detail |
| `POST /jobs` | multipart PDF + optional `engines` csv (default `surya`), `dpi`, `first_page`, `last_page` |
| `GET /jobs`, `GET /jobs/{id}` | job state (persisted every transition) |
| `GET /jobs/{id}/pages/{n}?engine=` | one page's text |
| `GET /jobs/{id}/text?engine=` | whole document text — the deliverable |
| `GET /jobs/{id}/review` | the ensemble's review queue (disagreeing lines + OOV flags) |

Quality tooling is deliberately NOT in the API: `compare.py` (line diffs,
CER, the ZWNJ/margin-numeral lessons) and `gold/` are offline QA used by
tests and future benchmark passes.

## Environment knobs (defaults fit this workstation)

`OCR_WORK_DIR`, `OCR_GOLD_DIR`, `OCR_DPI`, `TESSERACT_BIN`, `TESSERACT_LANG`,
`SURYA_BIN`, `LLAMA_CPP_BINARY`, `HF_HOME` — see `archive_ocr/config.py`.

## Roadmap (agreed 2026-07-21)

1. Grow the gold set to ~25 pages across eras (compare.py's line diffs
   feed the adjudication workflow; प्रमिथस p.30 is page #1, `draft` until
   native-speaker sign-off).
2. Benchmark: tesseract / surya / a frontier VLM on the gold set.
3. Arbitration stage: agent resolves only disagreement lines against page
   crops (ensemble accuracy at a fraction of full-agent cost) + lexicon
   OOV flagging from `roman_nepali_transliteration`.
4. Re-verify the ~60 OCR-derived archive works; wire into
   `process-book-archive`.
