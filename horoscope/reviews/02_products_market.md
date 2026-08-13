# Review 2: Products & market (agent review, 2026-07-21)

## Product comparison table

| Product | Type / origin | Rashifal cadence | Computed panchanga? | Content authorship | Bundled with | Monetization |
|---|---|---|---|---|---|---|
| **Hamro Patro** (hamropatro.com + app) | Nepali super-app, est. 2010 | Daily / weekly / monthly / yearly | Basic (tithi/panchang in calendar), not the focus | **No byline** on free rashifal; separate paid jyotish marketplace | Calendar, news, radio, podcasts, gold/forex, remit, pay, health, kundali | Ads (dominant) + premium ad-removal sub + astrologer consults + telehealth + e-commerce |
| **Ashesh.com.np** | Nepali web-tools dev (Ashesh Shrestha) | Daily (per-sign) | Panchang widget offered separately | No astrologer credit; "based on Vedic/Chandra sign" | Sold as **embeddable widgets** (calendar, rashifal, panchang, forex, gold) | Free-with-attribution; drives traffic to Smart Patro app |
| **Nepali Patro** (nepalipatro.com.np) | Nepali calendar site | Daily (also /nepali-rashifal/daily) | Panchanga section | No visible byline | Calendar, events, festivals, panchanga, date convert | Ads |
| **Ratopati / Onlinekhabar / Kantipur** (news portals) | Nepali news | Daily column | No | No per-day byline; OK says "from renowned astrologers" | News site section | Display ads on portal |
| **Ramro Patro, Chautari Hub, Nepal Jyotish, merotool, etc.** | Smaller Nepali sites | Daily/weekly/monthly/yearly | Some panchanga | None credited | Calendar/tools | Ads |
| **Drik Panchang** (drikpanchang.com) | Indian, reference-grade panchanga | Daily written rashifal (secondary) | **Yes — the reference implementation** | Written predictions; panchanga fully computed | Muhurat, calendars (many regions), festivals, jyotish calculators | Ads + app |
| **AstroSage** (incl. astrosage.com/nepali) | Indian, localized to Nepali | Daily per-sign | Yes (kundli/panchang engine) | Template/engine-driven + "AI astrology" | Kundli, matching, consult marketplace | Consult wallet, reports, ads |
| **GaneshaSpeaks** | Indian (est. 2003, Bejan Daruwalla) | Daily | Yes | Astrologer marketplace | Kundli, tarot, numerology | First chat free → wallet recharge; 50M+ consults / 180 countries |

## Hamro Patro — detailed notes

