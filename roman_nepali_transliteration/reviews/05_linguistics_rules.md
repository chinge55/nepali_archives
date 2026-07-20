# Review 5: Nepali romanization linguistics & rule design (Opus 4.8 agent, 2026-07-20)

## 1. `pipeline/devanagari_slug.py` — the reverse map, documented

The file does **Devanagari → Roman** with deliberate many-to-one collapses. Our input method must *invert* exactly these collapses (one Roman token → several Devanagari candidates). Full mapping tables as coded:

**Independent vowels (`VOW`)** — note vowel *length is discarded*:

| Devanagari | Roman | | Devanagari | Roman |
|---|---|---|---|---|
| अ, आ | `a` | | ए, ऎ, ऍ | `e` |
| इ, ई | `i` | | ऐ | `ai` |
| उ, ऊ | `u` | | ओ, ऒ, ऑ | `o` |
| ऋ, ॠ | `ri` | | औ | `au` |

**Vowel signs / matras (`MAT`)** — same length collapse:

| Matra | Roman | | Matra | Roman |
|---|---|---|---|---|
| ा | `a` | | े, ॆ, ॅ | `e` |
| ि, ी | `i` | | ै | `ai` |
| ु, ू | `u` | | ो, ॊ, ॉ | `o` |
| ृ, ॄ | `ri` | | ौ | `au` |

**Consonants (`CON`)** — key merges: श+ष→`sh`, व→`b`, त→`t` (dental) but ट→`t` too (retroflex; collapsed), similarly द/ड→`d`, ण/न→`n`:

| | | | | | | | |
|---|---|---|---|---|---|---|---|
| क`k` | ख`kh` | ग`g` | घ`gh` | ङ`ng` | च`ch` | छ`chh` | ज`j` |
| झ`jh` | ञ`ny` | ट`t` | ठ`th` | ड`d` | ढ`dh` | ण`n` | त`t` |
| थ`th` | द`d` | ध`dh` | न`n` | प`p` | फ`ph` | ब`b` | भ`bh` |
| म`m` | य`y` | र`r` | ल`l` | व`b` | श`sh` | ष`sh` | स`s` |
| ह`h` | ळ`l` | | | | | | |

**Multi-codepoint conjuncts (`DIGRAPH`, handled first):** क्ष→`ksh`, त्र→`tr`, ज्ञ→`gya`, श्र→`shr`; nukta letters ड़→`r`, ढ़→`rh`, फ़→`f`, ज़→`z`, क़→`k`, ख़→`kh`, ग़→`g`, य़→`y`.

**Signs (`SIGN`):** anusvara ं→`n`, chandrabindu ँ→*dropped*, visarga ः→`h`, avagraha ऽ→*dropped*, ॐ→`om`. Virama ्→removes the preceding consonant's inherent schwa.

**Two structural rules that matter most:**
1. **Inherent schwa is emitted for every consonant**, then the **word-final schwa is deleted** — *unless* the final consonant was preceded by a virama (a conjunct cluster). So पागल→`pagal` (dropped) but वसन्त→`basanta` (kept, `त` follows conjunct `न्त`). Non-final schwas are always kept.
2. Before a nasal sign the inherent schwa is resolved to `a` first (so …consonant+ं → `…an`).

**Net collapses our input method must invert (the ambiguity generators):** `a`←{अ,आ,ा}; `i`←{इ,ई,ि,ी}; `u`←{उ,ऊ,ु,ू}; `ri`←{ऋ,ृ}; `t`←{त,ट}; `d`←{द,ड}; `n`←{न,ण,anusvara}; `sh`←{श,ष}; `s`←{स}; `b`←{ब,व}; `ch`←{च}; `chh`←{छ}. Aspiration (`kh,gh,ch/chh,th,dh,ph,bh,jh`) and gemination *are* preserved by the slug, so they carry real information.

## 2. Corpus inventory (225 works, ~1.75M chars, ~303k tokens)

**Consonant frequency (bare letters), highest→lowest of the ambiguous sets** — these are the frequency priors for candidate ranking:

| Contrast | Members (count) | Prior |
|---|---|---|
| dental vs retroflex **t** | त 49,799 vs ट 9,050 | dental ~5.5× |
| **th** | थ 8,167 vs ठ 3,385 | dental ~2.4× |
| dental vs retroflex **d** | द 29,699 vs ड 6,298 | dental ~4.7× |
| **dh** | ध 8,025 vs ढ 2,239 | dental ~3.6× |
| **n** | न 80,555 vs ण 5,197 | dental न ~15× |
| **sibilant** | स 46,081 vs श 11,313 vs ष 5,902 | स ≫ श > ष |
| **b / v-w** | ब 21,094 vs व 24,698 | व slightly higher; both read /b/ |
| **affricate** | छ 20,110 vs च 13,290 | **छ > च** (copula छ/छन्) |

