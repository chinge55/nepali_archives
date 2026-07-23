# ocr/ — digitization infrastructure

This directory has two layers:

1. **Page OCR** turns a PDF into page images and engine text.
2. **Book workflow** turns those artifacts into reviewed archive sources using
   a persistent DAG of built-in Codex sub-agent tasks.

Page OCR is mechanical extraction, not an archive-ready transcription. A book
must still pass structure, folio, reconciliation, footnote, metadata, and
rights/exclusion checks plus two human approval gates.

## Page OCR design

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
~/miniconda3/envs/ocr_env/bin/python -m archive_ocr run book.pdf \
  --engines ensemble --first 20 --last 24

python3 tests/test_compare.py        # judgment core: normalize, CER, combine
python3 tests/test_storage.py        # ids, persistence, page padding
python3 tests/test_surya_parser.py   # surya results.json parsing (regression-pinned)
~/miniconda3/envs/ocr_env/bin/python tests/test_api.py   # API contract + failure paths
```

## API (no auth yet — single-operator; routes shaped so auth can wrap later)

| Route | What |
|---|---|
| `GET /health` | engine availability with detail |
| `POST /jobs` | multipart PDF + optional `engines` csv (default `ensemble`), `dpi`, `first_page`, `last_page` |
| `GET /jobs`, `GET /jobs/{id}` | job state (persisted every transition) |
| `GET /jobs/{id}/pages/{n}?engine=` | one page's text |
| `GET /jobs/{id}/text?engine=` | whole document text — the deliverable |
| `GET /jobs/{id}/review` | the ensemble's review queue (disagreeing lines + OOV flags) |

Quality tooling is deliberately NOT in the API: `compare.py` (line diffs,
CER, the ZWNJ/margin-numeral lessons) and `gold/` are offline QA used by
tests and future benchmark passes.

## Book workflow

Page OCR answers “what characters might be on each page?” The book workflow
answers the harder archival questions: which pages belong to which work, what
must be excluded, whether printed folios are shuffled, how disagreements are
resolved against the scan, and exactly which source files may enter Git.

The governing rule is simple: **the page image is evidence; OCR is only a
hint**. Neither OCR nor an agent may modernize spelling, invent numbering, or
silently repair the source.

### People, programs, and trust boundaries

There are three kinds of participant. Local programs perform repeatable
mechanical work. Built-in Codex sub-agents perform bounded reading tasks. A
human makes the two decisions that change the shape or destination of the work.

```text
                         INTERACTIVE CODEX SESSION
                    (signed in with ChatGPT Plus/Pro)

                  +----------------------------------+
                  | lead/coordinator                 |
                  | - claims ready graph nodes       |
                  | - launches built-in sub-agents   |
                  | - merges typed results           |
                  +----------------+-----------------+
                                   |
                     up to 3 worker slots in parallel
                    +--------------+--------------+
                    |              |              |
              +-----v-----+  +-----v-----+  +-----v-----+
              | structure |  | folio /   |  | reconcile |
              | reader    |  | support   |  | / verify  |
              +-----+-----+  +-----+-----+  +-----+-----+
                    |              |              |
                    +--------------+--------------+
                                   |
                              typed JSON only
                                   |
+----------------------------------v-----------------------------------------+
| LOCAL REPOSITORY AND TOOLS                                                 |
|                                                                            |
| source PDF -> render/OCR -> .ocr-work run state -> isolated stage          |
|                  ^                 |                    |                   |
|                  |                 |                    v                   |
|            page images          human gates       validate + exact commit  |
+------------------+-----------------+--------------------+-------------------+
                   |                 |                    |
             source of truth   approve exact hash   archives/ changes here
                                                    (Gate 2 only; no push)
