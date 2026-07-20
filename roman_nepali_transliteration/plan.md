# Roman Nepali → Devanagari: Project Plan

**Status (2026-07-20):** plan approved · Stage 0 done (`rules.md`) · Stage 1 done
(`pipeline/`, artifacts in `build/`: core 0.09 MB gz / full 1.11 MB gz / bigram
0.73 MB gz — all within budget; agreement filter dropped 8.2% of Aksharantar as
noise) · Stage 2 built (`poc/`), engine tests green (normalize parity with Python,
17 top-1 + 5 top-5 expectations, OOV floor, 0.06 ms/lookup), browser verification
in progress — user "path exists" judgment pending.
User refinements applied 2026-07-20 (rules.md §UX 9–10): English words pass
through by default with a toggle (english.json = google-10000 minus Nepali-core
collisions, 34 KB gz); output textarea is editable with insert-at-selection
commits (select wrong word → retype roman → replaced); optional uppercase
retroflex hints T/Th/D/Dh/N/S (bheTaula → भेटौला); rule layer prefers digraphs
and the ा reading of word-final 'a'. All headless-verified. Known Stage-3/4
item: OOV inflections of lexicon stems (भेट → भेटौला) want a suffix-join layer.
Stage 4 (partial, 2026-07-20): PRODUCTIZED — `/type/` page live in the site build
(nav: टाइप; indexed; canon type/; sitemap). Sources moved to tracked `assets/type/`
(lexicons vendored, pdfjs precedent; `build_lexicon.py --install` refreshes them);
page written by `build_site.write_type_page` with site chrome/theme; mobile-robust
commits via input events (space lands in buffer even when Android keydown is 229);
punctuation tails map through literals (`.`→।); attribution footer per rules.md.
Headless-verified light/dark/mobile. poc/ is now just the node test harness.
Shipped 2026-07-20 (commits 4d3e69b/192a4dd/ecba068, live on
www.nepaliarchives.org/type/). Post-ship fixes: digit/danda-only input converts
(२०८१/।; esc keeps literal), 1–5 pick candidates only when the buffer has
letters, and keyboard mode (body.kbd via visualViewport) keeps output +
candidates + input visible while the phone keyboard is open (fits 330px).
Still open in Stage 4: bigram re-rank wiring, real-device mobile testing,
IndexedDB caching, selection learning (localStorage), suffix-join.

*Draft for refinement — 2026-07-20. Grounded in [`literature_review.md`](./literature_review.md)
(evidence citations live there and in [`reviews/`](./reviews/)). Decisions marked
**⟨DECIDE⟩** need your call; each carries my recommendation so you can approve or
override in one pass.*

## Goal

Type romanized Nepali anywhere on www.nepaliarchives.org and get correct Devanagari:
`mero naam ho` → `मेरो नाम हो`. Word-at-a-time conversion with top-5 candidates and
short-context re-ranking. Free, offline-capable, static-site-only, tiny, and usable
by tech-illiterate users on cheap phones.

## Principles (fixed — from initial.md + review evidence)

1. **Usability over everything.** Copy, correction, candidate selection are designed
   first, not last. The user never sees an error state.
2. **Performance over accuracy.** Accuracy can never be perfect; speed and graceful
   behavior can. Top-5 + one-key correction is the accuracy strategy.
3. **POC before targets.** No metric-setting until a working path exists (Stage 3).
4. **Static site stays static; reader pages stay JS-free.** The tool loads only on
   its own surface. Nothing degrades when the model/lexicon isn't loaded.
5. **Clean licenses only** (MPL/MIT/BSD/Apache/CC0/CC-BY). No AGPL code, no
   Google-API dependency in core, no telemetry.

## Non-goals (v1)

- Full-sentence translation or grammar correction.
- Neural model in the base path (deferred until Stage 3 measures the OOV gap).
- A system-wide IME / mobile app. We complement Gboard, not compete with it.
- Spellchecking Devanagari the user pastes in.

---

## Stage 0 — Rules document (freeze scope)

**Work:** Write `rules.md`: the do/don't list (§Principles + §Non-goals above,
expanded), the UX contract (from review 02: space commits #1, backspace reopens,
literal-Latin escape, never fail closed, copy-first layout, candidates above input
on mobile, ≥48dp targets), and the engineering constraints (review 03: `input`/
`beforeinput` + composition events, no `contenteditable`, no keyCode, auto-* off).

**⟨DECIDE 0.1⟩ POC surface.** Recommendation: a **standalone `/type/` page** for the
POC (simplest, isolated), with the **search-box integration as the first v1
placement** (it's the mission-critical use: users without Nepali keyboards currently
cannot search the archive at all). Alternative: search box first.

