# Review 3: Browser-side implementation technology (Opus 4.8 agent, 2026-07-20)

Scope: how to *build* the client-side suggestion engine on a static (GitHub Pages / `www.nepaliarchives.org`) site — libraries, data structures, inference runtimes, loading, and input plumbing — with real size/latency numbers. The linguistic pipeline (rules → lexicon → normalized lookup → neural fallback → re-rank) is assumed; this covers what runs it in the browser.

Grounding note: this repo already ships a Rust→WASM search engine (Pagefind, invoked as `npx pagefind` in CI per `CLAUDE.md`), subsets fonts to `woff2`, and its PDF reader depends on GitHub Pages honoring `Accept-Ranges`/Range requests. So "lazy-loaded WASM + compact binary assets + range-served static files on GH Pages" is already proven infrastructure here, not a new bet.

## 1. JS transliteration libraries — deterministic mapping ≠ suggestion typing

The critical distinction: the well-known JS libraries are **deterministic scheme converters** (one input → exactly one output), not **suggestion engines** (fuzzy input → ranked candidate list). They solve a different problem and cannot, by themselves, deliver natural-typing behavior.

- **Sanscript.js / `@indic-transliteration/sanscript`** — "scheme" = a script or romanization; converts via `Sanscript.t(input, from, to)` producing a *single* output. Supports Devanagari plus Roman schemes `iast, iso, itrans, itrans_dravidian, kolkata, slp1, velthuis, wx, hk (Harvard-Kyoto), cyrillic`. It has **no ranking, no candidate suggestions, no dictionary lookup, no fuzzy matching** — purely character/phonetic rules, and requires the user to type in a *strict* scheme (e.g. exact ITRANS). It explicitly documents "lossy scheme" failure modes. MIT-licensed, small, dependency-free. Good as the deterministic **rule layer**, not as the typing UX. ([GitHub](https://github.com/indic-transliteration/sanscript.js))
- **ml2en and similar** (Kailash Nadh) — algorithmic Malayalam→English *romanization* (the reverse direction), again a deterministic phonetic mapper with hard-coded rules. Confirms the category: these are lossy, rule-only, single-output tools.
- **Google Input Tools / Transliterate API** — the reference *natural-typing* experience ("namaste" → नमस्ते with candidates), but it is **server-backed** (the deprecated API's backend still powers Gboard). Community clients like [`KSubedi/transliteration-input-tools`](https://github.com/KSubedi/transliteration-input-tools) (explicitly built for **Nepali**) are thin clients to that server: **no offline capability, TypeScript bundle, and the maintainer flags incomplete mobile support due to "challenges handling virtual keyboard events on phones."** This is exactly the architecture you must *avoid* (needs a server) but the UX to *match*.
- **Varnam / GoVarnam** ([libvarnam](https://github.com/varnamproject/libvarnam), [govarnam](https://github.com/varnamproject/govarnam)) — the best open-source *architectural model* for what you want: a greedy left-to-right tokenizer over a compiled symbol table (`.vst`) plus a **learned prefix tree with pattern frequencies** that produces ranked candidate matches ("knows >1M Malayalam words and 7M ways to write them"). This is precisely your rule-layer + lexicon + frequency-ranking design, done natively (C/Go). Not a browser lib, but the blueprint for candidate generation + ranking.

Takeaway: use a Sanscript-style deterministic mapper as the zero-download rule fallback, but the *suggestion* behavior (fuzzy/multiple romanizations → top-5) has to come from **your own lexicon+ranking layer** — no off-the-shelf JS library provides it client-side.

## 2. Compact lexicon data structures deployable in JS/WASM

For ~50–100k word→word mappings with frequencies, the realistic contenders, with numbers:

- **Succinct trie (LOUDS / bitstring + rank/select)** — Steve Hanov's classic: **80,000 English words → 216 KB** structure (132 KB gzipped), queried *in place* via `rank()` (O(1) with lookup tables) / `select()` (O(log n)), no client-side decompression, stored as Base64. Caveat: his encoding assumed a-z in 5 bits; Devanagari/Roman needs a wider alphabet, inflating per-node cost. ([Steve Hanov](https://stevehanov.ca/blog/index.php?id=120)) LOUDS-specific JS/C: [matsu-trie](https://github.com/yohokuno/matsu-trie), [fast_succinct_trie](https://github.com/kampersanda/fast_succinct_trie).
- **MARISA-trie** — canonical size numbers: **3M Russian words: 600 MB Python dict → 7 MB (`Trie`) / 11 MB (`RecordTrie`, i.e. keys + a fixed value per key)** — ~86× reduction. Lookup ~1M ops/sec (`Trie`), ~0.6M ops/sec (`RecordTrie`) in Python; C++ core faster. **`RecordTrie` is the key feature**: a fixed-format value (e.g. frequency + vocab-id) per key. The npm `marisa-trie` is a Node native binding (**not** browser) — browser use means compiling the C++ core to WASM yourself. ([benchmarks](https://marisa-trie.readthedocs.io/en/latest/benchmarks.html))
- **DAWG / DAFSA (MA-FSA)** — merges common *suffixes* as well as prefixes, typically smaller than a plain trie for inflected vocab. Pure-JS: [`tiny-trie`](https://github.com/jnu/tiny-trie) builds a trie then `#freeze()` dedupes suffixes into a DAWG and packs it. Good "all-JS, no WASM" option; membership + prefix walk, values need a side array.
- **FST (Lucene-style byte[] transducer)** — the natural fit for **key→value** (Roman spelling → Devanagari id + weight) because an FST *outputs* along the path. No mature browser port exists (it's Java); you'd port or approximate it. ([Lucene FST intro](https://blog.mikemccandless.com/2010/12/using-finite-state-transducers-in.html))
- **Bloom-filter-guarded lookup** — a cheap *gate*: ~**9.6 bits/element at 1% false-positive**, so 100k words ≈ 120 KB, to answer "is this Roman token even in the lexicon?" before a heavier lookup or fetch. JS: [`bloomfilter`](https://www.npmjs.com/package/bloomfilter), [BloomFilter.js](https://github.com/rawify/BloomFilter.js).

**Realistic sizing for 100k pairs (estimate — must be measured):** don't store Devanagari strings per Roman key; deduplicate. Build (a) a unique-Devanagari vocabulary in one succinct trie/DAWG (~50–60k unique words ≈ few hundred KB), and (b) a Roman-key trie whose value is `(vocab-id, freq-rank)` — ~3–5 bytes/key payload. Rough total on the wire: **~0.6–1.5 MB brotli** for the full 100k-pair lexicon + frequencies. A **"top ~3–5k most frequent words" starter shard** fits in **~50–120 KB** and can ship in the core. Source dataset for pruning: **Google's Dakshina** romanization lexicon is the model — note the browser-tech agent believed Dakshina includes Nepali; the academic review confirms it does NOT (12 languages, no Nepali) — pruning source should be Aksharantar/the 2.4M HF dataset instead.

## 3. Tiny neural inference in the browser

For a char-level seq2seq **fallback** (only when lexicon misses), the dominant byte cost is the **runtime, not the model**:

- **ONNX Runtime Web** — JS glue `ort.all.min.js` > 500 KB; the WASM binary ≈ **10 MB default**, ≈ **8 MB** MinSizeRel, ≈ **3 MB** minimal build, and a **custom build with only your model's kernels** can go well below that. Recommended when you own/export the model. Proxy-worker option for off-main-thread inference. ([deploy docs](https://onnxruntime.ai/docs/tutorials/web/deploy.html), [size issue #14817](https://github.com/microsoft/onnxruntime/issues/14817))
- **Transformers.js** — wraps ONNX Runtime Web; convenient but heavy. Quantization: **INT8 (q8) = 4× smaller with ~2–5% accuracy drop; INT4 = 8× smaller**; INT8 on WASM runs **2–3× faster** than FP32. Reference: a ~22M-param model infers in **8–12 ms on WASM on an M2** — a laptop, not a budget phone.
- **TensorFlow.js WASM backend** — explicitly best for **"ultra-lite models (<3 MB, <60M multiply-adds)"**; SIMD gives 1.7–4.5×, multithreading 1.8–2.9× — **but mobile multithreading and iOS SIMD are incomplete**; assume single-threaded WASM on low-end Android.
- **WebGPU on low-end Android: do not rely on it.** Chrome 121+, **Android 12+ with Adreno/Mali only**, initially ~half of even WebGPU-capable devices. WASM (SIMD, single-thread) is the only safe universal backend.
- **Model-size reality:** **IndicXlit is ~11M params** — at INT8 ~11 MB plus runtime, too heavy for per-keystroke. But a **single-pair Roman→Nepali char GRU/LSTM or tiny transformer of ~1–3M params → ~1–3 MB at INT8** is realistic; small char models hit ~98%+ char accuracy on CPU. Feasible **only** as a debounced fallback (fire on pause), never on the <10 ms hot path.

Verdict: neural is **optional, lazy, debounced**. Budget ~4–6 MB (custom ORT WASM + INT8 model), loaded only after idle and cached; the rule+lexicon layer must fully function without it.

## 4. Background / lazy loading on a static GitHub Pages site

- **Progressive enhancement, three tiers:** (1) **rule layer** in the core JS bundle (a few KB), zero extra download; (2) **lexicon shards** stream in background after first paint; (3) **neural runtime+model** loads only on idle/first-miss. The input box must be usable at tier 1 instantly.
- **fetch + IndexedDB caching** for the multi-hundred-KB/MB blobs: fetch the versioned asset once, store the ArrayBuffer in IndexedDB, cache-then-network afterward. Ready-made: [`indexed-cache`](https://github.com/knadh/indexed-cache).
- **Quota & eviction:** modern Chrome grants up to ~60–80% of free disk, but eviction is **LRU per origin and all-or-nothing** — under pressure the browser drops your entire origin's storage at once. Call `navigator.storage.persist()`; always keep network fallback. ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria))
- **Service worker on GitHub Pages:** works (HTTPS, custom domain = root scope). Use only for core offline precache; **prefer explicit fetch+IndexedDB for large blobs** (versioning control, avoids SW update-staleness). GH Pages sends `Accept-Ranges: bytes` (the PDF reader depends on it) so range-fetching lexicon slices is possible, but sharding into separate files is simpler.
- **Don't degrade the site when unloaded:** lazy `import()` / dynamic `<script>`; nothing executes unless the user focuses a Nepali input. Text/reader pages stay JS-free.

## 5. n-gram LM in the browser for candidate re-ranking

- **KenLM** is the reference for compact n-gram LMs (TRIE structure, bit-packing, quantization) but there is **no ready-made KenLM-in-WASM build**; its `.binary` format assumes memory-mapping. ([kpu/kenlm](https://github.com/kpu/kenlm))
- **Pragmatic alternative:** a **pruned, quantized word-bigram table** stored as a RecordTrie/FST or packed array: modest vocab (30–60k words), high-count bigrams only, log-probs quantized to 8 bits. Realistic size **~a few hundred KB to ~1–2 MB brotli**, O(1) lookup — plenty for re-ranking 5 candidates. This mirrors the Dakshina context-aware approach: **FST/pair-n-gram candidate generation + n-gram LM re-ranking remains competitive with neural** ([Kirov et al., CL 2024](https://aclanthology.org/2024.cl-2.2.pdf)).
- Because the re-ranker only scores 5 short candidates against 1–2 words of left context, even a naive JS hash-map bigram store is adequate on the hot path.

## 6. Input handling — the IME-overlay minefield on mobile

- **`keyCode`/`keydown` is unreliable on Android.** During composition (often for every key) Gboard/Android Chrome report **`keyCode: 229`**; `isComposing` is inconsistent; Android does not guarantee key events at all. **Never key logic off `keyCode`.** ([keyCode 229 writeup](https://minjung-jeon.github.io/IME-keyCode-229-issue/))
- **Use `input` / `beforeinput` + composition events.** `input` fires universally on any value change; `beforeinput` gives incoming `data` and allows `preventDefault()`. Track `compositionstart/update/end` to suspend candidate logic while the OS IME composes.
- **Event-ordering bugs:** Safari fires `compositionend` **before** `keydown` (double-Enter hazard); other browsers the opposite. Guard with a deferred `isComposing` flag. ([Square blog](https://developer.squareup.com/blog/understanding-composition-browser-events/))
- **Turn off platform "help":** `autocorrect="off" autocapitalize="none" autocomplete="off" spellcheck="false"`, or the OS keyboard rewrites the Roman buffer under you.
- **`contenteditable` on Android is the hardest surface** — soft keyboards break selection/DOM mid-composition (Slate's long-running issue). Prefer a plain `<input>`/`<textarea>` with a **separately positioned candidate overlay**, placed via caret coordinates + the **`visualViewport` API** so the virtual keyboard doesn't cover it.
- **Candidate overlay strategy:** maintain your own Roman composition buffer in JS, render top-5 in an absolutely-positioned popup, commit on space/number-key/tap, re-run the debounced pipeline on `input`. Debounce lexicon lookup to keystrokes and neural fallback to pauses.

## Recommended reference architecture

**Core — target ≤ 60 KB gzip, works instantly:**
- Deterministic **rule mapper** (~10–15 KB) — the zero-download floor.
- **Input controller**: plain input + own composition buffer + candidate overlay, driven by `input`/`beforeinput`/composition events, `visualViewport`-aware (~15–25 KB).
- **Starter lexicon shard** (~3–5k most-frequent words, packed DAWG/succinct trie + freq) — ~50–120 KB (borderline; can defer).
- Optional **Bloom filter** (~120 KB for 100k) as a lookup/fetch gate.

**Optional tier 1 — full lexicon (streams after first paint):** 50–100k Roman→(Devanagari-id, freq) as FST or MARISA RecordTrie in WASM, plus a deduped Devanagari succinct trie. **Est. ~0.6–1.5 MB brotli — MEASURE.** Pure-JS fallback: tiny-trie DAWG. Fold normalized keys into the same trie as extra edges pointing at the same vocab-ids.

**Optional tier 2 — word-bigram re-ranker:** pruned INT8 bigram table, **est. ~0.3–1.5 MB brotli**.

**Optional tier 3 — neural fallback (lazy, idle-loaded, debounced, cached):** custom-built ORT WASM (single-thread SIMD; no WebGPU assumption) + INT8 char seq2seq (~1–3M params → 1–3 MB). **Est. total ~4–6 MB.** Runs only on lexicon miss + input pause, in a Web Worker.

**Loading/plumbing:** dynamic `import()`; fetch→IndexedDB (versioned keys) for Optional blobs; `navigator.storage.persist()`; network fallback on cache miss; minimal SW for core offline only. All of it off non-input pages.

## Risk list — what commonly breaks browser IMEs

1. **`keyCode 229` / missing key events on Android** — mitigate with `input`/`beforeinput` + composition events.
2. **Native autocorrect fighting your buffer** — disable all four auto-* attributes.
3. **Composition-event ordering divergence** (Safari) → double Enter — deferred `isComposing` flag.
4. **`contenteditable` corruption on Android** — plain input + external overlay.
5. **WebGPU assumed present** — WASM-only, single-thread SIMD baseline.
6. **WASM runtime dwarfs the model** (3–10 MB ORT vs 1–3 MB model) — custom minimal build, lazy load, off-thread warm-up.
7. **IndexedDB LRU all-or-nothing eviction** — `persist()` + network fallback + versioned re-fetch.
8. **Service-worker staleness** — versioned asset URLs; don't SW-cache the big blobs.
9. **Main-thread jank** — Web Worker for anything heavier than the in-RAM trie walk; debounce.
10. **Node-only "browser" libs** (`marisa-trie` npm, Lucene FST are not browser-ready) — plan the WASM compile or pick pure-JS tiny-trie.
11. **Overlay occluded by the virtual keyboard** — `visualViewport` positioning.
12. **Per-keystroke neural calls** — neural fires only on miss + pause.

## The 3 most load-bearing findings

1. **The hot path is a data-structure problem, not an ML problem.** A compact lexicon (FST / RecordTrie / succinct-DAWG, ~0.6–1.5 MB brotli for 100k pairs) with frequency-weighted candidate generation and a small word-bigram re-ranker delivers the <10 ms, top-5 experience; **neural belongs only as a lazy, debounced, off-thread fallback** (its WASM runtime alone is 3–10 MB). Research backs this: FST/pair-n-gram + lexicon + LM re-ranking is competitive with neural for isolated words (Kirov 2024).

2. **Off-the-shelf JS transliteration libraries won't give natural typing.** Sanscript.js et al. are deterministic single-output scheme converters (fine as the zero-download rule floor); Google Input Tools clients need a server. The suggestion/ranking behavior must be your own lexicon+frequency layer — the Varnam (prefix-tree + learned pattern frequencies) design is the model to copy.

3. **Mobile input handling is the highest-risk surface, independent of the pipeline.** Android reports `keyCode 229` and unreliable key events, autocorrect fights the buffer, composition ordering differs across browsers, `contenteditable` corrupts under soft keyboards — build on `input`/`beforeinput`+composition events over a plain input with an external `visualViewport`-positioned overlay, disable auto-*, and progressively enhance so the rules layer works with zero download.

**Sources:** sanscript.js · KSubedi/transliteration-input-tools · Varnam/GoVarnam · Steve Hanov succinct trie · MARISA benchmarks · tiny-trie · Lucene FST · ONNX Runtime Web deploy docs · ORT size issue #14817 · Transformers.js docs · TF.js WASM backend · web.dev WebGPU · IndicXlit · Dakshina · Kirov CL 2024 · IndoNLP 2025 (arXiv:2501.05816) · KenLM · indexed-cache · MDN storage quotas · keyCode-229 writeups · Square composition-events blog.
