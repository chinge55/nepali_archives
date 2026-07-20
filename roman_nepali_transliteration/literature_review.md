# Roman Nepali → Devanagari: Literature Review & Build Document

*Reconciled from six parallel reviews (2026-07-20): academic literature, products & UX,
browser technology, datasets & evaluation, Nepali linguistics, and existing engines.
Full reports with sources live in [`reviews/`](./reviews/). This document is the
synthesis: what exists, what we reuse, how we build it, and the draft research plan.*

---

## 1. Verdict up front

**The wheel is largely invented, and it is symbolic, not neural.** Every successful
system — Google's Gboard transliteration (WFST, shipped for 22 languages at ≤20 ms
and ~10 MB), OpenBangla's `riti` (Bengali, the closest open-source match to our exact
spec), Varnam, Quillpad, RIME/Mozc — converges on the same layered design:

> rules generate candidates → a frequency-weighted lexicon ranks them → a small
> context model re-ranks → user selections are learned locally.

The academic evidence says the same thing: Dakshina showed a **6-gram pair model
lands within ~1–2% CER of tiny neural seq2seq** for word transliteration, and a
small n-gram LM re-ranker **halves sentence error and beats end-to-end neural**.
Neural models are not needed for the base engine; if ever added, they are a lazy,
debounced fallback (the WASM runtime alone costs 3–10 MB — more than the model).

**What does NOT exist** (our contribution):
1. No open-source Nepali Roman→Devanagari engine with candidates + learning — open
   Nepali tools are deterministic single-output rule tables, or thin wrappers around
   Google's closed (and winding-down) API.