```

The repository contains no model-network client for this workflow. Before
starting, `codex login status` must report ChatGPT sign-in on the intended
Plus/Pro account. Stop if Codex is using API-key authentication. The command
can confirm ChatGPT authentication, but the operator must know that the signed-in
account is the intended subscription.

### End-to-end lifecycle

The complete path for one scanned book is:

```text
 +-----------------------------+
 | 0. AUTH                     |
 | ChatGPT login on Plus/Pro   |
 +-------------+---------------+
               |
               v
 +-------------+---------------+
 | 1. ACQUIRE                  |
 | fingerprint, preflight, OCR |
 +-------------+---------------+
               |
               v
 +-------------+---------------+
 | 2. UNDERSTAND               |
 | 3 planning agents + merge   |
 +-------------+---------------+
               |
               v
 +-------------+---------------+
 | HUMAN GATE 1                |
 | approve exact structure hash|
 +-------------+---------------+
               |
               v
 +-------------+---------------+
 | 3. TRANSCRIBE               |
 | reconcile sections + notes  |
 +-------------+---------------+
               |
               v
 +-------------+---------------+
 | 4. CHECK                    |
 | deterministic QA; verify    |
 | risky pages, max 2 rounds   |
 +-------------+---------------+
               |
               v
 +-------------+---------------+
 | 5. MATERIALIZE              |
 | build and validate run/stage|
 +-------------+---------------+
               |
               v
 +-------------+---------------+
 | HUMAN GATE 2                |
 | approve exact manifest hash |
 +-------------+---------------+
               |
               v
 +-------------+---------------+
 | 6. PROMOTE                  |
 | exact paths, one commit     |
 | never push                  |
 +-----------------------------+
```

Gate 1 prevents agents from transcribing the wrong page ranges or copyrighted
editorial matter. Gate 2 prevents reviewed work from reaching canonical
`archives/` paths until the operator has inspected the exact proposed files and
their hashes.

### The graph and its parallel work

The workflow is a dependency graph, not a long prompt. A node becomes runnable
only when all of its parents are complete. The coordinator keeps one Codex slot
for scheduling and uses the other available slots for independent work.

```text
 preflight
     |
 local ensemble OCR (Surya primary, Tesseract shadow)
     |
     +-------------------+-------------------+
     |                   |                   |
     v                   v                   v
 plan_structure      plan_folios         plan_dedupe
 strong reader       support reader      support reader
     |                   |                   |
     +-------------------+-------------------+
                         |
                  merge_structure
                         |
                 +-------v--------+
                 | HUMAN GATE 1   |
                 | structure-plan |
                 | hash approval  |
                 +-------+--------+
                         |
                         v
              expand approved sections
                         |
          +--------------+------------------ ... --+
          |                                         |
 +------------v-------------+             +------------v-------------+
 | section A pages          |             | section N pages          |
 |       |          |       |             |       |          |       |
 |       v          v       |             |       v          v       |
 | reconcile     footnotes  |             | reconcile     footnotes  |
 +-------+----------+-------+             +-------+----------+-------+
           |                                         |
           +-------------------+---------------------+
                               |
                              QA 0
                               |
                 +-------------+-------------+
                 |                           |
       ready_to_stage=True       ready_to_stage=False
                 |                           |
                 v                    targeted verifier 1
               stage                         |
                                             v
                                            QA 1
                                             |
                         ready=True + ready=False
                              |             |
                              v      targeted verifier 2
                            stage            |
                                             v
                                            QA 2
                                             |
                                  ready=True  -> stage
                                  ready=False -> human intervention
```

Each included poem, canto, chapter, or essay gets its own reconciliation task
covering the complete semantic section. This avoids page-window seams that lose
lines or corrupt stanza numbering. A separate footnote task examines the same
section’s page bottoms. Excluded modern/editorial sections do not create
transcription tasks.

Every agent result is schema-bound to the claimed task, role, assigned source
pages, evidence pages, and uncertainties. Role-specific contracts add fields
such as folio state, duplicate decisions, section numbering, or footnotes. A
result for another task, role, or page range is rejected rather than quietly
accepted.

### What persists, and how resume works

Heavy OCR data and lightweight workflow state are deliberately separate:

```text
 OCR_WORK_DIR/jobs/<ocr-job-id>/          .ocr-work/book-runs/<run-id>/
 +--------------------------------+       +-------------------------------+
 | source.pdf                     |       | run.json        graph state   |
 | pages/pg-001.png               |<------| artifacts/      plans + QA    |
 | ocr/ensemble/pg-001.txt        | bind  | tasks/          agent results |
 | ocr/ensemble/review.json       | hash  | stage/          proposed tree |
 +--------------------------------+       | promotion-journal.json        |
                                          | promotion-backup/             |
                                          +-------------------------------+
