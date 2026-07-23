---
name: process-book-archive
description: >-
  Digitize a scanned Nepali book with the resumable archive_ocr book DAG:
  ensemble OCR, Codex sub-agent reconciliation, two approval gates, staging,
  and one local commit. Read AGENTS.md first.
---

# Process a scanned book into archive works

Cardinal rule: **preserve, don't rewrite**. Page images are the source of truth;
ensemble OCR is only a transcription hint. Before any model task, run:

```bash
codex login status
```

Proceed only when Codex reports ChatGPT sign-in on the intended Plus/Pro account.
If it reports API-key authentication, stop; this workflow makes no model API calls
but repository code cannot change which Codex account is active. Graph state lives in ignored
`.ocr-work/book-runs/<run-id>/`; heavy images/OCR stay in `OCR_WORK_DIR`.

## 1. Initialize and approve structure

Run from `ocr/`:

```bash
python -m archive_ocr book init "/absolute/path/book.pdf" --author <author-id>
python -m archive_ocr book status <run-id>
python -m archive_ocr book ready <run-id> --limit 3

# Claim each coordinator node and substitute its returned token.
python -m archive_ocr book claim <run-id> preflight --worker coordinator
python -m archive_ocr book preflight <run-id> --token <claim-token>
python -m archive_ocr book claim <run-id> ocr --worker coordinator --lease 86400
python -m archive_ocr book ocr <run-id> --token <claim-token>
```

`init` fingerprints the PDF, reuses matching 300-dpi ensemble OCR, and creates
preflight tasks. Unknown authors pause for `add-author`. Planning must classify
every page and establish duplicates, colophon/rights, TOC, work/section ranges,
and modern editorial exclusions; keep the author's own prefaces.

**Verify physical folio order before chunking.** Read every printed folio from
an optional locally generated footer montage, or each page image: scans can be shuffled and OCR mangles lone digits.
Record the printed-to-PDF offset; never infer a manuscript lacuna from PDF order.

The lead coordinator merges the three typed planning results into a `book-plan/v1`
`ApprovedStructurePlan`, writes it below `artifacts/`, claims `merge_structure`, and
completes that node with `--artifact <run-relative-plan-path>`. Then inspect that exact
producer artifact and pass the first hash-bound gate:

```bash
python -m archive_ocr book hash <structure-plan.json>
python -m archive_ocr book approve <run-id> structure <structure-plan.json> \
  --sha <sha256> --approver <name>
python -m archive_ocr book expand <run-id>
```

Approve only when rights/exclusions, folios, page mapping, semantic sections,
duplicate actions, and all-page coverage are correct.

## 2. Drive ready tasks with built-in Codex sub-agents

Run inside an interactive Codex Plus/Pro session. Use only built-in sub-agents:
no API key, OpenAI SDK, Agents SDK, or metered model API. Reserve one slot for
the lead/coordinator and use the remaining available slots.

Repeatedly fetch `book ready`, claim a task with `book claim`, emit its immutable
packet with `book prompt <run> <node> --token <claim-token>`, spawn the named
sub-agent profile with that prompt, then validate/record the isolated
result with `book complete --artifact <artifact_ref>` (or `book fail`). The
packet supplies both an absolute `result_path` for the worker and the exact run-relative
`artifact_ref` for completion. Agents write only to their result paths, never `archives/`. Use `python -m archive_ocr book --help`
and each subcommand's `--help` for exact arguments.

Schedule the largest independent semantic sections first. The DAG fans in
structure before gate 1, then fans out reconciliation and footnote tasks.


## 3. Reconcile — CHUNK BY SECTION, not fixed pages

This is the #1 lesson. Fixed page-window chunks drop/merge/mis-number stanzas (and
lose verse) at window **seams**. Use **one agent per section** (poem / सर्ग / canto /
essay), each given that section's full page range. For prose, one agent per essay.
(Parallel subagents if your tool has them; otherwise one sequential pass per section
with a fresh context — the section boundary is what matters, not the parallelism.)

Per-agent rules (put in the prompt): source of truth = images; faithfully reproduce
verse lines / paragraphs as printed; **read every stanza/श्लोक number from the image,
preserving genuine printed gaps; never retain OCR garbage such as `रर` or Latin-mixed
`3१`, and never infer an unprinted number from sequence alone**; numbers on their own line adjacent to the stanza; section
headings on their own line; **drop page furniture** (running headers, `<n> : <title>`
footers, page numbers); keep danda । ॥, ! ? quotes, hyphens, avagraha ऽ; never
modernize/translate. Margin श्लोक numbers: crop/upscale to read them.
Return structured `{title/heading, first_n, last_n, text, notes}`; add a QA stage.

**After reconciliation, always check per-section numbering contiguity (1..N).** Real
manuscript lacunae (printed numbering that genuinely jumps) are faithful — preserve
them and note in the description. Everything else is a transcription defect: re-run
that one section as a single agent (cleanest), or surgically insert/renumber against
the scan if it's a clean single-marker drop.

Two more agent failure modes to QA for (both hit लुनी):
- **Hallucinated structure** — an agent ADDED stanza numbers (१)–(७) to a canto the
  print leaves unnumbered. If a section looks unnumbered, verify against the image
  and keep it unnumbered.
