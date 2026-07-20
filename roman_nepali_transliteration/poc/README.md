# poc/ — dev harness (Stage 2)

The POC page graduated to the site: the product now lives at `/type/`
(sources: `assets/type/`, page writer: `pipeline/build_site.py
write_type_page`). This directory keeps the node test harness:

    node poc/test_engine.mjs     # engine + normalize-parity + latency tests

It reads the canonical engine/data from `assets/type/`. Regenerate lexicons
with `python3 pipeline/build_lexicon.py --install` (see pipeline/README.md).
