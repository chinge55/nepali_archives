---
name: verify-site-change
description: >-
  Build the site locally and verify a change in a real (headless) browser —
  screenshots, search queries, rendering checks. Use after editing
  build_site.py/stats.py/search JS, or to eyeball how a work renders before
  shipping. Encodes the proven local build + headless-chromium recipe.
---

# Verify a site change locally (build + headless browser)

## 1. Build (order matters)

```bash
python3 pipeline/build_index.py
python3 pipeline/build_formats.py <dir>     # only if a work's text changed; NOT --all needed locally
python3 pipeline/build_site.py              # rmtree's site/ — always rerun pagefind after
python3 pipeline/subset_fonts.py            # only if glyphs may have changed; then build_site again
npx -y pagefind --site site                 # else in-text search 404s locally
```

Subset of that is fine when scope is narrow (text-only change → index, formats for
that dir, build_site). `build_site` wipes `site/`, so anything written into `site/`
(pagefind) must rerun after the LAST build_site pass.

## 2. Serve

```bash
cd site && python3 -m http.server <port> &   # pick a fresh port (8137/8141/… were used)
curl -sI http://localhost:<port>/ | head -1   # confirm 200 before driving a browser
```

## 3. Headless browser

A chromium lives in the puppeteer cache (`~/.cache/puppeteer/chrome/...`,
installed 2026-07-20; the old ms-playwright cache is GONE). Recipe:

```bash
mkdir -p /tmp/sitetest && cd /tmp/sitetest && npm i puppeteer@21   # reuses the cached chromium
# if the cache is ever missing, this npm i re-downloads it (~10 min)
```

```js
const puppeteer = require('puppeteer');
const b = await puppeteer.launch({headless: 'new', args: ['--no-sandbox']});
const p = await b.newPage();
p.on('pageerror', e => console.log('PAGEERROR', e.message));   // always capture
await p.goto('http://localhost:<port>/…', {waitUntil: 'networkidle2'});
// drive: p.$eval('#q', (el,v)=>{el.value=v; el.dispatchEvent(new Event('input',{bubbles:true}));}, 'query')
// settle: await new Promise(r=>setTimeout(r, 2000));   // debounced search needs ~2s
await p.screenshot({path: 'shot.png', fullPage: true});
```

Read the screenshot with the Read tool and actually LOOK at it. Test the failure
modes that bit before: dynamic `import()` needs absolute/`./` URLs (bare specifiers
throw silently inside .catch); search results need the debounce delay; check both a
Devanagari and a roman query when touching search.

## 4. Checks that matter per change type

- **Work rendering**: headings are `<h2 class="sec">` (not verse), stanza numbers on
  own lines, no page furniture, colophon muted, pagination didn't trigger/break.
- **Search**: tier-1 titles instant; tier-2 "पाठभित्र खोजी" excerpts appear; result
  click lands + highlights (`?pagefind-highlight=`).
- **Stats**: all section `<h2>`s present, counts match `archives/index.json`.
- **Sweep**: `build_site` page count printed at build didn't move unexpectedly.

Kill the server when done. Then use the `ship` skill.
