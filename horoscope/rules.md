# पात्रो/राशिफल — project rules (Stage 0, frozen 2026-07-21)

## Authenticity contract
- चन्द्र राशि (moon sign) + गोचर system. Users find their राशि via the
  नामाक्षर table or birth data — NEVER a birth-month/sun-sign picker.
- Panchanga reckoned at Kathmandu sunrise; pages lead with the BS date.
- Rules cited to public-domain classics (बृहत्संहिता Ch.104, फलदीपिका Ch.26,
  ताराबल/नवतारा). Modern translations & B.V. Raman: reference only, never
  reproduced. Citations quote classics only for what they actually say —
  no fake ancient quotes around modern editorial.
- Validation authority: drikpanchang (Kathmandu) + hamropatro cross-check;
  disagreements investigated, never papered over.

## Engineering rules
- Deterministic critical path: Skyfield (MIT) + JPL DE440 + owned anga layer
  + nepali-datetime (Apache-2.0). Reproducible from sources on any machine.
- NO AGPL in the pipeline or requirements (swisseph/pyswisseph/drik-panchanga/
  PyJHora). A local swetest binary may serve as an OFFLINE validation oracle;
  it is never shipped, never imported, never in CI.
- No agent on the critical path. Template prose is committed source, reviewed.
- Pages are JS-free, static, fail-soft (a missed daily build leaves the
  newest dated page up with an honest banner — never blank, never wrong-date
  without saying so).
- Daily loop never commits build output (deploy publishes artifacts only).

## Content rules
- The written राशिफल is clearly labelled मनोरञ्जन/सांस्कृतिक with a short
  disclaimer (health/finance/legal decisions excluded) — better than the
  Nepali industry norm of no disclaimer.
- Prose register per reviews/04: 3–4 sentences, soft potential mood (-नेछ/
  -होला/-ला), rotate काम/स्वास्थ्य/प्रेम/आम्दानी/परिवार + one hedged caution.
- No ads, no tracking, free forever — stated on the page.
