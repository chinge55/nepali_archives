# Word meanings (WIP)

This directory contains an incomplete research and preview workflow for source-backed word meanings. It is work in progress and is not integrated into the public reader. The preview is for review only; it does not rewrite archive text, provide a backend, or claim automatic correct-context meanings.

The current review covers 300 frequent unmatched forms, with 280 accepted lookup associations. Across 704 works, exact lookup covers 57.36% of occurrences at baseline and reviewed associations raise occurrence availability to 64.81%. In the Muna Madan sample, 1,401 supported forms cover 62.15% of occurrences. These are availability measures, not scores for selecting the correct sense in context. Only three context combinations have been reviewed so far, so content and coverage remain incomplete.

## Data flow

Run commands from the repository root:

```sh
python3 word_meanings/pipeline/download_sources.py
python3 word_meanings/pipeline/combine_and_compare.py
python3 word_meanings/pipeline/build_lookup_review.py
python3 word_meanings/pipeline/build_reader_preview.py
python3 -m http.server 8258 --directory word_meanings/data/preview
```

- `download_sources.py` obtains hash-pinned source snapshots listed in `sources.json` into ignored `data/raw/`.
- `combine_and_compare.py` writes derived data under ignored `data/combined/`.
- `build_lookup_review.py` reads tracked `review/lookup-review.json` and writes derived review data under ignored `data/review/`. The tracked review is sanitized and does not copy dictionary definitions.
- `build_reader_preview.py` reads `preview/index.template.html`, `app.js`, and `styles.css`, then writes ignored full HTML, work JSON, and TXT files under `data/preview/`.

Raw and derived dictionary data are not committed. Acquisition terms and hashes are recorded in `sources.json` so the workflow can be reproduced. If a mutable upstream snapshot does not match its recorded hash, stop and update the reviewed manifest and review data deliberately; never silently accept a changed snapshot.

The preview has no backend. It keeps sources and saved words in the browser, and the displayed archive content remains unchanged. Do not treat its contextual sense examples as a complete reader integration.

## Browser QA

The browser checks were run with Puppeteer 21.11.0. Install it locally, then run the checks with the preview server running:

```sh
npm install --prefix word_meanings --no-save --package-lock=false puppeteer@21.11.0
node word_meanings/tests/reader.cjs
```

An existing Puppeteer installation can also be supplied through `NODE_PATH`. `PREVIEW_URL` is optional and defaults to `http://localhost:8258`. Screenshots and reports are written to ignored `data/qa/`. Keep credentials, private paths, and machine-specific configuration out of tracked files.


## Deployment and source correction

This work is held on `wip/word-meanings`. Push deployment is restricted to `main`, and both deployment workflow jobs also require `refs/heads/main` so manually dispatching this branch cannot publish it. The public site builder does not consume this directory.

The branch also retains the narrow, scan-checked Shakuntala page-6 correction from the word review: damaged fourth-stanza text, stanza markers, and an avagraha. Its evidence is in `review/shakuntala-page6-correction.json`; the complete work remains marked unproofread.
