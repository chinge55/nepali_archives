# Review 4: Datasets & evaluation (agent review, 2026-07-20)

## Dataset inventory

| Dataset | Size | Granularity | License | Quality verdict | Role for us |
|---|---|---|---|---|---|
| **Saugatkafley/Nepali-Roman-Transliteration** | 2,397,414 train + ~2.8k val | word-level pairs | Labeled **MIT** (unreliable — see below); true basis **CC-BY / CC0** | Single systematic **machine-generated** scheme, deduped 1 romanization/word; ~11–20% noise (glued tokens, loanword back-spellings) | **Train** (tiny neural fallback) + **Lexicon** (with a normalization layer). NOT eval as-is |
| **AI4Bharat/Aksharantar (nep)** — the true upstream | 2,397K train / 3k val / **4,133 test** | word-level pairs | **CC-BY** (manual) + **CC0** (mined); both archive-safe | Train = same noisy mined data; **test split is human-judged** and clean | **Eval** (use the 4,133 test split) + same train as above |
| **nirajandhakal/Devnagari-Romanized-Pair** | 959 | **sentence** triples (En / Deva / Roman) | **Apache-2.0** | Machine-translated translationese; romanized col inconsistent **and corrupted** (Devanagari leaks into it) | **Tiny dev/smoke sample** only — not a benchmark |
| **Dakshina** (Google) | 25k train / 2.5k dev / 2.5k test types per lang | word lexicon w/ **multiple attested romanizations + counts** + full sentences | **CC BY-SA 4.0** | Gold-standard multi-reference format, native-speaker collected | **Methodology template only — NO Nepali** |
| **IndoNLP-2025 shared-task sets** | 5 langs | word + sentence | task-specific | Splits "general" vs "ad-hoc" typing; strong protocol | **Methodology only — NO Nepali** |
| **FineWeb-2 Nepali unigrams (thenepaliguy, Kaggle)** | 200k+ unique words + freq | word freq list | ODC-By (FineWeb-2 derived) | Clean frequency counts | **Frequency prior** for ranking + choosing shipped-lexicon vocab |
| **Leipzig Corpora — Nepali** | 10k–1M sentence packages + freq wordlists | word freq | CC-BY | Newspaper/web freq lists | **Frequency prior** (alt/supplement) |
| **OSCAR / CC-100 Nepali** | 3.8 GB / multi-GB | raw text | research-use / CC0-ish | Common-Crawl corpora | Corpus to derive freq / mine natural romanized text |
| **Diwas524/Nepali-to-Roman-Transliteration**; SushilShrestha/NepaliTransliteralDataset (GitHub) | names/words | word/name pairs | check per-repo (permissive) | Nepali **names/surnames/places** | **Named-entity lexicon** (hardest category per Aksharantar) |
| **WikiPron (nep)** | small (hundreds–low-thousands) | word→**IPA** | Apache-2.0/CC | IPA not romanization; thin coverage | Minor — phonetic rule tuning only |
| **NepEMO / code-mixed Nepali sentiment corpora** | thousands of posts | sentence (Reddit/Twitter) | per-paper | **Real ad-hoc romanized typing** | **Source for a natural-typing eval set** |

## Detailed audit findings

### 1. Saugatkafley/Nepali-Roman-Transliteration — it IS Aksharantar-nep, one machine scheme, not natural variation

**Provenance (resolved).** The README is empty, but the fingerprint is conclusive: 2,397,414 train rows + ~2.8k val, columns `unique_identifier` / `native word` / `english word`, IDs `nep1…nepN`. AI4Bharat **Aksharantar's Nepali subset is train 2,397K / val 3k / test 4,133** with the identical schema and `nep`-prefixed IDs. This upload is **Aksharantar-nep (train+val), re-hosted** — it drops the valuable human-judged 4,133-word test split.

**Critical question — one scheme or natural typing variation? → ONE systematic machine scheme.** The dataset is **deduplicated by Devanagari word** — each appears exactly once with a single romanization. Verified via the datasets-server `/filter` endpoint:

```
गर्छ   → garchha   (count = 1)
हुन्छ  → hunchha   (count = 1)
राम्रो → ramro     (count = 1)
मान्छे → manchhe   (count = 1)
गरेको  → gareko    (count = 1)
सम्झना → samjhana  (count = 1)
```