- **Dropped footnotes** — short glosses (`*` or `१.` at page bottoms) get silently
  discarded, markers and all. Run a dedicated footnote sweep (a few agents scanning
  every page bottom), collate into a `टिप्पणी` endnote section after the text, and
  clean stray inline asterisks. OCR alone cannot find footnotes reliably.

Deterministic QA checks coverage, numbering, malformed numerals, dangling
footnote markers, unresolved disagreements, suspicious text loss, and furniture.
Risk creates a targeted verifier for only the affected pages. After two failed
attempts, block for human adjudication rather than silently accepting text.

Claim the ready QA node, run `book qa <run-id> --round N --token <token>`, then run
`book advance-qa <run-id> artifacts/qa-N-report.json`. This deterministically checks
coverage, numbering, footnotes, suspicious loss, and furniture, then adds either a
targeted verifier or staging nodes.

If the Codex session or subscription allowance ends, stop cleanly:

```bash
python -m archive_ocr book resume <run-id>
python -m archive_ocr book status <run-id>
```

Expired claims are requeued; completed OCR and accepted results are not
repeated.

## 4. Stage each work

`archives/authors/<author>/<slug>/` with `text.txt`, a per-work PDF (a `gs` slice for
collection members, or the whole-book PDF for a single-work book — identical copies
dedupe in git), and a schema-conformant `metadata.json`. Reusable helper pattern
(`make_work`): set `genre` so `genre[0]` drives rendering (`nibandha`/`upanyas` =
prose; else verse); `first_published.bs` from the colophon; `source.name` = the exact book, edition, and publisher wording supported by the scan's colophon; `source.pdf` = `<slug>.pdf`; `text.extraction_method="ocr"`,
`ocr_status="ocr-done"`, `proofread=false`. Compute
`title_roman`/slug via `pipeline/devanagari_slug.py`.

- **Collection members**: description = `From the collection <name>.` (terse first
  sentence; rich text may follow). Match an existing collection's exact name to join
  its page. **Dedup**: if a member already exists, prepend the collection sentence to
  its description — do NOT create a duplicate. Check slug collisions before writing.
- **Author's own preface** (भूमिका/author note): include it as prose (unwrap wrapped
  lines into flowing paragraphs); a heading + its subtitle need a blank line between.

## 5. Approval gate 2, promote, and commit

Write the proposed source tree only under `<run>/stage/archives/authors/...`, including
`_source_books/<original>.pdf` plus every per-work source slice. Claim `stage`, then run
`book stage <run> --token <token> --retained <target-original-pdf> --message <commit-message>`;
it builds, validates, and completes the manifest while canonical paths remain untouched.
Inspect exact
files, diffs, exclusions, QA, PDF slices, hashes, and commit allowlist:

```bash
python -m archive_ocr book verify-stage <run-id> <staging-manifest.json>
python -m archive_ocr book hash <staging-manifest.json>
python -m archive_ocr book approve <run-id> promotion <staging-manifest.json> \
  --sha <sha256> --approver <name>
python -m archive_ocr book claim <run-id> promote --worker coordinator
python -m archive_ocr book promote <run-id> <staging-manifest.json> --token <claim-token>
# Only after an interrupted promotion:
python -m archive_ocr book recover-promotion <run-id> <staging-manifest.json>
```

Changed artifacts invalidate approval. Promotion blocks on pre-existing changes
under a target, preserves unrelated dirty work, validates, and restores affected
paths on failure. It retains the original book plus per-work PDF slices and
creates one explicit-path local commit per source book.


**Source-only repo:** you commit `metadata.json` + `text.txt` + the source file. The
build artifacts (`reader.html`, `reader.epub`, `archives/index.json`, the font subset,
`site/`) are **git-ignored and rebuilt by CI** — do NOT commit them.

Verify before committing (same checks as `pipeline/validate.py`): metadata schema-valid;
dir name == `id`, author dir == `author.id`; `text.txt` non-empty Devanagari;
`rights.status` ∈ {public-domain, permission-granted}; sections render right (verse/prose,
headings, contiguous numbering). To eyeball rendering locally, optionally run
`build_index.py` → `build_formats.py <dir>` → `build_site.py` and serve `site/` — but
those outputs stay un-committed. Then commit per book (style: see git log; Co-Authored-By
trailer). Record the commit SHA and **never push**. Use the `ship` skill only
when the user separately requests deployment.

**Stats page** (`pipeline/stats.py` → `site/stats/`, "अभिलेख एक नजरमा"): `build_site.py`
**regenerates it on every run** (so it's recomputed before each commit/deploy and can
never go stale — CI rebuilds it too). After adding a NEW work, just rebuild and eyeball
`/stats/`; after adding a NEW AUTHOR, also skim `stats.STATS_STOP` and the signature-words
column — a new author's register may surface a few function/archaic words that belong in
the stopword list so the word cloud stays evocative.

## Reference

Worked examples: the 2026-06 Devkota `001_book_archive` batch (+40 works) and लुनी
(shuffled-folio scan). The site rendering contract is in AGENTS.md; shipping is the
`ship` skill.
