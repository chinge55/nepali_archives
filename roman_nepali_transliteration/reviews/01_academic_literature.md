# Review 1: Academic literature — Roman→Indic back-transliteration (agent review, 2026-07-20)

Scope note: "back-transliteration" here = Latin/Roman script → native Brahmic (Devanagari) script. Accuracy figures are as reported by the authors; transliteration is usually scored as **word-level top-1 accuracy** or **CER/WER** (lower is better).

## 1. AI4Bharat — Aksharantar dataset + IndicXlit model

**Madhani et al. (2023). "Aksharantar: Open Indic-language Transliteration datasets and models for the Next Billion Users." Findings of EMNLP 2023.** https://aclanthology.org/2023.findings-emnlp.4/ · arXiv:2205.03018 · https://github.com/AI4Bharat/IndicXlit
- Largest open Indic transliteration resource: **26M Roman↔native pairs, 21 languages, 12 scripts**, mined from corpora + ~554k manually annotated pairs. **Nepali IS covered** (native words sourced from the LDC-IL corpus). **IndicXlit** is a **transformer, character-level, one-to-many multilingual** encoder-decoder (target-language tag token), **~11M parameters**. Decoding = beam search (beam=4) then **re-ranking the top-4 with `F = 0.9·T + 0.1·P`** where T = char-level transliteration log-prob, P = **word-level unigram LM** score; re-ranking adds **+12% average accuracy**. Beats Dakshina baselines by +15% avg. Nepali top-1 ≈ **80%** on common words, **~49%** on foreign named entities. **Licenses: code+models MIT; benchmark+manual data CC-BY; mined data CC0.**
- *Relevance:* The single most usable asset — permissively-licensed, Nepali-covering model and dataset — but 11M params is heavy for phones; treat as the lazy-loaded/quantized "upgrade" engine or a teacher to distill from, not the always-on base.

**IndicXlit product page / dataset card.** https://indicnlp.ai4bharat.org/indic-xlit/ · https://huggingface.co/datasets/ai4bharat/Aksharantar
- Confirms deployment as a web transliteration tool; the exact UX we want already runs from this model.

## 2. Google — Dakshina dataset (methodology; no Nepali)

**Roark et al. (2020). "Processing South Asian Languages Written in the Latin Script: the Dakshina Dataset." LREC 2020.** https://aclanthology.org/2020.lrec-1.294/ · https://github.com/google-research-datasets/dakshina (CC)
- Latin+native text for **12 languages (bn, gu, hi, kn, ml, mr, pa, sd, si, ta, te, ur) — Nepali NOT included.** Three components: native-script Wikipedia, a romanization lexicon (attested human romanizations capturing spelling variation), human-romanized parallel sentences. Three single-word baselines: **pair 6-gram (Witten-Bell, compiled to a WFST)**, **LSTM seq2seq**, **char transformer** (dim 128, 4L/4H). Crucially, **all three land within ~2% absolute CER of each other**; the pair-6g wins on the sparsest-data language. CER ~6–20%, WER ~32–67%.
- *Relevance:* The load-bearing empirical result — a symbolic 6-gram pair model is essentially as accurate as a tiny neural model for word-level transliteration, at a fraction of the size/latency.

**Same paper, full-sentence section (context re-ranking evidence).**
- **"Noisy channel" = pair-6g word transliterator + Katz-smoothed trigram LM over native-script Wikipedia** (k-best per word, LM rescoring) vs. full seq2seq transformers. **Adding sentence context roughly halved error** (Hindi WER 24.6 → 11.0), and **the noisy-channel model beat the seq2seq transformers on 9 of 12 languages.**
- *Relevance:* Directly validates our "next-word + short-context re-ranking" design: small word transliterator + small n-gram LM outperforms end-to-end neural. This is the architecture to copy.

**Demirşahin et al. (2022). "Criteria for Useful Automatic Romanization in South Asian Languages." LREC 2022.** https://aclanthology.org/2022.lrec-1.718.pdf
- Methodology for what makes romanization/transliteration useful and how to evaluate it (reversibility, coverage, consistency). Useful for defining our accept/reject and evaluation criteria.

## 3. On-device WFST transliteration (the production precedent)