There is **no `nam`/`naam`, no `cha`/`chha`/`xa`** — the alternation the feature must handle **does not exist in this data**. It encodes a single canonical (model-produced) form per word. Scheme regularities observed: छ→`chha`, श/ष→`sh`, word-final schwa dropped naturally (`gareko`, `ramro`), व positional (**word-initial → v**: विरोध→`virodh`; **medial → w**: भवानी→`bhawani`, प्रवृत्ति→`prawritti`) — but long-vowel doubling is **inconsistent** (हराउँछ→`haraaunchha` with `raa`, yet नारीका→`narika` with `na`), the signature of neural output rather than a rule engine.

**Noise (matches Aksharantar's stated 80–89% mining accuracy, i.e. 11–20% bad pairs):**
- **Glued compound tokens** from imperfect corpus tokenization: `आफूनोबेल→afunobel`, `नगरपालिकाकासञ्जु→nagarpalikakasanju`, `पहिलेशान्ति→pahileshanti`, `उत्तरउत्तर→uttaruttar`.
- **English loanword back-spellings**: `एड्मिनिस्ट्रेशनको→administrationko`, `डाइग्नोटिक→diagnotic`, `जिम्बावेक→zimbawek`.
- **Coverage is skewed, not a clean frequency lexicon:** extremely common words are absent as standalone entries — `नाम`, `नेपाल`, `पानी`, `भयो`, `माया`, `कम्प्युटर`, `स्कुल` all returned **count = 0**. Vocabulary is dominated by long/inflected/compound forms from the mined news corpus.

**License:** the "MIT" tag is the re-uploader's own and not authoritative. The real basis is Aksharantar's: mined data **CC0**, manual data **CC-BY**. Either way **permissive and archive-compatible** — attribute **AI4Bharat / Aksharantar**, don't rely on the "MIT" label.

**Role:** excellent as (a) **training data** for the tiny fallback model and (b) a **Devanagari↔canonical-roman lexicon** — but because it is single-reference, it must sit behind a **normalization layer** (fold `aa→a`, `ee→i`, `oo→u`, `w/v/b→` one key, `chh/x→ch`, drop doubled letters) so a user's `naam`/`nam` both hit the `नाम` key. Strip glued-token and loanword rows before shipping. **Do not use it for evaluation as-is.**

### 2. nirajandhakal/Devnagari-Romanized-Pair — weak, partly corrupted

959 rows, columns `English` / `Nepali Translation` / `Nepali Romanized`. **Sentence-level, English-origin machine translation** (travel phrases + a chunk of a cancer-biology book), not native Nepali. The romanized column is natural-ish but **inconsistent and defective**:

- Reasonable rows: `म बजारमा केही तरकारी र फलफूल किन्न जाँदैछु।` → `Ma bajaarma kehi tarkari ra phalaphul kinna jaandai chhu.`
- Inconsistency: गर्दछ as both `gardachha` and `parcha`/`parchha`; व as `w` and `v`; `antarish` for अन्तरिक्ष — wrong.
- **Actual corruption — raw Devanagari leaks into the "romanized" column:** `...nihit ch चुनौती haru ra kathinaiharu...`.
- Loanwords kept in English (`airport`, `hotel`, `ATP synthase`), random Title-case.

**License** Apache-2.0 (clean). **Role:** at most a **tiny qualitative smoke/dev sample** for the sentence-context re-ranking stage. Not a benchmark.

### 3. Aksharantar (upstream) & Dakshina — the reference points

- **Aksharantar** (Findings-EMNLP 2023): 26M pairs / 21 langs; **AksharantarBench test = 103,005 pairs / 19 langs, Nepali included (4,133)**. Nepali training is **mined** (CC0), so the 2.4M is noisy by construction; the **4,133 test is human-judged** — that is the clean word-level eval, and it is missing from the Saugatkafley mirror. Get it from `ai4bharat/Aksharantar` (config `nep`, split `test`).
- **Dakshina** (Google, LREC 2020): **CC BY-SA 4.0**, 12 langs, **Nepali NOT included**. Its romanization lexicon is the format to copy: TSV of `(native_word, romanization, attestation_count)` with **multiple attested romanizations per word from native speakers** (25k/2.5k/2.5k word types). **Methodological blueprint** for a Nepali multi-reference test set, not data.

## Evaluation methodology & recommended protocol

**How the field measures transliteration quality.**

- **NEWS shared task (the multi-reference standard):** **ACC** = top-1 word accuracy (a hit if the #1 candidate matches **any** reference in the gold set), **Mean F-score** (LCS-based, partial credit), **MRR** = mean reciprocal rank of the first correct candidate (ideal for a top-k UI), **MAP_ref**. Gold is a **set** of valid romanizations per word.
- **Aksharantar / IndicXlit:** primary = **top-1 word accuracy**; secondary = **top-3 / top-5 + F1** (single reference).
- **Dakshina:** **CER** for word transliteration; WER/CER for sentences.
- **IndoNLP-2025:** **WER, CER, BLEU**, and crucially splits evaluation into **"general typing" vs "ad-hoc typing"** — systems scoring WER 0.074 on general collapsed to 0.227 (CER up to 0.67) on ad-hoc. This quantifies the exact gap our feature lives in: a single-scheme model looks great on canonical data and fails on real typing.

**Recommended protocol for us** (word-level, top-5, short-context re-ranking, static site):

1. **Canonical intrinsic eval — free, immediate.** Score against **Aksharantar-nep test (4,133)**. Report **top-1 and top-5 exact-match accuracy** + **CER of the top-1**. Regression gate for the lexicon/model; only tests the canonical scheme.
2. **Natural-typing eval — the metric that actually matters.** Build a small **Dakshina-style multi-reference set** cheaply: sample **300–1,000 high-frequency Nepali words** (FineWeb-2 unigram list), have **2–3 native typists** each type the romanization they'd naturally use (Google Form), store the **union as a reference set with counts** (`नाम → {nam, naam}`, `छ → {cha, chha, xa}`). ~1–2 hours of annotation. Alternatively/additionally, mine **real ad-hoc romanized words from social-media corpora** (NepEMO Reddit, code-mixed sets) and hand-align a sample. Score with **NEWS-style multi-reference metrics: ACC, MRR (the headline number for a top-5 dropdown), Mean F-score, CER**.
3. **Context re-ranking eval.** A ~100-item set of short romanized phrases with an ambiguous target word; measure whether short-context re-ranking moves the correct candidate into top-1/top-5 vs the context-free baseline.
4. **Report the general-vs-ad-hoc split** (à la IndoNLP): publish both the canonical number and the natural-typing number so the real-world gap is visible and tracked.

**Multiple-reference rule of thumb:** treat gold as a set; top-1 hit = best candidate in the set; MRR credits `1/rank` of the first in-set candidate. The only fair way to score a task where `nam` and `naam` are both correct.

## The 3 most load-bearing findings

1. **Saugatkafley/Nepali-Roman-Transliteration is Aksharantar-nep (train+val) re-hosted, and it is ONE deduplicated machine scheme — one romanization per word, no `nam`/`naam` or `cha`/`chha`/`xa` variation.** Strong training/lexicon material but **cannot teach or evaluate natural typing variation**. Add a normalization layer for lookup; do **not** treat it as a natural-typing benchmark. Its "MIT" label is unreliable; the real basis is Aksharantar's CC-BY/CC0 (archive-safe — attribute AI4Bharat).

2. **No Nepali natural-typing benchmark exists** (Dakshina and IndoNLP-2025 exclude Nepali; Aksharantar-nep test is single-reference canonical). The highest-leverage next step is to **build a small Dakshina-style multi-reference Nepali test set** (~500 frequent words, 2–3 typists) — a few hours of work that unlocks the only evaluation that reflects the product's real job.

3. **Evaluate with multi-reference top-k metrics, not single-answer accuracy.** **Top-1/top-5 accuracy + MRR + CER against reference sets** (NEWS convention); MRR is the natural headline for a top-5 candidate UI. Report the canonical (Aksharantar) number and the natural-typing number **separately** — the literature (IndoNLP) shows the gap between them is where usability is won or lost.

**Sources:** Saugatkafley/Nepali-Roman-Transliteration (HF) · nirajandhakal/Devnagari-Romanized-Pair (HF) · ai4bharat/Aksharantar (HF) · Aksharantar paper (Findings-EMNLP 2023) · Dakshina dataset + paper (LREC 2020) · IndoNLP 2025 shared task (arXiv:2501.05816) · FineWeb-2 · pemagrg1/Nepali-Datasets catalog · Diwas524/Nepali-to-Roman-Transliteration · NEWS shared task reports · Leipzig Corpora Collection.
