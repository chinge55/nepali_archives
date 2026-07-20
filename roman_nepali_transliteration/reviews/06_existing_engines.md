# Review 6: Existing engines & cross-language implementations (Opus 4.8 agent, 2026-07-20)

**Scope.** We want fuzzy *natural* typing ("mero naam ho" → मेरो नाम हो), a top-5 candidate dropdown, and next-word conversion with short-context re-ranking, running **entirely on a static site** (no server). That constraint is what separates "reuse this" from "overkill" below.

**Bottom line up front.** This wheel is largely invented. There is a production, open-source, *offline* reference implementation that matches our spec almost line-for-line — OpenBangla's `riti` (Bengali). There is enough open, permissively-licensed Nepali data to feed it (Aksharantar ~2.4M pairs; a Quillpad Nepali model). And there is one genuinely greenfield piece: **no Indic transliteration engine reviewed does next-word / short-context re-ranking** — that layer exists only in the CJK IMEs and Google's word-n-gram FST, so we lift it from there.

---

## Inventory by system

### 1. Avro Keyboard / OpenBangla / `riti` — the closest success story (Bengali)
- **What it is.** Avro Phonetic is the wildly successful Roman→Bengali phonetic input method; OpenBangla Keyboard is its open-source reimplementation, powered by the **`riti`** engine. This is the single most on-target prior art: natural typing + ranked candidate dropdown + autocorrect + user-selection learning, all offline.
- **Algorithm/architecture** (read from `src/phonetic/suggestion.rs`). Per word: `SplittedString::split()` peels leading/trailing punctuation → **rule-based phonetic parser** (`Parser::new_phonetic`, the *rupantor* engine) converts the Roman word to a base Bengali string → **dictionary lookup** `dict.suggest(word)` finds real Bengali words → **autocorrect** (`user_autocorrect` HashMap first, then the static table) gets top priority → **suffix handling** `add_suffix_to_suggestions()` reattaches agglutinative endings with morphological joining → results ordered **autocorrect > dictionary(+suffix) > phonetic fallback (rank 2) > raw English (rank 3)**, then sort → **user-selection memory**: a `selections` HashMap records the last chosen word and re-ranks it to the top next time. The rule layer (rupantor) is a **JSON grammar** of `find`/`replace` patterns with context rules keyed by `type` (prefix/suffix) and `scope` (`vowel`/`consonant`/`punctuation`/`exact`, each negatable).
- **Data sizes (shipped as static files):** `dictionary.json` **4.09 MB**, `autocorrect.json` **138 KB**, `suffix.json` **23 KB**. Plain JSON — gzips well, loads into memory in a browser.
- **Code/license.** `OpenBangla/riti` — **Rust, MPL-2.0**, active. `OpenBangla/OpenBangla-Keyboard` — C++, GPL-3.0. **JS ports:** `torifat/jsAvroPhonetic` (**MPL-1.1**, browser, *deterministic single output*); `wahidsadik/nodejs-avro-phonetic`; `hitblast/avro.py`. `OpenBangla/rupantor-rs` (**Rust, MPL-2.0**). `mhshajib/avro-phonetic-go` (**MIT**): trie longest-match + context prefix/suffix/scope rules, deterministic.
- **Perf.** ~1.2× faster dictionary search than the old C++ engine; runs resident with no server.
- **Steal this:** the **entire riti pipeline is our blueprint** — port the four-tier ranking + user-selection memory to JS; reuse the rupantor/jsAvroPhonetic **JSON-grammar rule-table format** for the base layer; note the **suffix layer maps directly onto Nepali's** -हरू/-मा/-को/-लाई/-सँग agglutination.