```

An OCR job is reusable only when its source checksum, 300-dpi setting, ensemble
completion, page sequence, text files, and review file all match the book run.
Completed artifacts are hash-checked before downstream work. If one changes,
the run blocks until the affected node is intentionally reset.

Task leases make interruption safe:

```text
                  claim                     valid result
    PENDING -----------------> CLAIMED --------------------> COMPLETED
       ^                          |
       |                          | lease expires / retry
       +--------------------------+
                                  |
                                  | attempts exhausted
                                  v
                               FAILED -> run BLOCKED
```

Restarting Codex does not discard accepted OCR or agent results. `book resume`
expires stale claims and returns safe tasks to the ready queue. `book abort`
stops scheduling without deleting evidence.

### The two human gates

Approval means “I approve these exact bytes,” not merely “the plan looked
reasonable earlier.”

```text
 producer artifact -> SHA-256 -> human inspection -> recorded approval
        |                                                  |
        +---------------- exact path + exact hash ----------+
                                                           |
                                             downstream work may start

 artifact changes after approval -> hash mismatch -> BLOCKED
```

At **Gate 1**, inspect page classification, physical/printed folio order,
rights exclusions, work boundaries, section ranges, duplicates, and complete
page coverage. Keep the author’s own prefaces; exclude modern editorial
introductions.

At **Gate 2**, inspect every staged `metadata.json`, `text.txt`, original scan,
per-work PDF slice, target path, prior hash, and proposed hash. Promotion then
rechecks the approved manifest, repository base commit, target cleanliness,
staged validation, changed Git paths, and committed Git blob hashes.

```text
 run/stage/archives/...                 canonical repository
 +------------------------+            +------------------------+
 | metadata.json          | --Gate 2-->| archives/authors/...   |
 | text.txt               |  approval  | exact approved paths   |
 | per-work PDF slice     |            | only                   |
 | retained original PDF  |            +-----------+------------+
 +------------------------+                        |
                                                 validate
                                                    |
                                                 one commit
                                                    |
                                              record commit SHA
                                                    |
                                              STOP (never push)
```

Promotion uses a repository-wide lock and a durable journal. If interrupted
before the commit, recovery restores only the approved targets from verified
backups. If the commit exists but completion was not recorded, recovery accepts
it only when its parent, changed paths, and committed bytes exactly match the
approved manifest.

### Operating the workflow

Start from `ocr/`:

```bash
codex login status
python -m archive_ocr book init "/absolute/path/book.pdf" --author <author-id>
python -m archive_ocr book status <run-id>

python -m archive_ocr book claim <run-id> preflight --worker coordinator
python -m archive_ocr book preflight <run-id> --token <claim-token>
python -m archive_ocr book claim <run-id> ocr --worker coordinator --lease 86400
python -m archive_ocr book ocr <run-id> --token <claim-token>

python -m archive_ocr book ready <run-id> --limit 3 --kind agent
python -m archive_ocr book claim <run-id> <node-id> --worker <worker-id>
python -m archive_ocr book prompt <run-id> <node-id> --token <claim-token>
# Spawn the built-in sub-agent with packet.prompt. It writes packet.result_path.
python -m archive_ocr book complete <run-id> <node-id> \
  --token <claim-token> --artifact <packet.artifact_ref>
