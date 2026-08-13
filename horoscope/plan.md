# पात्रो/राशिफल: Project Plan

**Status (2026-08-13):** Monthly coverage extended. Computed panchanga now
covers 2026-07-01 through 2026-09-30 (92 dated pages), and reviewed prose
covers 2026-07-21 through 2026-09-30 (72 days, 864 राशि readings). The new
August and September batches produced 732/732 mechanically valid entries.
The editorial audit found no exact duplicated readings, verified every
explicit house reference against the computed state, checked every
चन्द्राष्टम caution, and found no concrete medical, financial, or legal
instruction. Seven awkward literal caution phrases were corrected, and the
writer prompt now rejects that robotic construction. Daily builds still make
zero agent calls; committed prose remains an optional layer over the
deterministic fallback.

**Status (2026-07-21b):** Stage 2.5 DONE — offline agent prose layer, reconciled
with principle 2: the rules engine stays the authority
(valence/house/चन्द्राष्टम computed, never agent-decided);
`pipeline/generate_month.py` uses a private local execution binding in monthly batches →
mechanical validator (Devanagari-only charset, no Latin, 100–650 chars,
≥3 sentences, final danda; failures dropped) → `content/YYYY-MM.json`
committed as reviewed source. `build_patro_page.py` prefers committed prose,
falls back per-राशि to the deterministic templates — daily build makes ZERO
API calls. First batch: 2026-07-21/22, 24/24 texts passed, quality verified
against computed facts (houses correct, कुम्भ सावधान+चन्द्राष्टम caution
present). "No agent on the critical path" holds: the agent is an offline batch
stylist; templates remain the always-working floor.

**Status (2026-07-21):** literature review approved ("I like this, go ahead").
Stage 0 DONE (rules.md). Stage 1 DONE: panchanga.py (Skyfield+DE440s, ~230
lines, patro_env; ephemeris cached on the free disk) validated against
drikpanchang Kathmandu on 3 dates — ALL anga names exact; tithi/karana end
times 0-1 min; nakshatra/yoga/rashi 2-5 min (our True-Chitra vs theirs ~1-2
arc-min apart — tuning item, tolerance ±6 min in the frozen fixture
validate_panchanga.py); BS dates match nepali-datetime AND Ramro Patro's
published header. Next: Stage 2 (per-राशि state machine + citations +
templates — needs native-speaker review of श्लोक renderings).
Decisions locked from the review's recommendations: framing = **पात्रो-first**
(`/patro/`, राशिफल a section within); v1 = computed layer first; dated pages
kept forever (archival identity); validation authority = drikpanchang
(Kathmandu) cross-checked against hamropatro's rendering; शुभ रंग/अंक decision
deferred to Stage 2 (no classical basis — leaning drop or clearly-marked).

## Principles (from the review; inherit the house rules)

1. Authenticity contract: चन्द्र-राशि/गोचर system, नामाक्षर table, sunrise-
   reckoned Kathmandu panchanga, BS-date-first, classical citations quoted
   only for what they actually say. Never a birth-month picker.
2. Deterministic everything on the critical path. No agent. No AGPL anywhere
   near the pipeline (swisseph allowed ONLY as a local validation oracle,
   never in requirements, never shipped).
3. Static, JS-free pages; fail-soft daily loop; committed dated sources.
4. मनोरञ्जन/सांस्कृतिक disclaimer on every rashifal surface.

## Stages

**Stage 0 — rules.md** (this commit): the contract above, frozen.

**Stage 1 — panchanga engine (the POC).** `horoscope/pipeline/panchanga.py`:
Skyfield (MIT) + JPL DE440s + owned anga layer (ayanamsa, rashi, nakshatra,
tithi, yoga, karana, end-times, Kathmandu sunrise) + nepali-datetime BS.
CLI prints a full panchanga for any date. Validation harness
(`validate_panchanga.py`) compares against drikpanchang + hamropatro for
sample dates; frozen fixture becomes the regression test.
*Exit: anga names at sunrise match the references exactly on the sample;
end-times within ~1-2 min; BS dates match. The path exists.*

**Stage 2 — the daily state machine.** Per-राशि गोचर house, चन्द्रबल,
ताराबल + valence scoring; the citation corpus (curated PD श्लोकहरू keyed by
नक्षत्र/योग, with Nepali renderings — needs native-speaker review); the
template pool in the measured register (reviews/04 §4). Repetition audit
across a simulated year.

**Stage 3 — the page.** `/patro/` in build_site.py: site chrome, BS-date
header, panchanga block with end-times, चन्द्राष्टम line, राशि grid with
नामाक्षर, daily citation, disclaimer; dated pages `/patro/<BS-date>/`;
JSON-LD + lastmod sitemap. verify-site-change pass.

**Stage 4 — the daily loop.** patro.yml workflow: two off-peak crons after
KTM sunrise (~01:07 & 01:37 UTC) + workflow_dispatch + Healthchecks ping;
build-time assertion + fail-soft to newest dated page with "पुरानो" banner.
Soak-test against references for a couple of weeks before adding to nav.

*(Stages 2–4 detail thin until Stage 1's numbers match — house discipline.)*
