# Review 3: Computation & licensing (Opus 4.8 agent, 2026-07-21)

Scope: what computes the sky, what turns it into panchanga, what handles Bikram Sambat — under the clean-license rule (MPL/MIT/BSD/Apache/CC only, **no (A)GPL**), run at build time in Python, publishing only output text.

## Library inventory

| Library | What it does | License (verified) | Verdict |
|---|---|---|---|
| **Swiss Ephemeris** (`aloistr/swisseph`) | Reference ephemeris + ayanamsha/sidereal/panchanga primitives | **AGPL-3.0 OR paid commercial** (dual) | ❌ Do not link/ship. Offline validation oracle only. |
| **pyswisseph** | Python binding | **AGPL-3.0** | ❌ Binding inherits AGPL. |
| **Moshier `aa`** (Debian astronomical-almanac) | Analytic ephemeris, no data files | **GPL-2.0** | ❌ Copyleft. "Public domain" is a myth about the *model*, not the code. |
| **Moshier-Ephemeris-JS** | JS port | **GPL-3.0** | ❌ |
| **Skyfield** | Pure-Python positional astronomy over JPL kernels | **MIT** | ✅ **Recommended engine.** |
| **jplephem** | Reads JPL `.bsp` kernels | **MIT** | ✅ |
| **astropy** | General astronomy | **BSD-3** | ✅ optional/heavier |
| **JPL DE440/DE441 data** | Position tables (Moon at cm-level) | Positional facts, no copyright asserted | ✅ vendor `de440s.bsp` (~3 MB, 1550–2650) |
| **drik-panchanga** (bdsatish) | Full Drik panchanga | **AGPL-3.0** (+swisseph) | ❌ ship; ✅ best *algorithm reference* |
| **jyotisha** (sanskrit-coders) | Panchanga+festivals | Own code MIT **but depends on pyswisseph (AGPL)** | ⚠️ not clean as-is |
| **jyotishganit** (northtara) | Vedic calc **on Skyfield/JPL** (tithi/nakshatra/yoga/karana) | **MIT** | ✅ Cleanest full-stack reference; validates our approach. |
| **PyJHora** | JHora-equivalent | **AGPL** | ❌ |
| **nepali-datetime** (amitgaru) | BS↔AD, NPT tz | **Apache-2.0**; BS **1975–2100** | ✅ Recommended. |
| JS BS libs (`@nakarmi23/bikram-sambat`, `remotemerge/nepali-date-converter`) | BS↔AD lookup tables | mostly MIT | ✅ if ever client-side |
| **astral** | Sunrise/sunset (Meeus) | **Apache-2.0** | ✅ optional cross-check; Skyfield does rise/set |

## Swiss Ephemeris licensing — exact analysis

