#!/usr/bin/env python3
"""
kavitakosh_crawl.py — discover & download a Kavita Kosh work tree.

Kavita Kosh (a MediaWiki site) stores each poem's verse in <div class="poem">.
A "work" may be a single such page, or an *index* page (a collection/महाकाव्य/
खण्डकाव्य) that has no div.poem but links to its constituent poems or cantos.

Given seed URLs, this crawls breadth-first: it fetches each page (caching the
raw HTML to disk), classifies it as LEAF (has verse) or INDEX (links to parts),
and for INDEX pages enqueues the child links whose title shares the work's
prefix. It writes a JSON tree describing what was found. It downloads only;
extraction/assembly is a separate step (kavitakosh_build.py).

Politeness: 1s between network fetches; cached pages are never re-fetched.

Usage:
    python pipeline/kavitakosh_crawl.py --seeds /tmp/kk/seeds.json --out /tmp/kk
"""
import argparse, hashlib, json, re, sys, time
from pathlib import Path
from urllib.parse import urljoin, unquote, urlparse
from urllib.request import urlopen, Request

BASE = "https://kavitakosh.org"
UA = "Mozilla/5.0 (NepaliArchives/1.0; +archival; contact sangam)"
DEV = re.compile(r"[ऀ-ॿ]")

def devcount(s): return len(DEV.findall(s))

def cache_path(cache_dir: Path, url: str) -> Path:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{h}.html"

def fetch(url: str, cache_dir: Path, delay=1.0) -> str:
    p = cache_path(cache_dir, url)
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace")
    time.sleep(delay)
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8", errors="replace")
    p.write_text(raw, encoding="utf-8")
    return raw

def norm_title(t: str) -> str:
    # strip trailing " / author", whitespace, trailing dot
    t = re.sub(r"\s*/\s*लक्ष्मीप्रसाद देवकोटा\s*$", "", t).strip()
    return t.strip(" .।")

# Navigation / portal links that appear in content but are NOT works.
NAV_TITLES = {
    "हिन्दी/उर्दू", "अंगिका", "अवधी", "गुजराती", "नेपाली", "भोजपुरी",
    "मैथिली", "राजस्थानी", "हरियाणवी", "अन्य भाषाएँ",
    "लक्ष्मीप्रसाद देवकोटा", "रचनाकारों की सूची", "कविता कोश में भाषाएँ",
}
def is_nav(title: str) -> bool:
    t = title.strip()
    return (t in NAV_TITLES or t.endswith("/ परिचय") or "परिचय" in t
            or "रचनाकार" in t or "भाषाएँ" in t or "सूची" in t)

def classify(html: str):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    c = soup.select_one("#mw-content-text") or soup
    poems = [p for p in c.select("div.poem") if devcount(p.get_text()) > 60]
    title = ""
    h1 = soup.select_one("h1")
    if h1: title = h1.get_text(strip=True)
    if poems:
        return "leaf", title, []
    # INDEX: gather child work links inside the main content
    children = []
    seen = set()
    for a in c.select('a[href^="/kk/"]'):
        href = a.get("href", "")
        if "redlink" in href or "action=edit" in href or "#" in href:
            continue
        t = a.get_text(strip=True)
        if not t or devcount(t) < 3 or is_nav(t):
            continue
        url = urljoin(BASE, href)
        if url in seen:
            continue
        seen.add(url)
        children.append({"title": t, "url": url})
    return "index", title, children

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", required=True, help="JSON list of {section,title,url}")
    ap.add_argument("--out", required=True, help="output dir for cache + tree.json")
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args()

    out = Path(args.out); cache = out / "pages"; cache.mkdir(parents=True, exist_ok=True)
    seeds = json.loads(Path(args.seeds).read_text(encoding="utf-8"))

    nodes = {}           # url -> node
    queue = []
    for s in seeds:
        queue.append((s["url"], s.get("section"), s.get("title"), None, s.get("title")))
    visited = set()

    while queue:
        url, section, title, parent, work_prefix = queue.pop(0)
        if url in visited:
            # still record parent linkage if new
            continue
        visited.add(url)
        try:
            html = fetch(url, cache, args.delay)
        except Exception as e:
            nodes[url] = {"url": url, "section": section, "title": title,
                          "kind": "error", "error": str(e), "parent": parent}
            print(f"  ERROR {title}: {e}", flush=True)
            continue
        kind, page_title, children = classify(html)
        dev = devcount_of_poem(html) if kind == "leaf" else 0
        nodes[url] = {"url": url, "section": section, "title": title or page_title,
                      "page_title": page_title, "kind": kind, "parent": parent,
                      "cache": cache_path(cache, url).name,
                      "dev": dev, "nchildren": len(children)}
        print(f"  [{kind:5s}] dev={dev:5d} ch={len(children):3d}  {title or page_title}", flush=True)
        if kind == "index":
            # Take ALL non-nav content links: collection members don't share the
            # collection's title prefix, so prefix-matching loses them. Leaves are
            # terminal (children==[]), which bounds the crawl to Devkota's tree.
            child_list = children
            nodes[url]["child_urls"] = [ch["url"] for ch in child_list]
            nodes[url]["child_titles"] = [ch["title"] for ch in child_list]
            for ch in child_list:
                if ch["url"] not in visited:
                    queue.append((ch["url"], section, ch["title"], url, None))

    Path(out / "tree.json").write_text(
        json.dumps(list(nodes.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    leaves = [n for n in nodes.values() if n["kind"] == "leaf"]
    idx = [n for n in nodes.values() if n["kind"] == "index"]
    err = [n for n in nodes.values() if n["kind"] == "error"]
    print(f"\nDONE: {len(nodes)} pages — {len(leaves)} leaf, {len(idx)} index, {len(err)} error")
    print(f"tree -> {out/'tree.json'}")

def devcount_of_poem(html: str) -> int:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    c = soup.select_one("#mw-content-text") or soup
    return sum(devcount(p.get_text()) for p in c.select("div.poem"))

if __name__ == "__main__":
    sys.exit(main())