**Matras vs independent vowels:** matras dominate by ~15–20× (ा 126,892 vs आ 7,009; ि+ी 99,741 vs इ+ई 9,960; ु+ू 49,429 vs उ+ऊ 10,715). Independent vowels appear almost only word-initially → strong positional prior: **initial position → independent vowel; after a consonant → matra.**

**Virama** ्=116,151 (2nd most frequent codepoint) — conjuncts are pervasive, not incidental.

**Top conjunct clusters (of ~thousands):** त्य 4,630 · प्र 4,404 · न्द 3,682 · न्छ 3,527 · स्त 3,111 · त्र 3,072 · न्त 2,232 · स्व 1,984 · र्+C (र्द, र्य, र्न, र्छ, र्क, र्म, …) very common · ङ्ग 1,674 · **क्ष 1,357** · श्व 1,002 · द्ध 606 · **ज्ञ 481** · न्द्र 504. The r-cluster (`र्C`, i.e. reph) and `C्य`/`C्र`/`C्व` glide clusters are the workhorses.

**Nasalization — register-specific and important:** **chandrabindu ँ 16,580 ≫ anusvara ं 5,575** (3:1) in this classic-literature corpus. This inverts modern/formal usage (where anusvara dominates) — so a prior tuned on modern chat data will mis-rank against this archive. Visarga ः 451, avagraha ऽ 173, ॐ 3 are all rare. ऋ independent 215, vocalic ृ 4,489.

**Punctuation:** danda । 17,800 and double-danda ॥ 9,522 are primary sentence terminators (ASCII `.` only 1,630). Nukta letters (ड़ 3, ढ़ 4) essentially absent → loanword retroflex-flap is negligible in this register.

## 3. Roman → Devanagari ambiguity classes (input pattern → candidates → priority)

Priority ordered by corpus prior + informal-typing conventions. "Ctx" = disambiguating context.

| Roman input | Candidate Devanagari (priority →) | Notes / ctx |
|---|---|---|
| `a` | अ/ा (short) › आ/ा (long) | initial→अ, post-cons→ा; long only if typed `aa` |
| `aa`, `A` | आ / ा | explicit long आ |
| `i`, `e`(as vowel), `ee` | इ/ि › ई/ी | Nepali speakers rarely distinguish length; `ee`,`ii` bias long |
| `u`, `oo`, `uu` | उ/ु › ऊ/ू | `oo`/`uu` bias long |
| `e` | ए/े | vs diphthong below |
| `ai`, `ae` | ऐ/ै › (अइ) | |
| `o` | ओ/ो | |
| `au`, `ao` | औ/ौ | |
| `ri`, `ree`, `rri` | रि (र+ि) › री › **ृ** (matra, if post-cons no-vowel) › ऋ (rare, initial) | vocalic-R is minority |
| `k` | क › क्ष(if `ksh`/`x`) | |
| `kh` | ख | |
| `g`, `gh` | ग / घ | |
| `ng`, `n` (pre-velar) | ङ / anusvara | |
| `ch`, `c`, `cha` | **छ › च** | corpus छ>च; most typists write `ch` for *both* |
| `chh`, `Ch`, **`x`** | छ › (क्ष if word=`x`+ksha-context) | `x`=छ is the dominant chat shorthand ("k xa"=के छ) |
| `chha` | छ | |
| `j` / `jh` | ज / झ | |
| `ny`, `gy`, `gya` | ञ (ny) ; **ज्ञ** (gy/gya) | `gy(a)`→ज्ञ is near-universal |
| `t` | **त › ट** | dental default (5.5:1) |
| `T`, `tt` | ट | explicit retroflex (case/doubling) |
| `th` | थ(dental) › ठ(retroflex) › त्+ह | |
| `d` | **द › ड** | dental default (4.7:1) |
| `D`, `dd` | ड | |
| `dh` | ध › ढ › द्+ह | |
| `n` | **न › ण** › anusvara/ँ | dental न default (15:1) |
| `N`, `nn` | ण | |
| `p`, `ph`, `f` | प / फ / फ(फ़) | `f`→फ; ph→फ |
| `b` | **ब › व** | ब and व both surface as /b/ |
| `bh` | भ | |
| `v`, `w` | व › ब | व default; but व often *sounds* /b/ so `b` competes |
| `m`, `y`, `r`, `l`, `h` | म / य / र / ल / ह | stable |
| `s` | **स › श › ष** | plain स default |
| `sh`, `S` | श › ष › स | ष minority |
| `ksh`, `ksha`, `x`(+a-context), `chhya` | क्ष | `x` overloaded: छ *or* क्ष |
| `tr`, `shr`, `pr`, `kr`, … | त्र / श्र / conjunct with र | glide/`r` clusters |
| `gya`, `jna`, `gyan` | ज्ञ | |
| final `n`/`m`/`~` | anusvara ं › chandrabindu ँ | register-dependent (see §2); nasal vowel→ँ, pre-consonant→ं |
| `om` | ॐ / ओम् | |
| `.`, sentence end | । / ॥ / `.` | danda default in literary text |
| trailing consonant (no vowel) | **schwa-deleted** (halant) vs +अ | invert slug rule (see §5) |

