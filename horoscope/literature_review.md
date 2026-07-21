# राशिफल / पञ्चाङ्ग service: Literature Review & Build Document

*Reconciled from five parallel reviews (2026-07-21): ज्योतिष domain & Nepali
tradition, products & market, computation & licensing, content generation,
and static architecture. Full reports with sources in [`reviews/`](./reviews/).
This is the synthesis: what exists, what fits this archive, and the draft plan.*

---

## 1. Verdict up front

All five reviews converge on the same split, from different directions:

> A horoscope product has two layers. The **computed layer** — पञ्चाङ्ग (तिथि,
> वार, नक्षत्र, योग, करण), BS date, राशि transits, साइत windows — is
> deterministic astronomy + classical rules: evergreen, citable, license-clean,
> buildable at build time, and genuinely heritage. The **written layer** — the
> daily per-राशि prose — is a commodity: in Nepal it is overwhelmingly Hamro
> Patro's anonymous text re-syndicated by everyone else, increasingly
> AI-generated industry-wide, and descended not from the classics but from a
> 1930 British newspaper stunt (R.H. Naylor's 12-sign column).

**So the recommendation is: build the computed layer as the product, and
derive the written layer from it** — a rule engine over public-domain
classical texts (बृहत्संहिता, फलदीपिका) rendering short prose from a
valence-tagged template pool, clearly labelled, with a daily classical
citation as the archive's signature. Frame the whole thing as **पात्रो/पञ्चाङ्ग
heritage** (राशिफल as a section within), not as a fortune-telling page.

What this is NOT: not an LLM writing daily predictions (off-charter:
non-reproducible, uncitable — and unnecessary), not scraping/syndicating
anyone's feed, not a fight with Hamro Patro over "आजको राशिफल" (unwinnable
head term; identity-corroding to chase).

## 2. The authenticity contract (from the domain review)

1. **चन्द्र राशि, not sun signs.** The Nepali राशिफल is moon-sign based; the
   daily reading is a गोचर (transit) of today's Moon against each राशि. Users
   find their राशि via the **नामाक्षर table** (चु-चे-चो-ला… — full table in
   reviews/01) or birth data — never a birth-month picker.
2. **The rules are public domain.** Favorable-house tables (बृहत्संहिता
   Ch.104), Moon-transit + वेध obstruction pairs (फलदीपिका Ch.26), चन्द्राष्टम
   (Moon in 8th — the headline daily flag), ताराबल (9-tara day quality per
   birth-star): authors 500–1400 years dead. The engine can cite its sources.
   **Modern translations and B.V. Raman are copyrighted — rule reference only.**
3. **Sunrise + Kathmandu + Bikram Sambat.** Panchanga angas are reckoned at
   local sunrise; pages lead with the BS date; NPNS (नेपाल पञ्चाङ्ग निर्णायक
   समिति) is the legal authority whose patro we validate against.
4. **Quote the classics only for what they actually say.** बृहत्संहिता's
   Chandra-chara chapter is mundane astrology (omens/rainfall), not personal
   horoscopes; the per-house "outcome" sentences on commercial sites are
   modern editorializing. No fake ancient quotes.

## 3. What actually varies daily (the design keystone)

The Moon's राशि changes only every **~2.25 days** — daily text keyed to it
alone repeats. Honest daily variation comes from the faster limbs:

| Signal | Cadence | Role |
|---|---|---|
| **नक्षत्र → ताराबल per राशि** | ~daily | **the main per-राशि differentiator** (9 taras, classical valences) |
| वार (weekday lord) | daily | colours the day |
| तिथि (30) / योग (27) / करण (11) | ~daily/half-daily | day-quality classes |
| चन्द्र गोचर house + चन्द्रबल | ~2.25 days | slower background layer |

Weekday × ताराबल × तिथि/योग valence ⇒ thousands of distinct, citable,
per-राशि states — varied daily text with **zero invention**.

## 4. Computation stack (license-clean, from the computation review)

- **Skyfield (MIT) + JPL DE440** (`de440s.bsp`, ~3 MB, positional facts) —
  sub-arc-second Moon vs 30° rashi sectors: the ephemeris is never the
  limiting factor; conventions are.
- **A ~50-line anga layer we own**: True Chitra Paksha ayanamsa (Spica−180°,
  computed from Skyfield directly), sidereal rashi/nakshatra (30°/13°20′
  sectors), tithi & karana from elongation (ayanamsa-invariant), yoga from the
  sum, boundary end-times by root-finding, Kathmandu sunrise.
- **nepali-datetime (Apache-2.0)** for BS dates (table-based, BS 1975–2100).
- **Hard NOs**: Swiss Ephemeris / pyswisseph (**AGPL-or-paid** — output would
  be legal, but AGPL in the toolchain violates the house rule and a future
  live API would trigger §13); Moshier ports (all GPL — "public domain" is a
  myth about the model, not the code); drik-panchanga & PyJHora (AGPL).
  `jyotishganit` (MIT, Skyfield-based) is the clean reference proving the
  architecture.
- **Validation**: offline swetest oracle (never shipped) → drikpanchang.com
  (~50 dates incl. boundary edge cases; names exact, times ±1 min) → **a
  Nepali patro** (NPNS conventions may differ from Indian defaults) → frozen
  regression fixture in the repo.

