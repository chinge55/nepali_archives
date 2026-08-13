# Review 4: Content generation (agent review, 2026-07-21)

*Facet: how to GENERATE the daily text — rule-based vs. template vs. agent vs. hybrid, with an authenticity-first recommendation.*

## 1. Rule-based generation from classical transits (गोचर)

### 1a. The moon-transit-from-natal-moon scheme — the actual basis of daily rashifal

Daily rashifal is, at root, **Chandra gochara**: the Moon's current sign read as a house-count from each rashi (treated as the natal Moon sign). The Moon changes sign every ~2.25 days ([PocketPandit](https://blog.pocketpandit.com/moon-transit/); [astrobix](https://astrobix.com/engcontent/346-gocharfal-transit-of-moon.aspx)).

The classical benefic/malefic house scheme (from **B.V. Raman, *Hindu Predictive Astrology*, ch. 34**, reproduced at [vedastro.org](https://vedastro.org/blog/Hindu-Predictive-Astrology-Chapter-34-Gocharaphala-or-Results-of-Transits.html)):

| Planet | Good houses (from natal Moon) | Bad houses |
|---|---|---|
| Sun | 3, 6, 10, 11 | 1,2,4,5,7,8,9,12 |
| **Moon** | **1, 3, 6, 7, 10, 11** | **2, 4, 5, 8, 9, 12** |
| Mars | 3, 6, 10, 11 | rest |
| Mercury | 2, 4, 6, 8, 10, 11 | rest |
| Jupiter | 2, 5, 7, 9, 11 | rest |
| Venus | 1,2,3,4,5,8,9,11,12 | 6,7,10 |
| Saturn | 3, 6, 11 | rest |

A concrete per-house **result-list for the Moon** (from [astrobix](https://astrobix.com/engcontent/346-gocharfal-transit-of-moon.aspx) — a modern summary in the classical tradition):

- **1st:** fortunate; wealth and happiness increase. **2nd:** financial problems; disappointment. **3rd:** auspicious; support of friends. **4th:** affects mental capacity. **5th:** problems from cough/diseases. **6th:** physically fit; success. **7th:** fortunate; income increases. **8th:** health problems; stress. **9th:** less fortunate; children's support lacking. **10th:** auspicious in business. **11th:** many benefits; happy state of mind. **12th:** expenditures increase; respect affected.

### 1b. Vedha (obstruction) — cancellation rules

A "good" transit is cancelled if another planet sits in the Vedha house. Moon's good→vedha pairs (Raman, via [vedastro](https://vedastro.org/blog/Hindu-Predictive-Astrology-Chapter-34-Gocharaphala-or-Results-of-Transits.html)): 7↔2, 1↔5, 6↔12, 11↔8, 10↔4, 3↔9. **No Vedha between Moon and Mercury** ([ashtakvargajyoti](https://ashtakvargajyoti.wordpress.com/2015/01/30/rashi-gochar-vedha-transit-based-planetary-obstruction/)).

### 1c. Tarabala & Chandrabala — the per-rashi day-quality score

This is the mechanism that actually **varies daily per rashi**, fully computable and citable.

**Chandrabala**: count from janma rashi to the Moon's current sign; present when the count is **1, 3, 6, 7, 10, 11** ([astroved](https://www.astroved.com/astropedia/en/freetools/tarabalam); [cosmicinsights](https://blog.cosmicinsights.net/importance-of-tarabala-and-chandrabala-in-muhurta/)).

**Tarabala** (Navatara): count nakshatras from janma nakshatra to today's nakshatra (inclusive), ÷9; the remainder names one of nine taras ([sarvatobhadra](https://www.sarvatobhadra.com/navtara-chakra-explained/)):

| # | Tara | Valence | Theme |
|---|---|---|---|
| 1 | Janma | neutral | one's own nature |
| 2 | Sampat | good | wealth, resources |
| 3 | Vipat | bad | danger, loss |
| 4 | Kshema | good | well-being, health |
| 5 | Pratyari | bad | obstacles |
| 6 | Sadhaka | good | achievement |
| 7 | Naidhana | bad (worst) | death/suffering |
| 8 | Mitra | good | friends |
| 9 | Parama-mitra | good | best friend/community |

**Verdict on rule-based sufficiency:** enough classical material exists to *compute a defensible daily valence per rashi* (Chandrabala + Tara) with a short classical rationale. But the **flowery per-house outcome sentences are modern editorializing, not verbatim classical text** — see §5. Rules are excellent for *facts and score*; not, alone, a source of varied article-length prose.

## 2. What actually varies daily (the core problem)

The Moon's **sign** changes every **~2.25 days** — consecutive days often share the same Chandra-gochara house for every rashi. Honest daily variation must come from the faster panchanga limbs ([AstroSight](https://astrosight.ai/nakshatras/panchang-elements-tithi-vaar-nakshatra-yoga-karana); [Muhuratam](https://www.muhuratam.in/blog/how-panchang-works)):

| Element | Cadence | Distinct states | Usable daily signal |
|---|---|---|---|
| **Vara** (weekday lord) | 1 day | 7 | Ruling planet colours the day; deterministic |
| **Tithi** (lunar day) | ~1 day | 30 | Named, each with valence; nanda/bhadra/jaya/rikta/purna groups |
| **Nakshatra** | ~1 day | 27 (+4 padas ≈ 6h) | Moon's mansion — **drives per-rashi Tarabala** |
| **Yoga** | ~1 day | 27 | Each classed auspicious/inauspicious |
| **Karana** | ~½ day | 11 | Half-tithi; movable/fixed |
| **Tarabala** (per rashi) | ~daily | 9 taras | **The main per-rashi daily differentiator** |
| **Chandrabala** (per rashi) | ~2.25 days | present/absent | Slow — supporting, not driving |

**Design consequence:** key each rashi's text off **(weekday lord × today's nakshatra→Tarabala × tithi/yoga valence)**, with Chandra-gochara house and Chandrabala as the slower background layer. That combination changes every day → thousands of distinct states, no same-as-yesterday repetition, zero invention.

## 3. How commercial horoscope prose is actually produced

- **Origin: a 1930 newspaper stunt.** R.H. Naylor's Sunday Express column and his 1937 invention of the 12 sun-sign blocks created the modern daily horoscope ([Wikipedia](https://en.wikipedia.org/wiki/R._H._Naylor); [Mental Floss](https://www.mentalfloss.com/article/634011/princess-margaret-modern-horoscope-inspiration)). The daily 12-sign column format is a ~95-year-old media product, distinct from classical panchanga.
- **Industry production is templated and generalized** ([Astrodienst practical guide](https://www.astro.com/astrology/aa_article200602_e.htm)).
- **Barnum/Forer effect**: Forer (1948) — identical profile from horoscope columns rated ~4.3/5 self-accurate ([Wikipedia](https://en.wikipedia.org/wiki/Barnum_effect)). **Gauquelin (1968)**: same horoscope (a mass-murderer's chart) mailed to thousands — 94% rated it accurate.

**Takeaway:** vague, positively-framed, domain-tagged sentences ARE the working commercial technology. A rotating template pool keyed to the daily panchanga state is how the honest end of the industry operates.

## 4. Prose-register analysis of real Nepali दैनिक राशिफल

Sources: **Hamro Patro**, **Ratopati**, **DCNepal**.

**Structure (consistent):**
- **Length:** 3–4 short sentences per rashi, **~45–60 Nepali words**.
- **Categories rotated** (2–3 of): काम/जिम्मेवारी, स्वास्थ्य, प्रेम/सम्बन्ध, आम्दानी/लगानी, परिवार, शिक्षा, plus a caution (सचेत/सतर्क).
- **Hamro Patro** appends **शुभ रंग** + **शुभ अंक** (1–9): "आजको शुभ रंग [रङ] हो भने शुभ अंक [अंक] रहेको छ।" News portals usually omit them.
- No panchanga shown to the reader; only a BS date header. No disclaimer in the news-portal samples.

**Verbatim exemplars:**
> मेष: "आज जोगिएर काम गर्नुपर्ने दिन छ। कुनै कुराले मनमा खिन्नता बढ्नेछ। खानपानमा ख्याल नगर्दा स्वास्थ्यमा समस्या हुनेछ। मित्र बढ्नेछन्।"
> वृष: "तपाईंका लागि दिन राम्रो छ। सोचेका काम बन्नेछन्। रोग प्रतिरोधात्मक क्षमता बढ्नेछ। शिक्षामा जोसजाँगर बढ्ने।"
> मिथुन: "कुनै आकस्मिक घटनाले सोच्ने दृष्टिकोण बदल्न सक्छ। … विचार गरेर मात्र विश्वास गर्नुहोस्।"

**Template grammar:** future/probable tense (`-नेछ`, `-न सक्छ`), hedged conditional (`ख्याल नगर्दा …`), gentle imperative advice. Slot structure: `{domain-opening} + {conditional-caution} + {advice-imperative} [+ शुभ रंग/अंक]`, valence chosen by computed Tarabala + tithi/yoga class.

## 5. The archive's authenticity angle — the strongest differentiator

- **Panchang IS "computed data + classical rules"** ([prokerala](https://www.prokerala.com/astrology/panchang/)); Drik Panchang is the reference implementation.
- **Prior art for computed transits + cited Sanskrit verses:** the *2026 Candra Gocara Dīpikā* presents Moon-transit guidance as **"three verses from the Bṛhat Saṁhitā… original Devanāgarī, IAST, word-for-word meanings, full English translations"** ([Atma Occult](https://atmaoccult.com/2026-candra-gocara-dipika/)) — exactly the "computed + citation" model, adoptable in Nepali.
- **Public-domain sources:** Varāhamihira's *Bṛhat Saṁhitā* (6th c.) and *Bṛhat Jātaka* are PD; 19th-c. translations (Chidambaram Iyer 1884) too — Sanskrit + English on [wisdomlib](https://www.wisdomlib.org/hinduism/book/brihat-samhita). **B.V. Raman is NOT PD** (d. 1998) — rule reference only, never reproduce text.
- **⚠️ Authenticity caveat:** the *Bṛhat Saṁhitā*'s Chandra-chara chapter is largely **mundane astrology (omens/rainfall), not personal daily horoscopes**. Personal gochara result-lists are codified in later medieval manuals; sentence-level "outcomes" on modern sites are editorial. Quote classics for what they *actually say* (benefic-house scheme, Tarabala structure, nakshatra natures) — never dress modern predictions in a fake ancient quote.

## 6. Generation-approach comparison

| Approach | Authenticity fit | Repetition risk | Cost | Reproducible/citable | Offline / zero-dep |
|---|---|---|---|---|---|
| **Astrologer-written** | High (if real jyotishi) | Low | Ongoing human labour | Yes | N/A |
| **Rule + template pool** | High (facts real; prose framed) | Low **if keyed to daily panchanga state** | ~zero | **Yes — deterministic, rebuildable** | **Yes** |
| **Pure agent** | **Low** — hallucinates, non-reproducible | Low | Trivial | **No** | No |
| **Hybrid (rules compute → agent/template renders)** | Medium-High | Low | Trivial | Partial | Only with template fallback |

### agent specifics
- High-intelligence agents handle short Nepali prose better than smaller agents.
- Batch-generation cost is operationally minor; reproducibility is the real issue.
- **The real blocker is the repo's own charter**: "repo holds ONLY sources… CI rebuilds every build" + "faithful to the source." agent output is non-deterministic and non-reproducible — **agent-as-centerpiece is architecturally and philosophically off-charter.**
- If used anyway: cron CI call with **mandatory deterministic template fallback** on any failure — meaning templates must exist regardless; agent is at best enrichment.

## 7. Disclaimer / ethics norms

- **Global norm:** "for entertainment purposes only… not professional advice"; warnings against health/financial/legal decisions.
- **Nepali practice:** sampled outlets print rashifal **without** a disclaimer — a gap the archive can improve on with a short Nepali framing line (मनोरञ्जन/सांस्कृतिक).
- **Recommendation:** frame as **cultural preservation of the panchanga/jyotisha tradition**; show computed facts + cited classical source; label per-rashi prose मनोरञ्जन; keep visibly separate from the scholarly corpus.

## 8. Opinionated recommendation

**Build a deterministic, offline, rule-driven "पञ्चाङ्ग + शास्त्रीय उद्धरण" feature; per-rashi prose as clearly-labelled template output; NO agent on the critical path.**

1. **Compute daily at build time (deterministic):** tithi, vara, nakshatra(+pada), yoga, karana; per rashi: Chandra-gochara house, Chandrabala, Tarabala.
2. **Lead with authenticity:** panchanga facts + a **daily public-domain classical citation** (Bṛhat Saṁhitā/Bṛhat Jātaka verse in Devanāgarī + Nepali translation) chosen by today's nakshatra/yoga. Quote classics only for what they actually say.
3. **Render per-rashi prose from a valence-tagged template pool** keyed to (weekday lord × Tarabala × tithi/yoga valence), Hamro-Patro register: 3–4 sentences, rotate काम/स्वास्थ्य/प्रेम/आम्दानी, optional शुभ रंग/अंक.
4. **Label मनोरञ्जन** with a cultural-framing disclaimer.
5. **agent only as optional non-blocking enrichment** (skip initially).

## The 3 most load-bearing findings

1. **The Moon's sign changes only every ~2.25 days — honest daily variation must be driven by the faster panchanga limbs, above all today's *nakshatra → per-rashi Tarabala* (plus weekday lord, tithi, yoga).** That computed combination changes every day and yields thousands of distinct, citable per-rashi states — varied text with zero invention.

2. **A deterministic rule+template engine is the only approach that fits this archive's charter; agent-as-generator is off-charter.** Non-reproducible output clashes with "sources only, CI rebuilds" and "faithful to the source." Cost is negligible either way — the decision is philosophical, not financial.

3. **The winning move is "computed panchanga + genuine public-domain classical citation" (a real product category — cf. the Bṛhat Saṁhitā-quoting *Candra Gocara Dīpikā*), with per-rashi prediction reduced to clearly-labelled entertainment** — but only if citations quote the classics for what they actually say, since commercial per-house "outcome" sentences are modern editorializing.
