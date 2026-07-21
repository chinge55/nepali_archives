# Review 5: Daily content on the static architecture (Opus 4.8 agent, 2026-07-21)

Facet: how daily-changing content fits this repo's static/GitHub-Pages/JS-frugal architecture. Grounded in the actual pipeline (`.github/workflows/deploy.yml`, `pipeline/build_site.py`) and the existing `/type/` tool precedent.

## The decisive architectural fact for THIS repo

`deploy.yml` already **computes every derived byte at build time from sources and publishes `site/` as a Pages artifact via `actions/deploy-pages@v4` — it never commits build output** (the repo is "source-only" by charter, CLAUDE.md). That single fact settles the "daily commit vs no commit" question: **a scheduled run of the existing build produces a fresh page with ZERO repo commits.** "Today" is just the build machine's clock at run time. No bot-commit history pollution is required — the daily change lives only in the deployed artifact, exactly like `reader.html` or `index.json` do today.

The only thing that *can't* be conjured from the clock is **daily prose** (an LLM step). Prose generated fresh at build time and never stored is ephemeral and non-reproducible — which collides head-on with the archive's identity (permanent, reproducible sources). That tension, not the astro math, is what picks the architecture.

## Three regeneration architectures compared

| | A. Daily CI rebuild | B. Precompute-ahead (committed source) | C. Client-side compute |
|---|---|---|---|
| **How** | `schedule:` cron triggers the build; build reads system date + ephemeris, renders today | Build renders N dated pages from a committed content source; `/rashifal/` points at today | Ship a JS ephemeris + templates; browser computes today |
| **Daily commit?** | No | No (periodic content top-ups only, human-reviewed) | No |
| **Depends on cron?** | Yes — every day | Only for repointing "today" (degrades gracefully) | No |
| **JS on the page?** | None (server-rendered) | None (server-rendered) | Heavy — ephemeris libs on the landing page |
| **SEO (static HTML text)** | Strong | Strong | Weak (JS-rendered, no static text) |
| **Archive persistence** | None unless dated pages also kept | Native — dated pages ARE the archive | None (nothing stored) |
| **Reproducible / mission-coherent** | Only if prose is deterministic/templated | Yes — content is a committed source like `text.txt` | Prose must be template-only |
| **Fresh LLM prose possible?** | Yes (build-time), but ephemeral | Yes, in batches (monthly), archived | No (templates only) |
| **Failure blast radius** | Cron miss → stale/blank today | Cron miss → yesterday's *real* page persists | None, but a JS bug blanks the page for everyone |

**Recommendation for this repo: B as the substrate + a thin A on top.**

Concretely:
1. **Treat the rashifal corpus as archived source, not ephemeral output.** Panchanga (tithi/nakshatra/yoga/karana/vaar) is deterministic given date+location, so it can be precomputed arbitrarily far ahead. The prose is authored/LLM-generated in **batches (e.g. a month at a time), reviewed, and committed** as a source file per date — the same discipline the archive already applies to `text.txt`. This makes the daily content *reproducible and permanent*, which is the whole point of the site, and sidesteps "an LLM can't precompute a year of fresh-feeling prose": you top up monthly, which is fresh enough for horoscope prose and requires no daily automation.
2. **Build dated archive pages** `/rashifal/YYYY-MM-DD/` for every date that has a source → a persistent राशिफल archive, which *fits the site's archival identity* and costs trivial storage.
3. **`/rashifal/` (canonical "today") is produced by a light daily scheduled build** that reads the machine clock and renders today's dated content into the `/rashifal/` index (canonical link + `dateModified`). No commit; the cron only re-deploys. If today's source is missing, the build falls back to the most recent available dated page with an honest "पुरानो" banner — never blank.