**Deliverable:** `rules.md`. **Exit:** you sign off on it.

## Stage 1 — Data build (offline Python, repo-pipeline style)

**Work — `build_lexicon.py` (+ helpers), reproducible end to end:**

1. **Fetch** `ai4bharat/Aksharantar` config `nep` (train+val+**test** — the upstream,
   not the re-hosted mirror; test = the 4,133 human-judged pairs we hold out).
2. **Filter noise** (review 04): drop glued compounds (native side matches two
   dictionary words concatenated / length outliers), drop English back-spellings
   (Latin-side English-dictionary hits with non-Nepali phonotactics), dedupe.
3. **Frequency table:** blend (a) archive corpus counts (~303k tokens — register-
   matched to search) and (b) FineWeb-2 Nepali unigrams / Leipzig lists (modern
   register). Keep both columns; blend at query time so the surface can choose.
4. **Fill the gap:** Aksharantar lacks common words (नाम, नेपाल, पानी absent). Union
   its vocabulary with the archive corpus vocabulary + the top of the modern
   frequency list, generating romanizations for the missing words via
   `devanagari_slug.romanize()`.
5. **Normalization keys:** implement `normalize()` (review 05 §4 pseudocode — one
   notch coarser than `romanize()`: fold ch/chh/x, w/v→b, doubled letters, vowel
   length, final schwa). Key every word by `normalize(romanize(word))`. Property
   test: `normalize(variant)` hits the same key for hand-listed variant sets
   (nam/naam, cha/chha/xa, sabda/shabda, gyan/jnan…).
6. **Rule table:** author `rules.json` (rupantor-style JSON grammar) seeded from the
   ambiguity-class table (review 05 §3), cross-checked against Quillpad's BSD
   `Nepali_Xlit.xml`. Corpus-prior candidate ordering baked in (त before ट, स before
   श/ष, ब/व both, both nasals offered).
7. **Bigram table:** word-bigram counts with backoff from archive corpus + one modern
   corpus, pruned + 8-bit log-probs. (Built now because it's cheap here; *wired in*
   only at Stage 4.)
8. **Emit:** `lexicon-core.json` (top-N starter shard), `lexicon-full.json` (or
   sharded), `bigram.json`, `rules.json` — all gzip-measured, sizes recorded.

**⟨DECIDE 1.1⟩ Lexicon size.** Recommendation: **core shard = top 5k words
(~≤120 KB gz), full = top 50k (measure; target ≤1.5 MB gz)**. Adjust after measuring.

**⟨DECIDE 1.2⟩ Where data lives.** Recommendation: code in
`roman_nepali_transliteration/pipeline/`, generated artifacts in
`roman_nepali_transliteration/build/` (**gitignored**, like the site build), raw
downloads in a gitignored `data/`. Only code + hand-authored files are tracked —
keeps the source-only repo rule.

**Deliverables:** `build_lexicon.py`, `rules.json`, measured artifact sizes.
**Exit:** lexicon builds reproducibly; normalization property tests pass; spot-check
of 100 random entries by eye looks sane.

## Stage 2 — POC engine (pure JS, no framework, desktop-first)

**Work:**

1. **Engine (`engine.js`, plain ES module):**
   - Layer 1+2: greedy longest-match tokenizer over `rules.json` → deterministic
     Devanagari + ambiguity fan-out (candidate generation).
   - Layer 3: `normalize(input)` → lexicon bucket → rank by rule-cost +
     (−log freq) → **top-5**.
   - Layer 4: literal pass-through for detected English/unknown tokens (raw Latin
     kept as a pinned candidate, Yamli-style).
   - OOV floor: rules-only output always present — never fail closed.
   - Synchronous, in-memory, per-keystroke; no network after assets load.
2. **Test page (`poc/index.html`):** textarea + candidate strip implementing the
   UX contract: type → underlined active word + top-5 above/below → **space/enter
   commits #1**, 1–5/click picks, **backspace reopens** last word, Esc keeps Latin,
   prominent copy button with "कपी भयो" toast. Core shard inline; full lexicon
   fetched in background (works before it arrives — proves the lazy-load design).
3. **Dogfood harness:** a page that replays sample romanized sentences (typed by us,
   both `naam`- and `nam`-style) and shows conversions side by side, so refining
   rules has a fast feedback loop.

**Explicitly deferred to Stage 4:** mobile virtual-keyboard plumbing, bigram
re-ranking, user-selection memory, packed-trie compression, WASM anything.