### 2. Quillpad (Tachyon) — statistical reverse-transliteration, ships a Nepali model
- **What it is.** Pioneered predictive Roman→Indic transliteration (2006); 16 Indian languages + Urdu/Arabic; processed 1B+ words. Source: Ram Prakash H, *"Quillpad Multilingual Predictive Transliteration System,"* COLING 2012 WTIM-2 (https://aclanthology.org/W12-4810.pdf).
- **Algorithm/architecture.** **One CART decision-tree ("pronunciation tree") per Roman character**, classifying which target character(s) it produces, conditioned on position, following consonant, and character class. A hand-written **regex "language-definition" file** enumerates, per target character, the Roman letters a user might type (many-to-many). **No parallel corpus needed** — training data is *synthesized* by running those rules over a monolingual corpus (word frequency folded in, so each tree doubles as a char-LM). **Candidate generation** = run per-char trees; **ranking** = beam search over tree log-probs, then **re-order by a word-level LM**. English words detected via a dictionary and routed to separate trees. (Verified: the shipped `Nepali_Xlit.xml` is a **phoneme-intermediary, context-sensitive regex producer** file — Roman → phoneme codes like `_ah_`/`_aa_` → Devanagari, conditioned on preceding phonemes.)
- **Code/license.** `teamtachyon/quillpad-server` — **BSD-3-Clause**, Python 2.7 + a C extension, **dormant (last push 2017)**. **Ships a Nepali model** (verified): `Nepali_Xlit.xml` (10 KB rules), `Nepali_New.xml`, `Nepali_Mangal.xml`, `nepali.tar.bz2` (**1.1 MB trained model**). Server, not client-side — reuse the data/rules.
- **Steal this:** the **per-char tree → beam → word-LM re-rank** pattern; the **synthesize-training-from-a-monolingual-corpus + regex mapping** trick; and the **BSD-licensed Nepali rule file** as a starting rule set.

### 3. Varnam / GoVarnam — the closest *fully-offline* engine architecture
- **What it is.** A learning-based Indic transliteration library (15 language schemes incl. **Nepali `ne`**; Malayalam strongest). GoVarnam is a near-complete Go rewrite of the older C `libvarnam`.
- **Algorithm/architecture** (from `govarnam.go`, `learn.go`, `dictionary.go`). Three stores, two SQLite:
  - **VST (`<lang>.vst`, SQLite):** a `symbols` table mapping a Roman `pattern` → `value1` (independent form), `value2` (matra form), `value3`, plus `tag`, `match_type`, `priority`, and a **`weight` column**. Malayalam has ~7,410 symbol rows. Read-only.
  - **Learnings DB (separate SQLite):** `words(id, word, weight, learned_on)` + `patterns(pattern, word_id)` (learned Roman→word for non-phonetic/English words).
  - Conversion = a **greedy longest-match tokenizer** walking input left→right against the VST. Concurrent buckets merged: `ExactMatches`; `DictionarySuggestions` (`ORDER BY weight DESC LIMIT 5`); `PatternDictionarySuggestions`; `GreedyTokenized` (deterministic fallback, shown 2nd); `TokenizerSuggestions` (≤10). `SortSuggestions` orders by `weight` then `learned_on`. **Top-5 falls straight out of the defaults.** Pure frequency ranking — no neural net, **no cross-word context.**
  - **Learning:** `Learn(word)` → `UPDATE words SET weight = weight + 1` — every confirmed word bubbles up. `Train(pattern, word)` stores exact Roman→word for custom/English words. `LearnFromFile` bulk-imports `word<space>frequency` corpus lists (their Wikipedia crawler produces downloadable **VLF "language packs"** for pre-training).
- **Code/license/stack.** Go (cgo `c-shared`), bindings for Java/Rust/Go + `varnamcli`. **⚠ GoVarnam is AGPL-3.0** (`LICENSE.txt` is GNU AGPL v3; GitHub shows NOASSERTION only due to the filename) — strong network-copyleft. **The *old* `libvarnam` is MPL-2.0** (permissive). Actively maintained.
- **In-browser: NO true client-side port exists.** No WASM target; cgo `c-shared` is incompatible with Go's `js/wasm` target. All browser usage goes through a hosted HTTP daemon (`varnamd-govarnam`) with JS UI shells. But the algorithm is simple enough to reimplement in JS.
- **Size/perf.** Language packs are tens of MB of SQLite; the symbol table itself is small (thousands of rows). Tokenizer + SQL lookups are microsecond-fast, CPU-only.
- **Steal this:** the whole static-site-friendly recipe — **greedy longest-match symbol tokenizer + frequency-weighted word dictionary + learning = `weight++` on selection in local storage**, seeded from a corpus frequency list. **Port the algorithm (or start from MPL-2.0 libvarnam) — do not link the AGPL GoVarnam.**

### 4. Google Input Tools / Gboard transliteration lineage
- **What it is.** On-device Gboard transliteration keyboards (22 Indian langs, 2017) + the Google Input Tools web API. (Note: there is **no Google transliteration system called "Duet"** — that's Google's unrelated Workspace assistant.)
- **Algorithm/architecture.** Hellsten et al., *"Transliterated Mobile Keyboard Input via WFSTs,"* FSMNLP 2017 (https://aclanthology.org/W17-4002.pdf): a **pair (joint multi-gram) language model** — Roman↔native strings EM-aligned into pair symbols (`sha:श`), an n-gram trained over them (OpenGrm), encoded as a **weighted FST** `T = I∘P∘O`; decode by **on-the-fly composition of `C∘T` with a lexicon+grammar `L∘G`**. **Next-word prediction, completion, and error correction all fall out of the same graph** (traverse `L∘G`). Packed with LOUDS + 8-bit quantization.
- **Size/perf.** `C∘T` ≈ 1.7 MB, `L∘G` ≈ 6.7 MB → **~10 MB aggregate**, **<20 ms/word**, WER Hindi 16.4%, trigram, 150k vocab. A 2024 successor swaps `G` for a neural LM converted to FST at runtime (arXiv:2410.15575).
- **Code/license.** Models **closed**; community wrappers just call Google's cloud endpoint (which is winding down — a fragility, since most Nepali web tools depend on it). Toolkits are open: **OpenFst + OpenGrm (Apache-2.0)**. **Dakshina dataset** (**CC BY-SA 4.0**): romanization lexicons + parallel sentences for 12 languages — **but NOT Nepali** (the method/format transfer, the data doesn't).
- **Steal this:** the **pair-n-gram WFST as candidate generator + a word n-gram `G` giving next-word prediction and short-context re-rank in one graph** (one of only two places short-context re-ranking is actually built). A pruned trigram in a compact FST is plausibly WASM-shippable.

### 5. AI4Bharat IndicXlit / Aksharantar — best Nepali *data* + a ready MIT UI widget
- **What it is.** A neural romanized↔Indic transliteration model (21 languages incl. **Nepali**) trained on Aksharantar, deployed as a Python lib + hosted API + React widget. Paper: EMNLP-Findings 2023.
- **Algorithm/architecture.** **Transformer seq2seq (fairseq): 6 enc + 6 dec, d_model=256, 4 heads, FFN 1024, ~11M parameters.** Character-level, multilingual one-to-many (target-language tag token). Candidates = **beam search (default 4) → top-k**; optional **`rescore=True` re-ranks the beam against a dictionary** (the closest any Indic engine gets to re-ranking, but still word-isolated).
- **Nepali data specifics.** Aksharantar Nepali = **~2.4M train / 3K val / 4,133 test pairs.** Fields: `native word`, `english word`, `source`, `score`. Full corpus: 26M pairs, 21 langs / 12 scripts, **729 MB**.
- **Deployment — server/on-device, NOT in-browser.** `ai4bharat-transliteration` (PyPI) runs the fairseq checkpoint on CPU in Python. `xlit_server` is Flask (`GET /tl/{lang}/{word}`). `@ai4bharat/indic-transliterate` (npm) is a **React UI component only** — fetches from the AI4Bharat API (`customApiURL` escape hatch), caches ≤10k words/lang client-side, logs selections to central telemetry. **No ONNX/quantized/WASM/in-browser model anywhere.**
- **Code/license.** Code + models **MIT**; **Aksharantar CC0 (mined) / CC-BY (manual).** +15% over the Dakshina benchmark.
- **Steal this:** the **data, not the deployment** — Aksharantar gives free Nepali pairs to build our frequency dictionary + bigram + candidate rules, or to distill a *tiny* char seq2seq → ONNX → onnxruntime-web as an in-browser novel-word fallback (nobody has shipped the browser build — open ground). Plus the **MIT React widget as a ready UI shell**, and the "beam top-k then dictionary rescore" pattern.

### 6. libindic / indic-trans (IIIT-H) & SILPA
- **What it is.** `libindic/indic-trans` — a rule+statistical hybrid for cross-transliteration among ~15 Indian languages + English/Urdu (incl. **Nepali `nep`**), from the FIRE-2014 transliterated-search work.
- **Algorithm/architecture.** An **averaged structured perceptron** (Collins-style linear-chain sequence labeler): `coef.npy` emission weights + `intercept_{init,trans,final}.npy` transition scores; features = a **4-gram character context window**, one-hot; decoding = **Viterbi (1-best) / beam (k-best)** in Cython. Rule-based WX-charmap mode is the default. Word-level only, **no cross-word context.**
- **Code/license/stack.** Python/Cython (numpy+scipy), **~19 MB per language-direction**. **AGPL-3.0, dormant since Oct 2022.** SILPA's translit module was the older rule-based `libindic/Transliteration`, not indic-trans; both dormant.
- **Steal this:** little directly (AGPL + unmaintained). Use as a **Nepali baseline/reference**; the light GPU-free k-best recipe (emission + transition scores → Viterbi/beam) is portable to JS typed-arrays, but riti/Varnam cover this better with cleaner licenses.

### 7. Yamli & Arabizi (Arabic chat-alphabet → Arabic) — the UX reference
- **What it is.** yamli.com: commercial, real-time Arabizi→Arabic with a **live candidate dropdown** — essentially our exact UX.
- **Algorithm/architecture.** No engine paper; described as a **probabilistic language model** (explicitly not a rigid rule table) trained on web-crawled Arabic, handling numerals (`3→ع`, `7→ح`) and many spellings per word. **UX to copy:** dropdown with **first item = default**, the **literal Latin word pinned to the top**, a **"show more"** tail, and it **remembers the user's preferred choice** client-side.
- **Code/license.** **Closed**, JS widget only. Open Arabizi engines are neural and server-bound.
- **Steal this:** the **dropdown interaction** — default=top, pin the literal, "show more," persist the user's per-word pick locally for cheap adaptive re-ranking with no server.

### 8. CJK IMEs (Mozc / libpinyin / RIME) — the decoder + short-context lessons
- **Shared pipeline.** `romanized input → dictionary builds a lattice of candidate arcs (each carrying a frequency cost) → an n-gram/connection model scores transitions → Viterbi/beam picks the min-cost path → n-best = ranked candidates → user-history store re-ranks.`
- **Mozc** (Google Japanese Input, **BSD-3**, C++): two **LOUDS tries** (reading + surface) + token array; a **connection matrix** (POS-class *bigram*); **Viterbi cost-minimization**; `UserHistoryPredictor` = **LRU of ~5000** committed conversions + bigram chains.
- **libpinyin** (**GPL-3**, C++): **double-array trie** phrase index; **bigram+trigram interpolation**; runtime user bigram cache.
- **RIME/librime** (**BSD-3**, C++, the most transferable): `Prism` = Darts **double-array trie** (`CommonPrefixSearch` segments input) → `Table` = `Code→Entry{text, weight=log-freq}` → **`Poet`** decoder builds a `WordGraph` lattice; **`ContextualTranslation` re-ranks candidates using `preceding_text`** (literally our short-context re-rank). The **octagram LM** (`librime-octagram`, GPL-3; data LGPL-3) is a **Darts trie of (context, word) collocations up to 4 chars, with backoff to shorter context suffixes and tunable penalties**. User dict in LevelDB.
- **Steal this:** the **skeleton** — trie segmenter + word-frequency cost + **additive cost ranking** + **bigram-with-backoff next-word re-rank** (octagram) + **local history LRU**. One of only two prior arts that actually implement short-context re-ranking. **Overkill for us:** multi-word Viterbi lattices (we convert one word at a time), POS connection matrices, trigram interpolation, and compiled double-array/LOUDS binaries (we can gzip a JSON word-freq map instead).

### 9. Sinhala (Singlish) & Greeklish — bracketing the difficulty
- **`remeinium/singlish`** (`@siyabasa/singlish`, **Apache-2.0, TypeScript, browser**): deterministic two-stage — **trie of 400+ phoneme patterns, greedy longest-match**, then a **state machine** for inherent vowels / matras / conjunct shaping. O(n), single output. **Closest match to our deterministic base layer** (exactly the schwa+matra+halant problem).
- **Swa Bhasha** (arXiv:2404.13350): maps a consonant skeleton, then **fuzzy-matches against a native word list** to rescue vowel-dropped input, returning best + a suggestion list (84% word / 92% suggestion). Lesson: **dictionary-backed fuzzy match beats pure rules when users drop vowels.**
- **Helakuru** (proprietary): phonetic mapping + **self-learning prediction dictionary**.
- **Greeklish:** `alexkaf/g2g_converter` — OpenFST **two-stage translator + orthographer, edge weights = log-freq, min-cost path**. `nlpaueb/greeklish` (**Apache-2.0**) finds a 20-yr-old statistical model still competitive with neural — validates staying lightweight. **Key lesson:** Greeklish is *heavy-ambiguity*; **Devanagari is near-injective**, so we land near the deterministic-rules end and only need a light dictionary/freq re-rank for genuine ambiguities (schwa, ि/ी, ु/ू, स/श/ष, न/ण, व/ब, word boundaries).

### 10. Nepali-specific landscape
- **The gap:** there is **no open-source Nepali Roman→Devanagari engine with candidates + learning.** Open Nepali web converters are all **deterministic single-output rule tables**: `foss-np/unicode` (MIT, Electron/JS), `codexen/nepali-typing` (jQuery map), `nirooj56/nepaliunicode`, `ankitpokhrel/NepaliUnicode`, `amarnaths0005/Translitera` (10 scripts, pure-JS rule maps). Popular typing sites (easynepalityping, ashesh.com.np) mostly **call Google's closed transliteration API** (a dependency risk). Hamro Patro's keyboard is proprietary/deterministic (`/` to break wrong joins, `*` anusvara, `**` chandrabindu).
- **Closest Nepali candidate-capable thing:** `sushil79g/Nepali_nlp` (**MIT, Python**) — model-based `translit_word("Hello", topk=3)` → `['हेल्लो','हेलो','हेललो']`; server-side only.
- **Reusable Nepali base map:** `indic-transliteration/sanscript.js` (**MIT, browser**) — strict-scheme ITRANS/HK, deterministic, no fuzzy/candidates (a base-layer map source via `@indic-transliteration/common_maps`, not a solution).

---

## Composite architecture the wheel already suggests

Every successful system (riti, Varnam, Quillpad, Google-WFST, RIME) converges on the **same layered word-level design**, which maps cleanly onto a static site with everything shipped as gzip'd JSON assets:

1. **Deterministic base layer** — a **trie of multi-character Roman units + greedy longest-match + a small state machine** for schwa deletion, matras, halant, and conjuncts (siyabasa, avro-phonetic-go, rupantor, RIME `Prism`). Produces the phonetic skeleton.
2. **Candidate generation** — the rule layer emits **multiple spellings** wherever Roman→Devanagari is ambiguous (schwa, ि/ी, ु/ू, स/श/ष, न/ण, व/ब), à la Varnam's combination tokenizer / Quillpad's per-char trees.
3. **Dictionary re-ranking** — a shipped **Devanagari word → log-frequency map**; real words float above phonetic nonsense; **score = phonetic-rule cost + (−log word_freq)**; **top-5 = sort candidates by score**. At word level this is a sort, *not* a Viterbi lattice.
4. **Autocorrect / loanword layer** — a small high-priority table pinning common mistypes and English loanwords (riti `autocorrect.json`; Varnam `patterns` table).
5. **Next-word short-context re-rank** — a compact **word bigram `prev_word → {word: logprob}` with backoff to unigram + a penalty**, re-scoring the current word's candidates using the previous committed word (RIME octagram, Google `G`, Quillpad word-LM). **This is the layer no Indic engine builds** — it's our differentiator, lifted from CJK/Google.
6. **User-selection learning** — an LRU of committed picks in **localStorage/IndexedDB** that boosts/pins the user's earlier choices (riti `selections`, Mozc `UserHistory`, Varnam `weight++`, Yamli persistence, Helakuru).
7. **(Optional) suffix/morphology join** — riti's suffix layer reattaches agglutinative endings; **directly applicable to Nepali** -हरू/-मा/-को/-लाई/-सँग.

Footprint of the proven design: low hundreds of KB to a few MB of static assets, zero server. **Skip** (overkill or license-tainted for a static site): seq2seq transformers (IndicXlit), multi-word Viterbi + POS connection matrices + trigram interpolation (CJK), compiled LOUDS/double-array binaries, and the AGPL engines.

---

## Directly reusable artifacts (with licenses)

| Artifact | What / why | License |
|---|---|---|
| `OpenBangla/riti` (Rust) | **The reference pipeline** — port its rule→dictionary→autocorrect→suffix→learning ranking to JS/WASM | **MPL-2.0** |
| `torifat/jsAvroPhonetic` (JS) + `OpenBangla/rupantor-rs` (Rust) | Rule engine + **JSON-grammar format** (find/replace + prefix/suffix/scope) for the deterministic base layer | MPL-1.1 / **MPL-2.0** |
| `teamtachyon/quillpad-server` | Ships **Nepali rule file (`Nepali_Xlit.xml`) + trained model (`nepali.tar.bz2`, 1.1 MB)** — inspect/port | **BSD-3-Clause** |
| `ai4bharat/Aksharantar` (HF dataset) | **~2.4M Nepali Roman↔Devanagari pairs** — build the freq dictionary + bigram + candidate rules (or distill a tiny model) | **CC0 (mined) / CC-BY (manual)** |
| `AI4Bharat/indic-transliterate-js` (React) | **Ready-made UI shell** (candidate dropdown, trigger keys); repoint `customApiURL` at a local engine | **MIT** |
| `varnamproject/libvarnam` (old C engine) | Permissive base if we port the symbol-table + tokenizer algorithm | **MPL-2.0** |
| `indic-transliteration/sanscript.js` + `common_maps` | Browser scheme maps for strict base transliteration (a map source, not a candidate engine) | **MIT** |
| Google **Dakshina** + OpenFst/OpenGrm | Method + Hindi/Marathi lexicon format (⚠ **no Nepali**); toolkits to build a pair-ngram WFST if we go statistical | CC BY-SA 4.0 / Apache-2.0 |
| `librime-octagram` (concept/data) | Bigram-backoff-with-penalties pattern for next-word re-rank | GPL-3.0 / data LGPL-3.0 |
| `sushil79g/Nepali_nlp` | Nepali `topk` transliteration reference (Python) | MIT |
| ⚠ `varnamproject/govarnam` | Best offline *architecture* to copy, covers Nepali — but **AGPL-3.0** (network-copyleft). Copy the algorithm; **don't link it.** | **AGPL-3.0** |
| ⚠ `libindic/indic-trans` | Covers Nepali w/ k-best beamsearch, but **AGPL-3.0 + dormant since 2022** — reference/offline-tooling only | AGPL-3.0 |

---

## The 3 most load-bearing findings

1. **Don't build from scratch — port `riti`.** OpenBangla's `riti` (Bengali, MPL-2.0) is a complete, production, *offline* implementation of almost exactly our spec: fuzzy phonetic typing → ranked candidates → autocorrect → **user-selection learning**, with data shipped as static JSON (`dictionary.json` 4 MB, `autocorrect.json` 138 KB, `suffix.json` 23 KB). Its architecture — rule-based base conversion → dictionary/frequency re-rank → four-tier candidate ordering → remembered user picks — is the wheel, and its suffix layer maps onto Nepali agglutination. GoVarnam offers the same offline recipe (symbol tokenizer + `weight++` learning) as a cross-check.

2. **A static site wants the lightweight convergent design — and a clean-license source path.** Because Devanagari is near-injective (unlike Greeklish/pinyin), the proven stack is: trie + greedy-longest-match rules → word-frequency dictionary → tiny word-bigram-with-backoff → localStorage learning — a few hundred KB, zero server, most of the quality. Skip seq2seq transformers and multi-word Viterbi/POS lattices. **License rule:** build from **MPL/MIT/CC0** sources — `riti` (MPL-2.0), old `libvarnam` (MPL-2.0), IndicXlit code (MIT), Aksharantar data (CC0/CC-BY), the AI4Bharat React widget (MIT) — and **avoid the AGPL engines** (GoVarnam, indic-trans): copy their algorithms, don't link them.

3. **For Nepali the gap is data-assembly, and the data + UI already exist — but next-word re-ranking is genuine greenfield.** No open Nepali candidate-engine exists (open tools are deterministic tables or call Google's closing API), yet **Aksharantar gives ~2.4M CC-licensed Nepali pairs** and **Quillpad ships a BSD-licensed Nepali model/rules** — enough to derive the frequency dictionary, bigram, and candidate rules; the UI shell is solved by AI4Bharat's MIT React widget + Yamli's UX. Crucially, **every Indic engine reviewed (GoVarnam, IndicXlit, indic-trans) is word-isolated — none does short-context/next-word re-ranking.** That layer is proven only in the CJK IMEs (RIME `ContextualTranslation` + octagram bigram-backoff) and Google's word-n-gram FST — lift it from RIME/Google, not from the Indic prior art.
