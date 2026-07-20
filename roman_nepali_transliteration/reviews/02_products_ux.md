# Review 2: Products & UX (Opus 4.8 agent, 2026-07-20)

## Comparison of existing Roman→Devanagari transliteration products

| Product | Approach | Platform | Offline / client-side? | Candidate UX | Commit model | Key weaknesses |
|---|---|---|---|---|---|---|
| **Google Input Tools (web IME)** | Statistical/dictionary phonetic, fuzzy matching; Google backend | Web (embeds on any page), Chrome ext, Windows (discontinued) | No — needs Google's transliteration server | Dropdown of up to **5 candidates** under the active (underlined) word; fuzzy ("namaste"/"nemaste"→नमस्ते) | SPACE/ENTER = first candidate; click; **number key**; ↑↓ navigate + PgUp/PgDn; ENTER keeps literal English. **Backspace reopens the candidate window** | Server dependency (deprecated API, see below); desktop-oriented interaction; no first-party embeddable widget anymore |
| **Gboard Nepali (mobile)** | ML phonetic + native-script layouts | Android/iOS system keyboard | On-device models | Suggestion strip above keys shows Roman + Devanagari; tap to insert; "G"/arrow expands more | Tap word in strip; space auto-commits top | Must be installed & the Nepali layout enabled; not present on desktop or in a shared/kiosk browser |
| **SwiftKey** | Phonetic prediction | Android/iOS | On-device | Prediction bar, tap to select, arrow for more | Tap word | **Does NOT support Nepali transliteration** (12 Indic langs, Nepali excluded) |
| **easynepalityping.com** | **Wraps Google Input Tools API** | Web textarea | No (fails if Google unreachable → "reload browser") | On **space**, word converts; **backspace or click a word → candidate dropdown**; ↓ + Space to pick alt | Space/Enter commits; pipe/`.`→।; `Ctrl+.`→literal period | Server-dependent; whole-textarea model, not an inline field IME; candidate list is a click away, not always visible |
| **ashesh.com.np Nepali Unicode** | **Fixed rule-based scheme** (deterministic map) | Web | Yes — pure client-side JS, works offline | **No candidates** — one deterministic output | Live as-you-type | No disambiguation; user must learn escape rules: **`/` to split** wrong joins, **`\` for halant**, **`{...}` to keep English**, case-sensitive (ta=त vs Ta=ट) |
| **Hamro Nepali Keyboard** | Rule-based romanized + autosuggest | iOS/Android app | On-device | Real-time convert + autosuggest | Live | App install; `*`=anusvara `**`=chandrabindu conventions to memorize |
| **romantonepali / kokil / saral / merokalam etc.** | Rule-based scheme, "instant, no click" | Web | Mostly client-side | None (deterministic) | Live as-you-type | Same rigidity as ashesh; quality varies; no candidate correction |
| **Varnam / GoVarnam** | Scheme file + **greedy tokenizer + learning** (prefix tree, frequency-ranked) | C/Go lib, desktop & mobile IMEs, WASM-capable | Yes — fully local | Frequency-sorted suggestion list; **learns your words** to re-rank | IME-dependent | Nepali is not a first-class/mature scheme (Malayalam/Hindi lead); needs a bundled dictionary; integration effort |
| **Indic-Keyboard (SMC/Sabdakosh)** | Transliteration layout among 60 layouts, 23 langs | Android | On-device | Word prediction + transliteration | Tap | Android app only; not a web asset |
| **m17n / ibus (`ne-rom-translit`, Swanalekha)** | Rule-based `.mim` scheme, **one-to-many pattern maps with candidates** | Linux IME | Yes — local | Candidate list from pattern map | IME keys | Linux-only; `.mim` is a reusable *scheme source*, not a UI |

## Best-in-class interaction model: Google Input Tools (web IME)

This is the reference design and the one every Nepali web tool copies (easynepalityping literally proxies its backend). The interaction loop:

1. **Type Latin freely.** The in-progress word renders **inline in the field with an underline** marking it as "uncommitted/active." Nothing else on the page moves.
2. **Candidate window opens below the active word** as you type, showing **up to 5 ranked candidates**, numbered `1–5`. Ranking is statistical, and matching is **fuzzy** — misspellings still surface the intended word ("nemaste"→नमस्ते).
3. **Commit is multi-path, first-candidate-biased:**
   - **SPACE or ENTER** commits candidate #1 (the overwhelmingly common path — you rarely look at the list).
   - **Click** a candidate, or press its **number key**, to pick a non-default.
   - **↑/↓ (and PgUp/PgDn)** to browse, then Space/Enter on the highlighted one.
   - **ENTER on empty list / a special key** keeps the **literal Latin text** — the escape hatch for English words and proper nouns.
4. **Correction is via BACKSPACE:** backspacing into or right after a just-committed word **re-opens the candidate window** for that word, so a wrong auto-pick is a one-key undo, not a delete-and-retype. This is the single most important "fix a mistake" affordance.
5. **Next-word behavior:** each whitespace-delimited token is transliterated independently; committing one word starts a fresh active word. (Verified against the live backend: sending a whole phrase `mero naam ho` returns one best string `मेरो नाम हो`, while sending a single token `mero` returns the 5-candidate list `मेरो/मरो/मैरो/म्रो/मेरों` — so per-word requests are what yield the picker.)
6. **Never fails closed:** even pure gibberish (`xqzptv`) returns a char-by-char Devanagari string rather than an error or blank — the field always advances.

**Live technical verification (2026):** the backend `https://inputtools.google.com/request?text=<roman>&itc=ne-t-i0-und&num=5&ie=utf-8&oe=utf-8` is **still up and answering** despite the API being "deprecated" since 2011 (it backs Gboard). Response shape:
`["SUCCESS",[["mero",["मेरो","मरो","मैरो","म्रो","मेरों"],[],{"candidate_type":[0,0,0,0,0]}]]]`.
**Critically for a static GitHub Pages site:** the endpoint sends **no `Access-Control-Allow-Origin` header**, so a plain `fetch()` is CORS-blocked — but it **supports JSONP** via `&cb=fn` (returns `/*API*/fn([...])`), which is how every client-side wrapper (KSubedi's `transliteration-input-tools`, `google-input-tool`) reaches it without a server. That is the only client-side path to Google-quality candidates from a static host.

## UX requirements our tool should adopt / avoid

**Adopt (proven winners):**
- **First-candidate-on-space.** 95% of typing must require zero interaction with the candidate list — Space commits #1. The list is a fallback, not a gate.
- **Top-5 candidate list, ranked, with the intended word almost always at #1.** Use per-word requests (`num=5`) to get the picker; the phrase endpoint collapses to one answer.
- **Backspace-to-reopen as the primary correction gesture.** For tech-illiterate users this beats "select the word and choose from a menu." A wrong auto-pick should be recoverable without deleting characters.
- **Always-visible literal-English escape hatch.** Proper nouns, brand names, English words must be insertable verbatim (Google: ENTER/no-match; ashesh: `{...}` braces). Make this discoverable, not a memorized keystroke.
- **Never fail closed.** Unknown input still produces *something* Devanagari; never show an error or empty output mid-word.
- **Fuzzy matching** so users don't need correct romanization — the Google backend already does this; a rule-based fallback does not.
- **Copy-out as a one-tap primary action** with a **toast confirmation ("कपी भयो / Copied")**, 2–3s, `role="status" aria-live="polite"`. Copy is the user's actual goal (paste elsewhere / search), so the Copy button should be the most prominent control, not buried.
- **Mobile touch targets ≥48dp (Android) / 44pt (iOS), generously spaced.** Candidate chips must be large, finger-sized, and separated so mis-taps don't pick the wrong word or dismiss the list.
- **Render candidates ABOVE the input / current line** on mobile — where Gboard's strip lives and where fingers don't occlude them (no hover exists on touch).

**Avoid (observed failure modes):**
- **Do not ship a pure fixed rule-based scheme as the only engine** (ashesh/romantonepali model). It forces users to memorize escape syntax (`/`, `\`, `{}`, case sensitivity ta/Ta) and gives no way to fix a plausible-but-wrong conversion — fatal for tech-illiterate users. Rule-based is acceptable only as an *offline fallback*.
- **Do not hide candidates behind a click/second gesture as the norm** (easynepalityping requires backspace/click just to *see* alternatives). If the tool guesses wrong, alternatives should be one glance/one tap away.
- **Do not assume a physical keyboard.** KSubedi's client is explicitly *not mobile-compatible* because "there is no reliable way to handle text input events through virtual keyboards on phones" — mobile IMEs (autocorrect, composition events, predictive text) fight a JS transliterator. **Design mobile-first with a controlled input**, test against Gboard/iOS autocorrect interference, and consider a `contenteditable`/token-chip model rather than intercepting keystrokes in a raw `<input>`.
- **Do not depend silently on the network.** The Google backend is deprecated and could vanish; and it's blocked offline. Degrade gracefully to a bundled rule-based engine, and never leave the user staring at a dead field (easynepalityping's "reload the browser" is a bad fallback).
- **Don't require layout/mode toggles or symbol memorization** (`*`/`**`, pipe-for-purnabiram) as the primary path — surface those as optional helpers.
- **Don't over-rely on Gboard as "they already have it."** On Android with the Nepali layout enabled, a web IME is redundant — but **SwiftKey doesn't support Nepali at all**, iOS/desktop/shared-browser users often lack it, and many users never configure their keyboard. The web tool's job is to **complement** (work for the unconfigured majority and on desktop), so it must stand alone without assuming a system IME.

## The 3 most load-bearing findings

1. **The Google Input Tools backend is still live in 2026 and is the only route to "smart" top-5 candidates from a static site — but only via JSONP, not `fetch()`.** Verified: `inputtools.google.com/request?...&itc=ne-t-i0-und&num=5` returns ranked Nepali candidates, sends **no CORS header** (so `fetch` fails), but honors `&cb=` JSONP. This single fact determines the whole architecture: Google-quality client-side IME on GitHub Pages is feasible via script-tag JSONP, but it is **network-dependent and rests on a deprecated service** — so pair it with a bundled offline rule-based fallback.

2. **The winning correction model is "commit #1 on space, fix with backspace-to-reopen" — not a menu.** Google's dominance and the failure of rule-based converters both point here: for tech-illiterate, touch-first users, the intended word must be #1 and committing must be automatic, while fixing a wrong guess must be a single backspace that re-shows the 5 candidates. Copy-out (with a toast) is the actual end goal and should be the most prominent action on screen.

3. **Mobile is the hard part, and existing web IMEs punt on it.** The most-cited client-side library refuses mobile outright because virtual keyboards' composition/autocorrect events break keystroke interception. Because the product is mobile-first and Gboard/SwiftKey coverage is inconsistent (SwiftKey has no Nepali at all), the tool must be engineered around virtual-keyboard quirks from day one — large touch targets, candidates rendered above the field, and an input model (token chips / controlled contenteditable) that coexists with mobile autocorrect rather than fighting it.