```

Repeat `ready -> claim -> prompt -> complete` for the three planning agents.
The coordinator then reconciles their typed results into one
`book-plan/v1` JSON file, records it, and completes `merge_structure`:

```bash
python -m archive_ocr book write-artifact <run-id> \
  artifacts/structure-plan.json /path/to/book-plan.json
python -m archive_ocr book claim <run-id> merge_structure --worker coordinator
python -m archive_ocr book complete <run-id> merge_structure \
  --token <claim-token> --artifact artifacts/structure-plan.json
```

Use `book renew` for a legitimately long task, `book fail` for a failed worker,
and `book reset` only for an intentional retry. Dynamic nodes are created by
the typed `book expand` and `book advance-qa` transitions; operators should not
construct graph internals by hand.

Gate 1:

```bash
PLAN="/absolute/path/to/.ocr-work/book-runs/<run-id>/artifacts/structure-plan.json"
python -m archive_ocr book hash "$PLAN"
python -m archive_ocr book approve <run-id> structure "$PLAN" \
  --sha <sha256> --approver <name>
python -m archive_ocr book expand <run-id>
```

QA and Gate 2:

```bash
python -m archive_ocr book claim <run-id> qa_0 --worker coordinator
python -m archive_ocr book qa <run-id> --round 0 --token <claim-token>
python -m archive_ocr book advance-qa <run-id> artifacts/qa-0-report.json
python -m archive_ocr book status <run-id>
python -m archive_ocr book ready <run-id> --limit 3
```

If the report is not ready to stage, `advance-qa` creates `verify_1` and
`qa_1`; a second risky report creates `verify_2` and `qa_2`. Run verifier nodes
through the normal agent loop, then claim and execute the corresponding QA
node. After round 2, unresolved high-risk findings require human intervention.
Claim `stage` only when `ready` actually exposes it.

Before running `book stage`, the coordinator materializes the complete proposed
source tree below `<run>/stage/archives/authors/...`: every `metadata.json` and
`text.txt`, every per-work PDF slice, and the retained original scan. Canonical
`archives/` paths remain untouched. Then build and verify the exact manifest:

```bash
python -m archive_ocr book claim <run-id> stage --worker coordinator
python -m archive_ocr book stage <run-id> --token <claim-token> \
  --retained archives/authors/<author>/_source_books/<original.pdf> \
  --message <commit-message>

MANIFEST="/absolute/path/to/.ocr-work/book-runs/<run-id>/artifacts/staging-manifest.json"
python -m archive_ocr book verify-stage <run-id> "$MANIFEST"
python -m archive_ocr book hash "$MANIFEST"
python -m archive_ocr book approve <run-id> promotion "$MANIFEST" \
  --sha <sha256> --approver <name>
python -m archive_ocr book claim <run-id> promote --worker coordinator
python -m archive_ocr book promote <run-id> "$MANIFEST" \
  --token <claim-token>
```

After an interrupted promotion only:

```bash
python -m archive_ocr book recover-promotion \
  <run-id> "$MANIFEST"
```

Resume or stop safely:

```bash
python -m archive_ocr book resume <run-id>
python -m archive_ocr book abort <run-id>
```

Use `python -m archive_ocr book --help` and each subcommand’s `--help` for
exact arguments and JSON contracts. See
`../skills/process-book-archive/SKILL.md` for the executable preservation,
folio, numbering, front-matter, footnote, staging, and promotion rules.

## Environment knobs (defaults fit this workstation)

`OCR_WORK_DIR`, `OCR_GOLD_DIR`, `OCR_DPI`, `TESSERACT_BIN`, `TESSERACT_LANG`,
`SURYA_BIN`, `LLAMA_CPP_BINARY`, `HF_HOME` — see `archive_ocr/config.py`.

## Accuracy roadmap

1. Grow the gold set to ~25 pages across eras (compare.py's line diffs
   feed the adjudication workflow; प्रमिथस p.30 is page #1, `draft` until
   native-speaker sign-off).
2. Benchmark: tesseract / surya / a frontier VLM on the gold set.
3. Re-verify the ~60 OCR-derived archive works through the book graph.
