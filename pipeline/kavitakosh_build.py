#!/usr/bin/env python3
"""
kavitakosh_build.py — turn a crawled Kavita Kosh tree into archive works.

Reads /tmp/kk/{tree.json, leaves.json, containers.json} produced by
kavitakosh_crawl.py and materialises work directories under
archives/authors/devkota/:

  * CONTAINERS (multi-part single works) are assembled into one text.txt with a
    header per part:  मुना मदन (18 sections).  पृथ्वीराज चौहान is already built
    and is only used here to EXCLUDE its canto pages from the poem set.
  * COLLECTIONS (भिखारी., लक्ष्मी कवितासङ्ग्रह, सुनको बिहान) are anthologies; their
    members become individual poem works, tagged with the collection name in the
    description. No text is duplicated.
  * Every remaining unique leaf poem becomes its own work.

Dedup is by normalised-content hash (variant-spelling pages collapse to one).
Text is preserved verbatim (proofread=false). Slugs/title_roman come from
indic_transliteration (HK for slugs, IAST for display).
"""
import json, re, hashlib, sys
from datetime import date
from pathlib import Path
from urllib.parse import unquote
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

ROOT = Path(__file__).resolve().parent.parent
DEVK = ROOT / "archives/authors/devkota"
KK = Path("/tmp/kk")
TODAY = date.today().isoformat()
AUTHOR = {"id": "devkota", "name": "लक्ष्मीप्रसाद देवकोटा",
          "name_roman": "Laxmi Prasad Devkota"}

def clean_title(t):
    return re.sub(r"\s*/\s*लक्ष्मीप्रसाद देवकोटा\s*$", "", t).strip().strip("‘’\"")

def slugify(dev_title):
    hk = transliterate(dev_title, sanscript.DEVANAGARI, sanscript.HK)
    s = hk.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "work"

def roman(dev_title):
    return transliterate(dev_title, sanscript.DEVANAGARI, sanscript.IAST)

def base_meta(slug, title, genre, desc, url):
    return {
        "id": slug, "title": title, "title_roman": roman(title), "subtitle": None,
        "author": dict(AUTHOR), "language": "ne", "script": "Devanagari",
        "genre": genre, "first_published": {"bs": None, "ad": None},
        "edition": None, "publisher": None, "description": desc,
        "rights": {"status": "public-domain",
                   "basis": "Author died 1959; Nepal's Copyright Act 2059 grants life + 50 years, expiring 2009."},
        "source": {"name": "Kavita Kosh (kavitakosh.org)", "url": url,
                   "pdf": None, "html": None},
        "pages": None,
        "text": {"extraction_method": "html", "ocr_status": "born-digital",
                 "proofread": False, "quality": "good"},
        "formats": {"pdf": None, "txt": "text.txt", "html": None, "epub": None},
        "added": TODAY, "updated": TODAY,
    }

def write_work(slug, text, meta, keep_existing_source=False):
    d = DEVK / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "text.txt").write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    mp = d / "metadata.json"
    if keep_existing_source and mp.exists():
        old = json.loads(mp.read_text(encoding="utf-8"))
        # preserve a previously-recorded source PDF and formats.pdf
        if old.get("source", {}).get("pdf"):
            meta["source"]["pdf"] = old["source"]["pdf"]
            meta["formats"]["pdf"] = old["formats"].get("pdf")
        meta["added"] = old.get("added", TODAY)
    mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return d