The dominant player by a wide margin. Founded 2010 by Shankar Uprety (built in the US to track the Bikram Sambat calendar for the diaspora), it is "Nepal's most-downloaded app": ~15M+ downloads over 12 years (~20M on Android per Play listing), and ~1.8M (18 lakh) daily active users; ~70% of users in Nepal, the rest diaspora. It employs ~100 people directly, ~300 including the astrologers and medical professionals on its platforms.
- Sources: [Rest of World](https://restofworld.org/2023/3-minutes-with-shankar-uprety/), [Kathmandu Post](https://kathmandupost.com/science-technology/2019/05/05/hamro-patro-is-one-of-the-most-downloaded-nepali-apps-heres-its-story), [nepalitelecom.com](https://www.nepalitelecom.com/hamro-patro), [Wikipedia](https://en.wikipedia.org/wiki/Hamro_Patro).

**Rashifal offering** ([hamropatro.com/rashifal](https://www.hamropatro.com/rashifal)): daily, weekly, monthly, and yearly, in Nepali and English ([english.hamropatro.com/rashifal](https://english.hamropatro.com/rashifal)). Each of the 12 signs is a clickable card with English + Nepali name, the sign's **name-initial syllables** (नाम अक्षर, for users who pick by the first letter of their name rather than birth chart), a prediction paragraph, and a lucky color + lucky number. **Critically, there is no astrologer byline or source credit on the free rashifal** — the predictions are published anonymously as house content.

**Jyotish Sewa is a separate, paid product** ([hamropatro.com/jyotish](https://www.hamropatro.com/jyotish)): live audio/video consultations with "verified" Nepali Vedic astrologers and Vastu experts, plus kundali (birth-chart) generation. So Hamro Patro splits the free mass-market daily rashifal (a traffic/habit hook) from the monetized 1:1 astrologer marketplace.

**Bundle & monetization:** ~25 services — BS↔AD calendar, news, radio, podcasts, gold/silver + forex rates, mobile recharge, remittance, telehealth, an upcoming Hamro Pay wallet, e-commerce/gifts. Ad-supported (majority of revenue from Facebook/Google ads plus news-page ads), with subscriptions removing ads: **Premium Rs 299/mo or Rs 3,000/yr; Premium Plus Rs 599/mo or Rs 6,000/yr**. Additional revenue from astrology consults, telehealth appointment fees, e-commerce, and remittance.

## Drik Panchang — detailed notes

The reference implementation of **computed** panchanga (India-focused but the model everyone copies). Its daily page ([drikpanchang.com](https://www.drikpanchang.com/)) is location-aware and shows the classic five-limb panchang plus derived timings, all deterministically calculated:
- **Computed:** Tithi, Nakshatra, Yoga, Karana (with exact end-times), sunrise/sunset, paksha, weekday, month in both Amanta and Purnimanta systems, moonsign/sunsign transitions; plus Rahu Kala, Choghadiya (8-part day divisions), Muhurat windows, and a Lagna Kundali with planetary positions.
- **Written (not computed):** the "Rashifal for Today" per-sign predictions are prose interpretations, secondary to the panchang.
- Navigation: Panchang (many regional formats), Calendars, Muhurat, Vrat & Upavas, Festivals, Jyotish calculators, Planets, Lyrics, Gallery.

The key architectural lesson: a mature horoscope product is two distinct layers — a **computed** layer (panchanga, muhurat, choghadiya, kundali; pure date/astronomy math, evergreen, no human) and a **written** layer (the daily sign predictions; human/template/AI-authored, requires a daily pipeline). AstroSage and GaneshaSpeaks add a third layer: a **paid astrologer marketplace** (kundli reports, per-minute chat/call — GaneshaSpeaks reports 50M+ consultations across 180 countries; first chat free then wallet recharge).

## Content-sourcing findings

This is the most important market signal for our purposes.
- **The Nepali daily-prediction text is overwhelmingly re-syndicated, not originally authored.** Hamro Patro is the de-facto source of truth, and a whole ecosystem of unofficial scrapers/APIs pulls the rashifal text straight off hamropatro.com: [prabincankod/rashifal-api](https://github.com/prabincankod/rashifal-api) ("scrapes rashifal on every request"), [mrjudiyt/np-rashifal.api](https://github.com/mrjudiyt/np-rashifal.api), [milancodess/hamro-patro-scraper](https://github.com/milancodess/hamro-patro-scraper), [ankurgajurel/rashifal-api](https://github.com/ankurgajurel/rashifal-api). Many small Nepali sites/apps therefore display Hamro Patro's predictions.
- **Ashesh.com.np is the other syndication rail** — official free embeddable widgets (iframe + JS, customizable width/height/header color) for rashifal, calendar, panchang, forex, and gold, explicitly meant for "blogs, news portals, or personal websites," monetized only by a required attribution backlink ([ashesh.com.np/rashifal](https://www.ashesh.com.np/rashifal/), [widget page](https://www.ashesh.com.np/nepali-calendar/widget/)). So a large share of Nepali sites don't author rashifal at all — they embed Ashesh's widget or scrape Hamro Patro.
- **No authoritative single author to emulate.** Almost no Nepali site publishes a bylined daily astrologer. News portals (Ratopati /rashifal, Onlinekhabar /rashifal — "from renowned astrologers," ekantipur) run daily columns with no visible per-day byline, implying in-house/agency/syndicated copy. Named jyotishi columnists exist in print (a Devmani Basyal / देवमणि बस्याल surfaced, weakly sourced), but the online norm is anonymous.
- **AI-generation is the rising pattern.** The global astrology-app market is ~USD 3–4B (2024) heading to ~USD 9B by 2030; India's ~USD 163M (2024) → ~USD 1.8B (2030), and vendors (AstroSage "AI Astrology," Om.AI, Astroficial) now market chart-specific AI predictions rather than mass sun-sign text ([astrosage.com](https://www.astrosage.com/), [developerbazaar list](https://developerbazaar.com/10-best-ai-powered-astrology-apps/)). Template/rule-generated → increasingly agent-generated is the trajectory for the written layer.

## Demand evidence

- **Rashifal is a habitual, top-tier query in Nepal.** "आजको राशिफल / aajako rashifal" is one of the most consistently searched Nepali terms; it anchors the traffic of Hamro Patro (1.8M DAU) and news portals. Onlinekhabar is reportedly Nepal's #1 searched keyword (~158K/day), and every major portal runs a permanent rashifal section — a signal it reliably drives return visits ([tech4nepal](https://www.tech4nepal.com/5-most-searched-keywords-in-nepal/)). (Google Trends itself was not directly reachable for a numeric series.)
- **Audio/video rashifal is a huge Nepali format.** YouTube is saturated with daily per-sign spoken rashifal videos (mesh→meen), posted every single day by many channels, plus radio rashifal — a distinctly Nepali consumption mode beyond text ([YouTube playlist](https://www.youtube.com/playlist?list=PL3LfckLlEvw30q2a2iNqzF_Kr5AjXFXxe)). This is the "listen, don't read" audience.
- **Diaspora demand is structural, not incidental.** Hamro Patro was literally built for expatriates to stay tied to the BS calendar and festivals; ~30% of its base is diaspora — the same audience a public-domain Nepali archive serves.

## UX patterns

- **Rashifal is rarely standalone — it lives inside a "patro" (calendar) context.** The sticky daily loop is calendar + rashifal + gold/forex + news in one app opened every morning; rashifal is the return hook, the BS calendar is the utility anchor. That bundling is what makes Hamro Patro's presentation sticky.
- **12-sign grid/list of cards.** Standard anatomy: a grid or vertical list of the 12 rashi (Mesh, Brish, Mithun, Karkat, Singha, Kanya, Tula, Brischik, Dhanu, Makar, Kumbha, Meen), tap a sign → prediction paragraph + **lucky color + lucky number**.
- **Name-initial (नाम अक्षर) table.** A distinctly South-Asian affordance: each sign lists the Nepali syllables a person's name might start with, so users who don't know their moon-sign self-select by the first letter of their name. Worth replicating for accessibility.
- **Timeframe tabs:** daily / weekly / monthly / yearly, all on one surface.
- **Nepali BS date header** at top (e.g. "०५ साउन २०८३ मंगलवार"); a trailing muted date colophon is common.
- **Computed panchang block** (Drik Panchang model): tithi/nakshatra/yoga/karana + sunrise/sunset + rahu kaal + choghadiya + muhurat — the evergreen, no-human, static-friendly layer.
- **Audio option** is expected by a large slice of the audience (radio/YouTube norm).

## Monetization patterns in the niche (for awareness only — our site stays free/no-ads)

Layered: (1) display ads on the free daily rashifal (the traffic magnet); (2) premium ad-removal subscriptions; (3) the real money — a **paid astrologer marketplace** (per-minute chat/call, wallet recharge, à la Jyotish Sewa / GaneshaSpeaks / AstroSage); (4) kundli/report sales; (5) cross-sell into remittance, telehealth, e-commerce. Free daily rashifal is uniformly a loss-leader funnel toward consultations.

## The 3 most load-bearing findings

1. **The written daily prediction is a re-syndicated commodity, not original work.** In Nepal it is overwhelmingly Hamro Patro's anonymous text, redistributed via scrapers ([rashifal-api repos](https://github.com/prabincankod/rashifal-api)) and via Ashesh's free embeddable widget. There is no bylined authority to emulate, and the trend is toward AI-generated copy. Any daily-prediction feature would mean either licensing/embedding a feed, scraping (rights/quality risk), or generating our own — none of which is a "preserve public-domain literature" activity, and each needs a daily content pipeline the current source-only, CI-rebuilt static architecture doesn't have.

2. **The computed panchanga layer is the part that actually fits a free, no-ads, static archive.** Panchang/tithi/nakshatra/muhurat/choghadiya (the Drik Panchang model) is deterministic date-and-astronomy math — evergreen, no daily human, no third-party content rights, buildable at page-render time. If the archive wants a genuine differentiated, defensible utility, the computed layer is it; the daily written predictions are the commodity/liability part.

3. **Demand is real, daily, and diaspora-heavy — but the category is saturated and monetization-funnel-shaped.** Rashifal reliably drives return traffic (it is why Hamro Patro and every portal run it) and the diaspora overlap with the archive's audience is strong. The strategic value for our site is purely as a daily-return hook bundled with a Nepali calendar — with the clear caveat that the market norm (unattributed, re-syndicated, increasingly AI-written predictions, consultation upsell) sits in tension with a faithful-preservation, free, no-ads mission.