This keeps **every reading page JS-free** (matching the `/type/` precedent where JS loads *only* on its own page), keeps **git history clean** (no daily bot commits — content arrives in reviewed monthly batches), and makes **cron failure a soft failure** (yesterday's page is a real, committed, deployed page that simply stays up).

Reject **C**: a browser ephemeris is exactly the kind of heavy client-side JS the archive avoids, it produces no server-rendered text for search engines, and it stores nothing — the opposite of an archive. Reject **pure A** (fresh LLM prose at build time, nothing stored): simplest to wire, but ephemeral and non-reproducible, violating the cardinal preserve-don't-rewrite ethos.

*(Licensing note bordering the computation facet: if precomputing panchanga, prefer an MIT-licensed engine — `skyfield` + public-domain JPL ephemeris, or `astronomy-engine` — over Swiss Ephemeris, which is dual AGPL-3.0/commercial and would sit awkwardly beside the "clean licenses" constraint even though build-time use producing static data is defensible.)*

## Cron / NPT timing analysis

**NPT = UTC+5:45, no DST** ([Nepal Standard Time, Wikipedia](https://en.wikipedia.org/wiki/Nepal_Standard_Time)). GitHub cron is UTC-only.

Two date boundaries matter, and they differ:
- **Civil Nepali date (गते)** rolls at **midnight NPT = 18:15 UTC** the previous day.
- **Panchanga tithi/nakshatra are reckoned from local sunrise** ([ashesh.com.np/panchang](https://www.ashesh.com.np/panchang/), [nepcalendar.com/today](https://nepcalendar.com/today/)). Kathmandu sunrise ranges roughly 05:00–06:20 NPT across the year. So the panchanga values "for today" are only settled *after* the latest possible sunrise.

To have both the civil date and the sunrise-based panchanga correct, **rebuild after the latest yearly Kathmandu sunrise, ~06:30 NPT = 00:45 UTC.**

But GitHub explicitly warns scheduled runs are **delayed during high load, commonly 5–30 min, occasionally dropped**, and the top-of-hour and `:00/:30` minutes are the congested waves ([community #156282](https://github.com/orgs/community/discussions/156282), [community #52477](https://github.com/orgs/community/discussions/52477), [cronpreview](https://cronpreview.com/guides/github-actions-cron-in-production), [Predicting GitHub Cron Delays](https://lowlysre.substack.com/p/predicting-github-cron-delays)). Mitigations, applied:

```yaml
on:
  schedule:
    - cron: "7 1 * * *"    # ~06:52 NPT — after sunrise year-round, off-peak minute
    - cron: "37 1 * * *"   # ~07:22 NPT — second attempt, belt-and-suspenders
  workflow_dispatch: {}     # manual re-trigger
  push: { branches: [main] }
```
- **Odd, off-peak minute (`:07`, `:37`)** dodges the `:00` congestion wave.
- **Two crons ~30 min apart** absorb a dropped/delayed run; the existing `concurrency: {group: pages, cancel-in-progress: true}` safely coalesces them (builds take minutes, so they rarely overlap; if they do, the later wins — identical output).
- **`workflow_dispatch` already present** in `deploy.yml` — keep it for manual recovery.
- **60-day inactivity auto-disable** of scheduled workflows ([cronpreview](https://cronpreview.com/guides/github-actions-cron-in-production), [community #194300](https://github.com/orgs/community/discussions/194300)) is **not a live risk here** — this repo commits regularly — but if the archive ever goes quiet, the daily cron would silently stop after 60 days. The graceful-fallback design (yesterday's committed page persists) means even that fails soft.
- **Minimum interval is 5 min** and sub-5-min crons are silently ignored — irrelevant for daily, noted for completeness.

For **public repos, GitHub-hosted Actions minutes are free/unlimited**, so a daily full-pipeline rebuild (pandoc + pagefind + font subset, a few minutes) is not a cost concern.

## URL design + SEO

**URLs** (matches the site's trailing-slash directory convention):
- `/rashifal/` — canonical **today** (rebuilt daily; `<link rel="canonical">` to itself).
- `/rashifal/YYYY-MM-DD/` (Bikram Sambat, e.g. `/rashifal/2083-04-05/`) — persistent dated archive pages.
- `/rashifal/mesh/`, `.../brish/` … — optional per-sign evergreen pages (long-tail SEO + the natural "my sign" landing).
- Consider labelling the section **पात्रो/पञ्चाङ्ग** rather than राशिफल (identity, below).

**Freshness signals on static hosting** (Google uses `dateModified` as a freshness signal; put dates in title/H1/URL and ISO-8601 in schema — [Google Article structured data](https://developers.google.com/search/docs/appearance/structured-data/article), [Search Engine Land: byline dates](https://searchengineland.com/guide/byline-dates)):
- Date in `<title>`, `<h1>`, and the URL.
- **JSON-LD `Article`/`NewsArticle`** with `datePublished` + `dateModified` in ISO-8601 *with the +05:45 offset* (there is no schema.org "Horoscope" type; `Article` is the honest fit). The repo already emits per-work JSON-LD via `page(..., extra_head=...)` — reuse that hook.
- **Add `lastmod`.** The current sitemap is a plain `sitemap.txt` URL list with **no `lastmod`**. For daily pages, emit an **XML sitemap (or a dedicated `sitemap-rashifal.xml`) carrying `<lastmod>`** so crawlers see the daily change; add `/rashifal/` and recent dated pages to the sitemap list.
- **GitHub Pages caps `Cache-Control: max-age=600` (10 min)** and it's not user-configurable ([community #11884](https://github.com/orgs/community/discussions/11884), [caching GitHub Pages](https://mrmarble.dev/blog/caching-github-pages/)). For once-a-day content this is *ideal* — a fresh deploy is globally visible within ~10 minutes, no staleness worries.
- Warn against the known **CTR trap**: don't let dates thrash — set `dateModified` to the content's target date, not "now on every rebuild" ([Search Engine Land: date-updated CTR](https://searchengineland.com/date-published-date-updated-organic-ctr-453209)).

**Realistic competitive assessment:** the head terms **"आजको राशिफल" / "aajako rashifal" are owned by high-authority patro portals** — [Hamro Patro](https://www.hamropatro.com/rashifal), [Nepali Patro](https://nepalipatro.com.np/nepali-rashifal), [Ramro Patro](https://ramropatro.com/rashifal), [AstroSage](https://www.astrosage.com/nepali/rashifal/), [rat32](https://nepalicalendar.rat32.com/rashifal/) — backed by apps, years of backlinks, and daily updates. **Outranking Hamro Patro on the head term short-term is not realistic**, and chasing it would push the site toward content-farm tactics that clash with its mission. The honest opportunity is the **long tail and a differentiated angle**: per-sign pages, dated-archive pages ("राशिफल <date>"), and the archive's unique framing (heritage panchanga + public-domain jyotisha), plus the genuine differentiator these portals can't match — **no ads, no tracking, free forever.** Treat SEO as a bonus, not the goal.

News-portal page structure to mirror (all twelve signs on one page with anchor links, prominent H1 + date, an "updated" timestamp, and weekly/monthly/yearly variants) is worth copying structurally; skip their ad-driven bloat.

## Integration & mission-coherence

- **Nav precedent:** `/type/` was added as the archive's first "tool" page, sitting in a 4-item nav (`गृह · लेखकहरू · टाइप · बारेमा`) and loading JS only on its own page. A rashifal/patro item is the natural 5th entry, following the same pattern (JS-free reading page).
- **Identity risk is real** — a literature archive sprouting a daily horoscope reads like a traffic play and can dilute the brand. **The counter-argument is also real and I'd lean on it:** the Nepali **पात्रो and classical ज्योतिष are heritage**, and the archive already holds/collects public-domain texts. **Frame the feature as पञ्चाङ्ग/पात्रो heritage, not clickbait horoscope:** present the panchanga (tithi/nakshatra/vaar) as cultural-calendar data, with the rashifal as a derived reading, ideally cross-linked to public-domain jyotisha sources in the corpus. Labelling the nav item **पात्रो/पञ्चाङ्ग** (with राशिफल as a section within) foregrounds the calendar-heritage angle and de-emphasizes the fortune-telling framing.
- **Main domain vs subdomain:** a subdomain (`patro.nepaliarchives.org`) cleanly quarantines both the identity risk and any SEO/spam blowback from the literary corpus, but it fragments domain authority and doubles ops (separate Pages target/CNAME; the build currently emits a single `CNAME` = `www.nepaliarchives.org`). **Recommendation: keep it on the main domain under `/patro/` (or `/rashifal/`) with explicit heritage framing and a disclaimer** — the archive is small and mission-driven, and the heritage framing resolves most of the dilution concern. Hold the subdomain as the clean hedge if leadership judges the risk too high.
- **Footer/disclaimer:** the shared footer already carries "सार्वजनिक डोमेन." Add a **rashifal-specific disclaimer** (cultural/entertainment interest; computed from panchanga; not professional advice) on the section pages, and lean into the **no-ads/no-tracking** promise as a visible differentiator from the ad-heavy incumbents.

## Failure-mode design

- **Daily generation/cron fails →** because the substrate is committed dated pages, `/rashifal/` **falls back at build time to the most recent available dated page**, shown with an honest "यो <date> को राशिफल हो" / "पुरानो" banner. Never a blank page, never a 500.
- **No content at all for a date range →** last-resort **evergreen per-sign readings** (generic, date-agnostic) so the section is never empty.
- **The silent-staleness trap** (cron "succeeds" but serves yesterday's content) is the classic cron-built-page failure. Mitigate with **self-evidencing pages + an external dead-man's-switch**:
  - The page **prints its own target date** in visible text *and* in JSON-LD `dateModified`, so staleness is human-visible (and, given the 10-min Pages cache, quickly so).
  - Wire a **cron-monitor dead-man's-switch** — the workflow pings [Healthchecks.io](https://healthchecks.io/) / Cronitor at the end of a successful run; if the daily check-in doesn't arrive, you get alerted that the cron dropped ([monitoring GitHub scheduled workflows](https://cronjobpro.com/guides/monitor-github-actions-scheduled-workflows)). This is the recommended pattern precisely because GitHub gives *no* alert on a dropped scheduled run.
  - A **build-time assertion** fails the run loudly if today has neither content nor a valid fallback.

## The 3 most load-bearing findings

1. **No daily commit is needed — and shouldn't be used.** `deploy.yml` already builds `site/` in-workflow and publishes via `actions/deploy-pages@v4` with no repo commit, so a scheduled build regenerates "today" for free with a clean git history. The right model is **precompute panchanga (deterministic) + commit LLM prose in reviewed monthly batches as archive source, with a thin daily cron only re-pointing `/rashifal/` at today** — reproducible, permanent, JS-free, and mission-coherent, instead of ephemeral build-time prose.

2. **GitHub cron is unreliable-by-design, so the architecture must fail soft, not the cron be trusted.** Runs are commonly delayed 5–30 min and occasionally dropped. Target **~00:45–01:37 UTC (after Kathmandu's latest sunrise ≈06:30 NPT, since panchanga is sunrise-reckoned), at off-peak odd minutes, with two crons + `workflow_dispatch` + a Healthchecks.io dead-man's-switch** — and lean on committed dated pages so a missed run just leaves yesterday's real page up. The 10-min Pages cache makes daily freshness a non-issue.

3. **Compete on identity, not on the head keyword.** "आजको राशिफल" is locked up by Hamro Patro and peer patro portals with overwhelming authority; outranking them is unrealistic and chasing it corrodes the archive's mission. Win instead with **static server-rendered text + `Article` JSON-LD (`datePublished`/`dateModified` at +05:45) + a `lastmod` XML sitemap** for freshness, a **persistent dated राशिफल archive** (which fits the site's archival identity), a **पात्रो/पञ्चाङ्ग heritage framing** (with disclaimer) that keeps the literature archive coherent, and the honest differentiator the incumbents can't offer — **no ads, no tracking, free forever.**