2. **No Indic engine anywhere does short-context / next-word re-ranking** (GoVarnam,
   IndicXlit, indic-trans are all word-isolated). That layer exists only in CJK IMEs
   (RIME's octagram bigram-backoff) and Google's word-n-gram FST. It is our genuine
   greenfield.
3. No Nepali natural-typing benchmark exists (Dakshina and IndoNLP-2025 both exclude
   Nepali). We will have to build a small one — after the POC.

## 2. The convergent architecture (what we build)

Seven layers, all shipping as static assets on GitHub Pages, no server:

| # | Layer | Source of the design | Cost |
|---|---|---|---|
| 1 | **Deterministic rule base** — trie of Roman multigraphs, greedy longest-match, state machine for schwa/matra/halant/conjuncts | riti's rupantor JSON grammar; `@siyabasa/singlish` (Apache-2.0, exactly Devanagari-shaped problems); Quillpad's BSD Nepali rule file | ~10–15 KB, zero download beyond core |
| 2 | **Candidate generation** — rules emit *multiple* spellings at each ambiguity (त/ट, स/श/ष, ब/व, न/ण, ि/ी, schwa) | Varnam tokenizer; Quillpad per-char trees; our own ambiguity-class table (reviews/05 §3) | in layer 1 |
| 3 | **Lexicon lookup with normalization keys** — `normalize(input)` and `normalize(romanize(word))` provably meet in one key space; ranking = rule cost + (−log word freq) | Our `devanagari_slug.romanize()` already defines the collapse (reviews/05 §1, §4); riti `dictionary.json`; Varnam `ORDER BY weight DESC LIMIT 5` | ~0.6–1.5 MB brotli for 50–100k words, streamed after first paint |
| 4 | **Autocorrect / loanword pass-through** — high-priority table for common mistypes + English-word detector that keeps Latin verbatim | riti `autocorrect.json` (138 KB); Gboard's "literal pass-through" for OOV | tens of KB |
| 5 | **Short-context re-rank** — word bigram `prev → {word: logprob}` with backoff to unigram + penalty, rescoring the current word's top-5 | RIME octagram; Google's `G` FST; Dakshina noisy-channel (halved WER) | ~0.3–1.5 MB brotli, optional stream |
| 6 | **User-selection learning** — LRU of committed picks in localStorage boosting earlier choices | riti `selections`; Varnam `weight++`; Mozc UserHistory; Yamli | free |
| 7 | *(later)* **Suffix/morphology join** — reattach -हरू/-मा/-को/-लाई/-सँग to dictionary stems | riti `suffix.json` (23 KB) — maps directly onto Nepali agglutination | small |

A tiny neural fallback (distilled char seq2seq → ONNX WASM, ~4–6 MB total) is
**explicitly deferred**: the literature says it wouldn't beat the symbolic stack on
words, and the POC must prove the path first. If layers 1–5 leave a measurable OOV
gap, revisit.

Progressive enhancement is structural: layer 1 works instantly with zero download;
layers 3/5 stream in the background (fetch → IndexedDB, versioned,
`navigator.storage.persist()`); nothing loads on reader pages — same policy as
pdf.js (viewer-page-only), so text pages stay JS-free.

## 3. The UX contract (from products review — non-negotiable list)

Google Input Tools is the reference interaction; every Nepali typing site imitates it.

- **Space/Enter commits candidate #1**; number key / tap / ↑↓ picks another. 95% of
  typing must need zero interaction with the list.
- **Backspace reopens candidates** for the last committed word — the one-key fix.
- **Literal-Latin escape hatch** always available (English words, names) — and
  discoverable, not a memorized symbol.
- **Never fail closed**: unknown input still yields best-effort Devanagari.
- **Copy is the primary action** (big button, "कपी भयो" toast) — the user's actual
  goal is to paste elsewhere or search.
- **Mobile**: candidates rendered *above* the input (fingers occlude below), touch
  targets ≥48dp, works against Gboard/iOS autocorrect.
- **Do not** ship a rules-only converter as the product (ashesh.com.np model — forces
  escape-syntax memorization); **do not** hide candidates behind an extra gesture;
  **do not** depend on the network (easynepalityping dies with Google's API).

Note: Google's transliteration backend is still live in 2026 and reachable from a
static page via JSONP (no CORS; `itc=ne-t-i0-und`). Deprecated + network-dependent →
**not core**. At most a later optional enhancer; the POC ignores it.

## 4. Engineering constraints (from browser review)

- **Mobile input is the highest-risk surface.** Android reports `keyCode 229` and
  doesn't guarantee key events; build on `input`/`beforeinput` + composition events,
  a plain `<textarea>` with an external overlay positioned via `visualViewport`,
  and `autocorrect/autocapitalize/autocomplete/spellcheck` all off. No
  `contenteditable`. (The most-cited Nepali JS client refuses mobile outright —
  this is where we must be better.)
- **Hot path is a data-structure problem**: packed trie/DAWG lookups in <10 ms.
  POC can use a plain JS map from a gzipped JSON shard; succinct-trie/WASM
  compression is an optimization stage, not a POC requirement.
- Beware Node-only "browser" libs (marisa-trie npm, Lucene FST); pure-JS `tiny-trie`
  or a hand-packed format are the realistic options later.

## 5. Data plan (from datasets review)

- **Primary pairs: Aksharantar-nep** — the HF set in our brief
  (Saugatkafley/Nepali-Roman-Transliteration) turned out to be **Aksharantar's
  Nepali train+val re-hosted** (2,397,414 pairs; identical schema/IDs), minus the
  valuable **human-judged 4,133-pair test split** — pull that from
  `ai4bharat/Aksharantar` (config `nep`) directly. License CC0 (mined) / CC-BY
  (manual); the mirror's "MIT" tag is not authoritative. **Attribute AI4Bharat.**
- **It is ONE machine scheme, deduplicated** — one romanization per word, no
  nam/naam or cha/chha/xa variation, ~11–20% noise (glued tokens, loanword
  back-spellings), and common words like नाम, नेपाल, पानी are *absent*. So: filter
  noise, use it for lexicon/rules coverage, and rely on the **normalization layer**
  (§2 layer 3) to absorb typing variation it cannot teach.
- **Frequency priors**: the archive corpus itself (~303k tokens; register-matched to
  what users will search) + FineWeb-2 Nepali unigrams / Leipzig lists for modern
  vocabulary. Note the register split the linguistics review quantified: the archive
  is chandrabindu-heavy (ँ:ं ≈ 3:1) and छ>च — the *opposite* of modern text — so
  ship blended priors, and offer both nasal forms in top-5.
- **Bigram LM for layer 5**: derive from the archive corpus + a modern Nepali corpus
  (OSCAR/CC-100 or FineWeb-2).
- **nirajandhakal/Devnagari-Romanized-Pair**: machine-translated, inconsistent,
  partly corrupted (Devanagari leaking into the romanized column). Smoke-test
  sample at most.
- **Names**: Diwas524 / SushilShrestha GitHub name lists for the named-entity
  lexicon (the hardest category per Aksharantar's own numbers).

## 6. Reuse & license rules (from engines review)

Build only from **MPL / MIT / BSD / CC0 / CC-BY / Apache** sources:

| Reuse | What | License |
|---|---|---|
| `OpenBangla/riti` | The reference pipeline to port (rules→dict→autocorrect→suffix→learning) | MPL-2.0 |
| rupantor / `jsAvroPhonetic` | JSON-grammar rule format (find/replace + prefix/suffix/scope) | MPL |
| `teamtachyon/quillpad-server` | **Nepali rule file** `Nepali_Xlit.xml` + 1.1 MB trained Nepali model | BSD-3 |
| `ai4bharat/Aksharantar` (nep) | 2.4M pairs + human-judged test split | CC0/CC-BY |
| `@ai4bharat/indic-transliterate` | React candidate-dropdown UI shell (design reference; we're not React) | MIT |
| `@siyabasa/singlish` | Browser TS trie + state machine for a Brahmic script | Apache-2.0 |
| `indic-transliteration/sanscript.js` | Scheme maps for the strict base layer | MIT |
| `pipeline/devanagari_slug.py` | Our own collapse function — keys the lexicon | ours |
| RIME octagram / Google WFST papers | Short-context re-rank *design* (concepts, not code) | — |

**Avoid linking**: GoVarnam and indic-trans are **AGPL-3.0** (network copyleft) —
copy algorithms, never code. (GoVarnam's LICENSE.txt is AGPL despite GitHub showing
NOASSERTION; the older `libvarnam` is MPL-2.0 if we want its code.)

## 7. What we will NOT do (evidence-backed non-goals)

- No sentence translation; word-level conversion + short-context re-rank only (brief).
- No server, no API dependency, no telemetry. Everything static + local.
- No neural model in the base path; deferred until the symbolic stack's measured
  OOV gap justifies it.
- No rules-only product (fails tech-illiterate users), no mandatory escape syntax.
- No AGPL code, no Google-API dependence in core.
- No global site JS: the tool loads on its own page(s) only; reader pages stay JS-free.

## 8. Open questions (to resolve while refining this document)

1. **Rule-layer format**: adopt rupantor's JSON grammar vs. Quillpad's regex-producer
   XML vs. our own table derived from reviews/05 §3? (Leaning: rupantor-style JSON,
   seeded from the 05 §3 ambiguity table + Quillpad's Nepali file as a cross-check.)
2. **Lexicon size/shape for POC**: top-N by blended frequency — N=10k? 50k? Ship as
   plain JSON first, measure, then compress.
3. **Register blend**: weighting between archive-corpus priors and modern-web priors
   for ranking (affects छ/च, ँ/ं defaults). Possibly a per-surface choice (search box
   → archive priors; free typing → modern priors).
4. **Where the POC lives**: standalone `/type/` page vs. wired into the Pagefind
   search box. (Recommendation from the initial analysis: search box is the killer
   integration for the archive's mission; a standalone page is the simpler POC.)
5. **`x` default**: छ (chat convention) vs क्ष (typing-tool convention) — corpus says छ.

## 9. Draft research plan (POC-first, per project rules)

**Stage 0 — Rules document.** Freeze scope from §7, the UX contract from §3, and the
do/don't list. (The brief's "make rules for the project" step.)

**Stage 1 — Data build (offline, Python, in this repo's pipeline style).**
Download Aksharantar-nep → filter noise (glued tokens, loanword back-spellings) →
build the Devanagari vocabulary + blended frequency table (archive corpus +
FineWeb-2/Leipzig) → generate normalization keys via `normalize(romanize(w))`
reusing `devanagari_slug.py` → emit `lexicon.json` shards + a word-bigram table.
Deliverable: reproducible `build_lexicon.py`.

**Stage 2 — POC engine (pure JS, no framework).**
Layer 1+2 rule engine (rupantor-style JSON grammar, seeded from the ambiguity table)
+ layer 3 lexicon lookup + frequency ranking + top-5. Desktop-first HTML test page
with the §3 interaction contract (space commits, backspace reopens, literal escape,
copy button). *Success = the path exists: typing "mero naam ho" and a paragraph of
real Nepali feels right to a native speaker.*

**Stage 3 — Measure (only now do targets get set).**
Run the POC against Aksharantar's 4,133 human-judged test pairs (top-1/top-5, CER)
and eyeball-test natural typing. Build the small multi-reference natural-typing set
(~500 frequent words × 2–3 typists; MRR headline) — the datasets review's protocol.
Set the v1 accuracy/latency/size targets from what the POC actually measures.

**Stage 4 — v1 hardening.** Mobile input plumbing (§4), context bigram re-rank
(layer 5), user-selection memory (layer 6), asset compression (packed trie if JSON
is too big), lazy loading, then integration placement (search box and/or /type/
page) via the `verify-site-change` skill.

*(Stages 3–4 detail deliberately thin until the POC proves the path — per the
project's "first make sure there is a path" rule.)*