**Deliverables:** `poc/` runnable locally (plain `python3 -m http.server`).
**Exit (the "path exists" test):** typing `mero naam ho`, `k xa khabar`, `ma
nepali sikdai chhu`, plus ~20 archive-relevant queries (author names, poem titles:
`muna madan`, `laxmi prasad devkota`, `pagal`) produces the intended Devanagari in
top-1 for most and top-5 for nearly all — judged by you.

## Stage 3 — Measure, then set targets

**Work:**
1. **Canonical eval:** POC vs the held-out Aksharantar-nep test (4,133 human-judged
   pairs): top-1/top-5 accuracy, CER. Script: `evaluate.py` (becomes the
   regression gate).
2. **Natural-typing eval (the one that matters):** build the multi-reference set —
   ~500 high-frequency words, 2–3 native typists each writing the romanization they'd
   naturally use (Google Form); gold = union set. Metrics: multi-reference ACC,
   **MRR (headline)**, top-5 coverage. (First Nepali natural-typing benchmark —
   worth publishing with the archive.)
3. **Search-intent eval:** ~100 real archive queries (titles, authors, first lines)
   romanized by the same typists — measures the mission use-case directly.
4. **Error analysis** → decide: which failures are rule fixes, which are lexicon
   gaps, which are genuinely ambiguous (top-5's job), and **whether an OOV gap
   remains that would justify the deferred tiny neural fallback**.
5. **Now set v1 targets** (numbers TBD from what the POC measures — e.g. "top-1 ≥ X%
   / top-5 ≥ Y% natural-typing, keystroke→candidates < 10 ms on a low-end phone,
   core payload ≤ Z KB").

**Deliverables:** `evaluate.py`, eval sets, a short results memo, agreed v1 targets.
**Exit:** targets agreed; go/no-go on neural fallback decided by data.

## Stage 4 — v1 hardening & integration

Ordered by risk (mobile first — it's the known hard part):

1. **Mobile input plumbing:** controlled input + external candidate overlay via
   `visualViewport`; `input`/`beforeinput` + composition events; all auto-* off;
   test matrix = Gboard + iOS Safari + a low-end Android Chrome.
2. **Context re-rank (layer 5):** wire the bigram table; verify on the Stage-3
   context set that it lifts top-1 without hurting latency. *(The genuinely novel
   layer — no Indic engine has it.)*
3. **User-selection memory (layer 6):** localStorage LRU boosting committed picks.
4. **Payload engineering:** only if Stage-1 JSON sizes exceed budget — packed
   DAWG/succinct trie, IndexedDB caching + `navigator.storage.persist()`.
5. **Integration:** the ⟨DECIDE 0.1⟩ placement(s) — `/type/` page styled like the
   site, and romanized input in the search box (convert → feed Pagefind). Build via
   `build_site.py` conventions; verify with the `verify-site-change` skill; ship
   with the `ship` skill.
6. **Docs:** attribution page (AI4Bharat/Aksharantar CC-BY credit, riti/Quillpad
   design credits), a short "how to type" help section in Nepali + English.

**Exit:** v1 targets met on the eval sets; works on the phone test matrix; deployed.

## Later / research backlog (post-v1)

- Tiny distilled char seq2seq (ONNX WASM) if Stage 3 shows an OOV gap worth 4–6 MB.
- Suffix/morphology layer (riti-style) for agglutinated forms (-हरूको, -लाई…).
- Publish the natural-typing benchmark + a write-up (the context re-ranking layer
  is publishable — no Indic engine has one).
- Optional online enhancer (Google JSONP) — only if ever needed, never core.

## Risks

| Risk | Mitigation |
|---|---|
| Mobile virtual keyboards break the input model (the known killer) | Stage 4 does mobile *first*; design already avoids keyCode/contenteditable; fallback UX = convert-on-space textarea (easynepalityping model) which works everywhere |
| Aksharantar noise poisons the lexicon | Stage 1 filters + spot-check gate; frequency blending drowns rare junk |
| Normalization collapses too much (wrong words in top-5) | Rule-cost term + exact-surface bonus in ranking; property tests; Stage 3 error analysis |
| Payload creep | Sizes measured at Stage 1 and budgeted before any integration |
| Register mismatch (archive vs modern priors) | Both frequency columns kept; per-surface blend (⟨DECIDE⟩ deferred to Stage 3 data) |

## Decision summary — RESOLVED 2026-07-20 (plan approved)

| # | Question | Decision |
|---|---|---|
| 0.1 | POC surface | **Standalone** (a self-contained page). Site integration deferred — "we will integrate later." |
| 1.1 | Lexicon size | Core 5k / full 50k, adjust after measuring |
| 1.2 | Data layout | Code tracked; downloads + built artifacts gitignored |