## 5. Content generation (from the content review)

- **Deterministic rule + template pool on the critical path; no LLM.** LLM
  output is non-reproducible and uncitable — off-charter for a repo whose
  rule is "sources only, CI rebuilds, faithful to the source." (Cost was
  never the issue: ~$2/yr on Haiku. The decision is philosophical.)
- Prose register (from real Hamro Patro/Ratopati samples, quoted in
  reviews/04): 3–4 sentences, ~45–60 words, future/potential mood (-नेछ,
  -होला, -ला), rotate काम/स्वास्थ्य/प्रेम/आम्दानी/परिवार + one hedged caution,
  optional शुभ रंग/अंक footer. Template slots keyed to the computed valence.
- **The signature feature: a daily classical citation** — a public-domain
  श्लोक (Devanagari + Nepali rendering) selected by today's नक्षत्र/योग, in
  the vein of the *Candra Gocara Dīpikā* (computed transits + cited बृहत्संहिता
  verses). This is what no Nepali competitor does and what only an archive
  would do.
- **Label the prose मनोरञ्जन/सांस्कृतिक** with a short disclaimer — Nepali
  outlets print none; we can be better.

## 6. Architecture (from the architecture review)

- **Decisive fact**: `deploy.yml` already builds `site/` in-workflow and
  publishes via `actions/deploy-pages@v4` — **no commits of build output**. A
  daily scheduled run regenerates "today" with a clean git history.
- **Substrate = committed, dated sources** (like `text.txt`): panchanga is
  deterministic (precomputable years ahead); template prose is generated in
  reviewed batches and committed. Dated pages `/rashifal/<BS-date>/` persist —
  **a राशिफल archive, which suits this site's identity**.
- **A thin daily cron re-points `/rashifal/` at today**: two crons at
  off-peak minutes after Kathmandu's latest sunrise (~00:45–01:37 UTC),
  `workflow_dispatch` for recovery, Healthchecks.io dead-man's-switch —
  GitHub cron is delayed/dropped by design, so the architecture fails soft
  (yesterday's real page stays up, with an honest "पुरानो" banner rule).
- **Pages stay JS-free** (the /type/ precedent). Client-side ephemeris
  rejected (heavy JS, no SEO text, stores nothing).
- SEO: date in title/H1/URL, Article JSON-LD with +05:45 timestamps, add a
  `lastmod` XML sitemap; compete on the long tail + "no ads, no tracking,
  free forever" — not the head keyword.

## 7. Mission tie-ins (the part that makes this belong here)

1. **Classical citations turn the page into a doorway to the corpus.**
2. **Acquisition candidates surfaced**: दैवज्ञ बलभद्र जोशी (b. 1494, Jumla —
   *Bhāsvatī* commentary; firmly PD, genuinely Nepali jyotish), early
   **Toyanath Panchanga** editions (1946 BS lineage; death-date check
   needed), Pandit Hemraj Sharma's works — real future archive entries under
   the standard rights process.
3. The **BS calendar + पञ्चाङ्ग is heritage** — the framing (nav item
   पात्रो/पञ्चाङ्ग, राशिफल inside) keeps the literature archive coherent.

## 8. Open questions (for your refinement pass)

1. **Naming/framing**: `/patro/` (पात्रो-first, राशिफल a section — my
   recommendation) vs `/rashifal/` (horoscope-first, bigger draw, bigger
   identity risk)?
2. **Scope of v1**: panchanga + चन्द्राष्टम/ताराबल per राशि + citation only?
   Or include template prose per राशि from day one?
3. **शुभ रंग/अंक**: traditional footer, but pure invention (no classical
   basis) — include for familiarity or drop for authenticity?
4. **Dated archive**: keep every day forever (archival identity) or last N
   days (less crawl surface)?
5. **NPNS alignment**: validate against which Nepali patro as authority
   (Toyanath lineage vs hamropatro's rendering)?

## 9. Draft plan (POC-first, per house rules)

**Stage 0 — rules doc**: authenticity contract (§2), disclaimer text, framing
decision, license rules (no AGPL anywhere near the pipeline).

**Stage 1 — panchanga engine (the POC)**: `horoscope/pipeline/panchanga.py` —
Skyfield + DE440 + owned anga layer; CLI printing a full Kathmandu panchanga
for any date; validation harness vs drikpanchang + a Nepali patro (~50-date
frozen fixture). *Success = names match exactly, times within a minute — the
path exists.*

**Stage 2 — the daily state machine**: per-राशि ताराबल/चन्द्रबल/गोचर
computation + valence scoring; the classical citation selector (a small
curated PD श्लोक corpus keyed by नक्षत्र/योग); template pool in the measured
register.

**Stage 3 — the page**: `/patro/` in `build_site.py` (site chrome, JS-free,
BS-date header, panchanga block, राशि grid with नामाक्षर, citation, disclaimer),
dated archive pages, JSON-LD + sitemap.

**Stage 4 — the daily loop**: scheduled workflow (two crons + dispatch +
dead-man's-switch), fail-soft fallback, live validation period against
drikpanchang/patro before announcing.

*(Stages 2–4 deliberately thin until Stage 1 proves the numbers match — same
discipline as the transliteration project.)*