def main():
    tree = json.load(open(KK / "tree.json"))
    leaves = json.load(open(KK / "leaves.json"))      # url -> {title,hash,dev,text}
    containers = json.load(open(KK / "containers.json"))  # name -> [child_url]

    # ---- collection membership (by url and by content-hash) ----
    COLLECTIONS = {"भिखारी": "भिखारी (कवितासङ्ग्रह)",
                   "लक्ष्मी कवितासङ्ग्रह": "लक्ष्मी कवितासङ्ग्रह",
                   "सुनको बिहान": "सुनको बिहान (बालसाहित्य)"}
    hash_of = {u: leaves[u]["hash"] for u in leaves}
    coll_by_hash = {}   # hash -> set(collection display names)
    for key, disp in COLLECTIONS.items():
        for u in containers.get(key, []):
            if u in hash_of:
                coll_by_hash.setdefault(hash_of[u], set()).add(disp)
    balsahitya = set()  # hashes that belong to सुनको बिहान
    for u in containers.get("सुनको बिहान", []):
        if u in hash_of:
            balsahitya.add(hash_of[u])

    # ---- URLs consumed by assembled container works (excluded from poems) ----
    consumed = set()
    for key in ("मुना मदन", "पृथ्वीराज चौहान"):
        consumed.update(containers.get(key, []))
    # also exclude the collection self-link pages (titles ending in '.')
    selfish = {u for u in leaves if leaves[u]["title"].strip().startswith(("सुनको बिहान .", "भिखारी ."))}

    # ---- 1) assemble मुना मदन into existing dir 'munamadan' ----
    mm_parts = []
    for u in containers["मुना मदन"]:
        if u not in leaves:
            continue
        seg = clean_title(leaves[u]["title"]).replace(" / मुना मदन", "").strip()
        mm_parts.append(f"{seg}\n\n{leaves[u]['text'].strip()}")
    mm_text = "मुना मदन\n\nलक्ष्मीप्रसाद देवकोटा\n\n" + "\n\n\n".join(mm_parts)
    mm_meta = base_meta("munamadan", "मुना मदन", ["khandakavya", "narrative-poem"],
        "Devkota's beloved khandakavya in jhyaure metre, in 18 titled sections; the most famous work in Nepali. Text from Kavita Kosh (born-digital); a scanned PDF edition is also preserved in this directory.",
        "https://kavitakosh.org/kk/मुना_मदन_/_लक्ष्मीप्रसाद_देवकोटा")
    write_work("munamadan", mm_text, mm_meta, keep_existing_source=True)
    print(f"  munamadan (मुना मदन): assembled {len(mm_parts)} sections")

    # ---- 2) individual poems (unique by content hash, minus consumed/selfish) ----
    seen_hash = {}     # hash -> slug  (dedup)
    slug_taken = set(p.name for p in DEVK.iterdir() if p.is_dir())
    # keep these existing dirs as-is / reuse:
    REUSE = {"भिखारी": "bhikhari"}   # crawl version refreshes existing bhikhari

    KNOWN_GENRE = {"दिल कचौरा यो उचालौँ": ["gazal", "ghazal"],
                   "सागरभरि छाती चिरी": ["git", "song"]}

    made = 0
    # order: prefer longer text as the representative for a hash
    poem_urls = [u for u in leaves
                 if u not in consumed and u not in selfish]
    poem_urls.sort(key=lambda u: -len(leaves[u]["text"]))
    for u in poem_urls:
        h = leaves[u]["hash"]
        if h in seen_hash:
            continue
        title = clean_title(leaves[u]["title"])
        if not title or len(re.findall(r"[ऀ-ॿ]", leaves[u]["text"])) < 40:
            continue
        seen_hash[h] = True
        # slug
        if title in REUSE:
            slug = REUSE[title]
        else:
            slug = slugify(title)
            base = slug; i = 2
            while slug in slug_taken:
                slug = f"{base}_{i}"; i += 1
        slug_taken.add(slug)
        # genre + collection note
        colls = sorted(coll_by_hash.get(h, []))
        genre = KNOWN_GENRE.get(title,
                 (["balkavita", "children's poem"] if h in balsahitya else ["kavita", "poem"]))
        desc = ("From the collection " + "; ".join(colls) + "." ) if colls else None
        meta = base_meta(slug, title, genre, desc, unquote(u))
        write_work(slug, leaves[u]["text"], meta)
        made += 1
    print(f"  individual poems written: {made}")
    print(f"  (skipped {len(containers.get('पृथ्वीराज चौहान',[]))} पृथ्वीराज cantos — already a work)")
    print(f"  total work dirs now: {sum(1 for p in DEVK.iterdir() if p.is_dir())}")

if __name__ == "__main__":
    sys.exit(main())