Strict dual license ([LICENSE](https://github.com/aloistr/swisseph/blob/master/LICENSE)): choose **AGPL** ("obligation to place his or her whole software project under the AGPL") **or** the paid Professional License, decided "before any public service using the developed software is activated."

- **Is generated output copyleft? No.** [GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.html): program output isn't covered by the program's copyright unless it copies the program. Ephemeris output = uncopyrightable facts.
- **Does build-time-only use trigger AGPL? Strictly, no** — copyleft triggers on conveying or network interaction (AGPL §13). Private build-machine use emitting static text is permitted private use.
- **Why still avoid it:** (1) AGPL in the toolchain is the exact audit burden the house rule prevents; (2) safety is contingent on never shipping the generator and never exposing a live endpoint — the moment a "daily horoscope API" appears, §13 bites the whole service; (3) an equally accurate permissive path exists. **Keep swisseph out of the pipeline; a local `swetest` as an offline validation oracle is fine.**

## Moshier — the "public domain" trap

The PD claim refers to the analytic *model*; all usable code is copyleft: Debian `aa` = GPL-2 ([copyright file](https://sources.debian.org/copyright/license/astronomical-almanac/)), the JS port GPL-3, via swisseph AGPL. Skyfield+JPL is both permissive and more accurate — Moshier offers no advantage.

## Recommended clean stack: Skyfield (MIT) + JPL DE440 + our own anga layer

**Precision:** DE440's Moon is lunar-laser-ranging cm-level; Skyfield apparent ecliptic longitudes are sub-arc-second. A rashi is 30° (108,000″), a nakshatra 13°20′ (48,000″); the Moon moves ~0.5°/hr — arc-second error ⇒ sub-second anga-boundary error. **The ephemeris is never the limiting factor; convention choices (ayanamsa, sunrise, day boundary) are.**

### The math we own (small, auditable, license-free)

λ☾/λ☉ = apparent ecliptic longitudes of date from Skyfield:

- **Ayanamsa — True Chitra Paksha** (drikpanchang's default): `ayanamsa(t) = tropical_longitude(Spica, t) − 180°` — compute Spica (HIP 65474, with proper motion) in Skyfield directly; tracks drikpanchang exactly. Sanity fallback: linear Lahiri, J2000 = 23.853222°, +~50.29″/yr. **Caveat: NPNS (Nepal) may use its own conventions — validate against a Nepali patro too.**
- **Sidereal:** `λ_sid = (λ_trop − ayanamsa) mod 360°`
- **Rashi** = `floor(λ☾_sid / 30°)`; **Nakshatra** = `floor(λ☾_sid / 13°20′)` (pada = quarter)
- **Tithi** = `floor(((λ☾−λ☉) mod 360°)/12°)+1` — **ayanamsa-invariant** (robustness fact)
- **Karana** = half-tithi (6°), 60 half-tithis → 11-karana cycle — ayanamsa-invariant
- **Yoga** = `floor(((λ☉_sid+λ☾_sid) mod 360°)/13°20′)` — **ayanamsa-dependent**; pin ayanamsa before validating
- **Anga end-times:** root-find boundary crossings (report anga at sunrise + end time, like drikpanchang)
- **Sunrise (Kathmandu 27.7172°N, 85.3240°E):** Skyfield rise/set (USNO −0.8333°); astral as cross-check. Panchanga "today" = values at local sunrise.
- **BS date:** nepali-datetime (lookup-table based — accuracy = table quality; authority is the NPNS patro; watch month-boundary off-by-ones).

## Validation plan

1. **Oracle A — swetest offline** (never shipped): raw λ☉_sid/λ☾_sid within a few arc-seconds — isolates ephemeris/ayanamsa from anga logic.
2. **Oracle B — drikpanchang.com** (Kathmandu, 40–60 dates incl. boundary/kshaya/vriddhi edge cases): anga names exact; end-times within ~1 min; sunrise within ~1 min.
3. **Oracle C — Nepali patro** (NPNS/hamropatro): BS dates + Nepal-specific conventions; flag systematic offsets.
4. **Regression fixture:** freeze ~50 validated days as a test file so ephemeris upgrades can't silently drift the pages.
5. **Failure protocol:** names match but end-times drift minutes ⇒ suspect ayanamsa variant or sunrise constants, not the ephemeris.

## The 3 most load-bearing findings

1. **Swiss Ephemeris is AGPL-or-paid; the danger isn't the output — it's the toolchain and the future live endpoint.** Output is uncopyrightable, build-time private use is defensible, but AGPL §13 turns any on-demand horoscope API into whole-project AGPL. Keep it out (offline oracle only).

2. **"Moshier is public domain" is false for any usable code** (GPL-2/GPL-3/AGPL variants only). No clean drop-in exists, and none is needed.

3. **The clean, sufficient stack is Skyfield (MIT) + JPL DE440 + a ~50-line owned anga/ayanamsa layer + nepali-datetime (Apache-2.0).** Accuracy is bounded by convention choices, not the ephemeris — adopt True Chitra Paksha to match drikpanchang, validate against a NEPALI patro as well, and jyotishganit (MIT, Skyfield-based) proves the architecture.

**Key sources:** [Swiss Ephemeris LICENSE](https://github.com/aloistr/swisseph/blob/master/LICENSE) · [pyswisseph](https://pypi.org/project/pyswisseph/) · [GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.html) · [Debian aa copyright](https://sources.debian.org/copyright/license/astronomical-almanac/) · [Skyfield](https://rhodesmill.org/skyfield/) · [JPL DE440/441](https://ssd.jpl.nasa.gov/doc/de440_de441.html) · [drik-panchanga](https://github.com/bdsatish/drik-panchanga) · [jyotishganit](https://github.com/northtara/jyotishganit) · [nepali-datetime](https://github.com/amitgaru/nepali-datetime) · [drikpanchang](https://www.drikpanchang.com/) · [True Chitrapaksha](https://www.apa-software.com/True%20Chitrapaksha%20Lahiri%20Ayanamsha.html)