**Overloaded inputs to watch (highest candidate fan-out):** `t` (त/ट), `d` (द/ड), `n` (न/ण/ं/ँ), `s`/`sh` (स/श/ष), `b`/`v`/`w` (ब/व), `ch`/`chh`/`x` (च/छ/क्ष), `ri` (रि/री/ृ/ऋ), word-final consonant (halant vs schwa).

## 4. Normalization-key algorithm (collapse spelling variants → one lexicon key)

**Key architectural insight:** the lexicon key and the query key must pass through the *same* collapse. Build the lexicon key with `normalize(romanize(devanagari_word))` (reusing `devanagari_slug.romanize`, which already collapses length, sibilants, retroflex/dental, व→b) and the query key with `normalize(raw_roman_input)`. `normalize()` must be **strictly coarser than `romanize()`** — it additionally erases the distinctions informal typists don't reliably make (aspiration of the affricate, `x`, doubled vowels/consonants, w/v vs b). Then both sides provably meet in the same key space.

```
function normalize(s):
    s = lowercase(strip(s))
    # 0. strip non-letters, digits, danda, punctuation → single spaces
    s = re.sub(/[^a-z ]+/, ' ', s)

    # 1. multigraph consonant classes (longest match first, left→right)
    s = replace_seq(s, [
        "chh"->"C", "chhy"->"C", "x"->"C",      # छ  (also क्ष; resolve later by lexicon)
        "ch"->"C",  "c"->"C",                    # merge च/छ aspiration → one affricate class
        "ksh"->"kC","gy"->"J","gya"->"J","jn"->"J",  # क्ष, ज्ञ
        "sh"->"s",  "shh"->"s",                  # श/ष → स class
        "ng"->"n",                               # velar nasal → nasal class
        "ph"->"P","f"->"P",                      # फ
        "z"->"j",                                # ज़ → ज
        "w"->"b","v"->"b"                         # व/ब both /b/  (matches romanize's व→b)
    ])

    # 2. retroflex/dental & gemination fold (case already lost → fold doubles)
    s = collapse_runs(s, of=[t,d,n,l,k,s,r,m,p,b,g,C])  # tt→t, dd→d, nn→n, ll→l ...
    # aspiration h AFTER a stop is kept (kh,gh,th,dh,bh,jh,P) — carries info;
    # but th/dh already ambiguous dental~retroflex → leave as th/dh

    # 3. vowel length + variant fold
    s = replace_seq(s, [
        "aa"->"a", "ee"->"i", "ii"->"i", "ai"->"E", "ae"->"E",
        "oo"->"u", "uu"->"u", "au"->"O", "ao"->"O",
        "rri"->"ri"
    ])
    s = collapse_runs(s, of=vowels)   # naaam → nam, kiii → ki

    # 4. schwa normalization: drop word-final 'a' unless preceded by 2+ consonants
    #    (mirrors slug's conjunct-sensitive final-schwa deletion)
    for each word: if word endswith "a" and word[-3:-1] not two-consonants: strip "a"

    # 5. nasalization: any n/m at a syllable/word boundary → single 'n' token
    s = re.sub(/[nm]+(?=($|[ ]))/, "n", s)

    return re.sub(/ +/, " ", s).strip()
```

`collapse_runs` and the `C/J/P/E/O` sentinels are internal — they exist only so both the query and the `romanize()`-derived lexicon key land identically. Equivalence guaranteed: `nam` ≡ `naam` ≡ `naama`; `cha` ≡ `chha` ≡ `xa` (all → `C`-class); `sabda`≡`shabda`; `kasto`≡`kasTo`; `gyan`≡`jnan`≡`gyaan`.

**Candidate ranking (top-5), separate from normalization:** normalization finds the lexicon *bucket*; ranking orders the Devanagari words in that bucket by (a) unigram frequency from the corpus/lexicon, (b) how few "surprising" expansions the surface form required (prefer dental त, स, ब, न per §2 priors), (c) exact-surface bonus if the user typed a length/aspiration marker (`aa`, `chh`, `T`) that a candidate honours. Out-of-lexicon input falls back to deterministic longest-match transliteration with the §3 priority chain.