**Hellsten et al. (2017). "Transliterated Mobile Keyboard Input via Weighted Finite-State Transducers." FSMNLP 2017.** https://aclanthology.org/W17-4002/
- Google Gboard's WFST keyboard decoder extended to transliteration: an n-gram **pair language model** and lexicon compiled/composed as weighted FSTs (OpenGrm/OpenFst), combined with a native-script keyboard LM, with **literal pass-through for OOV** (if the best decoded word scores below a margin, emit the raw typed Latin string). On-device budget stated explicitly: **latency ≤ 20 ms, models ~10 MB aggregate.** **Launched for 22 languages in Gboard (2017).**
- *Relevance:* Proof that our exact use-case (per-keystroke Roman→Devanagari, smartphone, tiny/fast, graceful OOV fallback) is solved by a symbolic WFST + n-gram LM stack at our budget. "Literal pass-through" is a ready-made design for "works without the model."

## 4. Non-neural foundations: joint source-channel & pair n-gram

**Li, Zhang, Su (2004). "A Joint Source-Channel Model for Machine Transliteration." ACL 2004.** https://aclanthology.org/P04-1021/
- Introduces **direct orthographical mapping** via a **joint source-channel n-gram model** (jointly modeling aligned source+target orthographic units), no intermediate phoneme layer. The canonical pair-LM formulation.
- *Relevance:* Theoretical basis for the pair-n-gram engine Dakshina and Hellsten both use — a few-KB-to-MB symbolic model trainable from Aksharantar's Nepali pairs.

**NEWS shared tasks on machine transliteration (2009–2018).** e.g. https://www.microsoft.com/en-us/research/publication/report-of-news-2011-machine-transliteration-shared-task/
- Multi-year benchmark (English↔many, incl. Hindi). Dominant pre-neural approaches: **joint source-channel n-gram; DirecTL+ (discriminative many-to-many alignment); phrase-based SMT with chars-as-words**; winners frequently used **system combination and candidate re-ranking**. Neural entries rise from ~2015. Top-k candidate lists + re-ranking were standard.
- *Relevance:* (a) n-gram + discriminative models were competitive/winning for years; (b) **re-ranking a candidate list is the established way to squeeze accuracy** — matches our top-5 + re-rank design.

## 5. Small / character-level neural & quantization for on-device

- **Dakshina LSTM & transformer baselines** (§2) — concrete tiny-seq2seq configs (biLSTM 256 + 3-layer LSTM 128 w/ Luong attention; char transformer dim 128, 4L/4H), but no more accurate than the symbolic pair-6g for single words.
- **Ge et al. (2022). "EdgeFormer: A Parameter-Efficient Transformer for On-Device Seq2Seq Generation." EMNLP 2022.** arXiv:2202.07959 — int8 + reduced vocab + factorized embeddings meets on-device budgets. The size/technique template if we ever want on-device neural.
- **"Extremely Low Bit Transformer Quantization for On-Device NMT." Findings of EMNLP 2020.** arXiv:2009.07453 — mixed-precision under 3 bits: **11.8× smaller, 8.3× less memory, 3.5× faster on mobile**, minimal quality loss. Quantifies how far IndicXlit's 11M could shrink.
- **Char-level transformer transliteration (Tajik-Persian, 2026).** arXiv:2605.09092 — ~98.8% char accuracy on CPU. Character-level (not subword) is the right granularity; feasible on mobile CPU.

## 6. Context-aware re-ranking: the cost/benefit ladder

- **IndicXlit unigram re-ranking** (§1): +12% accuracy from a pure word-frequency prior (no context).
- **Dakshina noisy channel** (§2): word k-best + **trigram** native LM ≈ halves sentence WER, beats seq2seq.
- **Vectora (IndoNLP 2025, §8)**: BERT masked-LM sentence scoring — highest accuracy, too heavy/slow for us.
- *Relevance:* unigram (cheapest, +12%) < native bigram/trigram (best value, **our target**) < neural MLM (too heavy). Our "short-context re-ranking" should be a small bigram/trigram Devanagari LM.

## 7. Nepali-specific transliteration & IME work