## 5. Hard cases

1. **Word-final schwa (halant) — the single biggest structural ambiguity.** `ho`→हो but `hos`→होस्; `garchan`→गर्छन्; `man`→मन vs मन् . Roman gives no signal for whether a final consonant carries schwa. Must invert the slug rule + use lexicon: default schwa-deleted, but restore schwa if the deletion yields an illegal/unknown form or if the final consonant follows a conjunct (वसन्त-type). Mid-word schwa deletion (e.g. नमस्ते typed `namaste`) also needs lexicon backing.
2. **Conjunct clusters with no vowel between consonants.** `sst`, `ntr`, `rgh` etc. must be segmented into virama-joined stacks (`न्त्र`=न्+त्+र). Reph (`र्C`, very frequent per §2) is written `r`+consonant in Roman but is the *pre*-posed र-form — `karm`→कर्म not क+र+म. Requires cluster-aware, not char-by-char, expansion.
3. **`x` and `chh` overload.** `x`=छ in chat ("k xa"=के छ) but `x`=क्ष in some typing tools ("xama"=क्षमा). `chh` is almost always छ, but `chhya`/`kchh` can be क्ष. Resolve by lexicon; default `x`→छ (far higher corpus frequency than क्ष).
4. **`gy`/`gya`→ज्ञ vs literal ग्य.** `gyan`→ज्ञान but `bhagya`→भाग्य (ग्य). Both are real; lexicon decides. Default word-initial `gy`→ज्ञ.
5. **Loanwords / nukta letters.** English/Urdu loans want ज़(`z`), फ़(`f`), but the archive corpus barely uses them (ड़/ढ़ near zero) — for *this* register, fold z→ज, f→फ; keep nukta forms only if a modern-text lexicon demands them.
6. **English code-switching ("Nepanglish").** Users type whole English words mid-sentence ("ok cha", "sms garne", "reply diyo"). Need an English-word detector (dictionary + capitalization + non-Nepali phonotactics like consonant clusters `sms`, `str`-initial) to pass such tokens through as Latin rather than transliterate them to garbage.
7. **Length-marked vs unmarked vowels colliding on real minimal pairs.** `bhat` भात (rice) vs भट; `ban` बन/वन/बान; `mari` मरी/मारी/मरि. The normalization key deliberately merges these, so the *ranking* layer (frequency + optional user length markers) must surface the intended one in the top-5.
8. **Nasalization register mismatch.** Because this corpus is chandrabindu-heavy (ँ 3× anusvara) while modern chat priors favour anusvara, a nasal-final input (`chhan`, `hunchha`) should offer *both* ं and ँ candidates; do not hard-default to anusvara if the target lexicon is this classical corpus.

## The 3 most load-bearing findings

1. **`devanagari_slug.romanize()` already defines our collapse — reuse it to key the lexicon.** Its forward map is many-to-one over exactly the distinctions informal typists lose (vowel length; श/ष/स→s(h); त/ट, द/ड, न/ण; व→b). Keying the lexicon with `normalize(romanize(word))` and queries with `normalize(input)` — where `normalize` is one notch coarser (folds `ch/chh/x`, `w/v→b`, doubled letters) — makes both sides provably land in the same bucket. Normalization is the coarse *lookup* layer; a separate frequency+marker *ranking* layer produces the top-5.

2. **Word-final (and internal) schwa deletion is the hardest and highest-value ambiguity, and it's irregular.** Roman input carries no schwa signal; `ho`/`hos`, `man`/`man्` differ only in the invisible final schwa. This cannot be solved by rules alone — it needs the slug's conjunct-sensitive default plus lexicon backing, and it is the main reason a plain char-by-char transliterator produces wrong Devanagari.

3. **Frequency priors are strong but register-dependent.** Dental beats retroflex heavily (त:ट≈5.5:1, न:ण≈15:1), स beats श/ष, and — notably — छ outranks च and **chandrabindu outranks anusvara 3:1** in this classical corpus, the opposite of modern chat. So candidate ranking must be trained on the *target* corpus, not a generic Nepanglish prior, or the top-1 guess for nasals and affricates will be systematically wrong.

**Key sources:** `pipeline/devanagari_slug.py` (reverse map to invert); the 225 `text.txt` files under `archives/authors/*/*/` (frequency priors). External scheme references: Wiktionary Nepali transliteration (IAST-based), nepalgo.de (informal-convention discussion), easynepalityping.com (popular phonetic scheme: `aa/oo/uu`, `chh`, `xa`, `gya`, `tt`/`T` retroflex), Wikipedia Nepali phonology (schwa deletion, व→/b/, sibilant merger, weak nasal-vowel contrast).