- **Roy, Paul, Purkayastha (2022). "Statistical and Syllabification Based Model for Nepali Machine Transliteration." CICBA 2022, Springer.** https://link.springer.com/chapter/10.1007/978-3-031-10766-5_2 — English→Nepali names, statistical MT + syllabification, 19,513 parallel entries. Confirms syllable-unit modeling fits Devanagari; name-entity focus limits transfer.
- **K.C. & Thapa (2018). "Removing Language Barrier: A Survey of Machine Transliteration."** — Nepali-authored survey; landscape orientation.
- **"Transliteration System For Nepali Language" (academia.edu).** https://www.academia.edu/74929010/ — rule/syllable-based Roman→Devanagari converter; the common rule/dictionary baseline our re-ranking should improve on.
- **Nepali-NLP-Progress (curated list).** https://github.com/divyamani1/Nepali-NLP-Progress — transliteration entries are sparse. **Nepali-specific literature is thin — the strongest Nepali resource is Aksharantar, not a Nepali-only paper.**
- **Deployed Nepali IMEs (non-academic):** Google Input Tools Nepali (server-side statistical); `scientiac/ne-roman-translit`, `ne-rom-translit` (m17n, rule/dictionary); RomanToNepali / EasyNepaliTyping. Client-side field today = rule/dictionary transliteration with little context modeling — the exact gap our n-gram re-ranking fills.

## 8. IndoNLP 2025 shared task — Real-Time Reverse Transliteration (our task shape; no Nepali)

**Sumanathilaka et al. (2025). "IndoNLP 2025: Shared Task on Real-Time Reverse Transliteration for Romanized Indo-Aryan languages."** arXiv:2501.05816
- Task = **real-time / low-latency reverse transliteration** of Romanized Indo-Aryan text to native script — nearly our exact problem. Languages: Sinhala, Hindi, Bengali, Gujarati, Malayalam — **no Nepali**. Findings: deep learning beat rule-based across the board; **ad-hoc/vowel-dropped typing is the hardest case for every system**. Winning system, **Team Vectora (Sinhala)**: a **hybrid — ad-hoc transliteration dictionary for frequent words + phonetic rule-based fallback for OOV + BERT-MLM sentence-level context disambiguation**, reaching BLEU ≈ 0.91, WER < 0.09, CER ≈ 0.02 (with an explicit note that BERT is the latency bottleneck). Related: TAMZHI (Romanized Tamil) at 93% char / 70% word accuracy.
- *Relevance:* The closest published mirror of our feature. Endorses exactly our layered design — **dictionary/frequency for common words, rule/model fallback for OOV, context LM re-ranking on top** — while warning that heavy contextual re-rankers are the latency bottleneck (use a small n-gram LM instead) and that ad-hoc spelling is where accuracy is lost.

## Synthesis

**Which approach family the literature points to.** For a tiny, fast, smartphone-first, model-optional client-side tool, the evidence converges on a **symbolic noisy-channel design: a small word-level transliterator emitting a top-k candidate list, re-ranked by a compact native-script (Devanagari) n-gram LM**, with **literal Roman pass-through** whenever confidence is low. The word transliterator should be a **character-level pair n-gram / pair-LM (optionally compiled to a WFST)** — trainable directly from Aksharantar's Nepali pairs. IndicXlit (11M params, MIT, Nepali, ~80% top-1 common words) is the right **lazy-loaded, quantized "upgrade"** engine behind the same top-5 UI, never a hard dependency. Purely neural end-to-end or LLM approaches are accurate but too large or latency-heavy for the "performance over accuracy, works offline" mandate.

**The three most load-bearing findings.**
1. **A tiny symbolic model is not a compromise on word-level accuracy.** Dakshina: its 6-gram pair model lands within ~1% absolute CER of tiny LSTM/transformer seq2seq, and wins on the lowest-resource language. We do not need neural nets for the base engine.
2. **Context re-ranking, not a bigger transliterator, is where accuracy is won.** A trigram native LM roughly halved Dakshina's sentence WER and beat seq2seq on 9/12 languages; unigram re-ranking alone gave IndicXlit +12%. The highest-leverage build is a small bigram/trigram Devanagari LM (ideally trained on the archive's own corpus).
3. **The exact deployment target is already proven.** Hellsten/Gboard shipped WFST transliteration for 22 languages at **≤20 ms latency, ~10 MB models, with literal-passthrough OOV fallback** — validating both feasibility at our budget and the graceful-degradation design we require.
