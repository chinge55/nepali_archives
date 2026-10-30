"""Static discovery pages for reviewed metres and located passages."""

from pathlib import Path

from prosody import FREE_VERSE, POETIC_GENRES, published_metres

from ..config import SITE_NAME
from ..text import devnum, esc


def prosody_badge(annotation, metres, up):
    if not annotation:
        return ""
    if annotation["kind"] == "mixed":
        return 'छन्द: <a href="#chhanda-details">मिश्रित</a>'
    identifier = published_metres(annotation)[0]
    label = metres[identifier]["name"]
    return f'छन्द: <a href="{up}chhandas/{identifier}/">{esc(label)}</a>'


def passage_details(annotation, targets, metres, up):
    if not annotation or annotation["kind"] != "mixed":
        return ""
    items = "".join(
        f'<li><a href="{up}{esc(p["url"])}">{esc(metres[p["metre"]]["name"])} · {esc(p["label"])}</a></li>'
        for p in targets
    )
    return ('<details class="prosody-details" id="chhanda-details" data-pagefind-ignore>'
            '<summary>छन्दका अंशहरू</summary><p>यस कृतिमा फरक छन्दका अंश छन्। '
            'तलका लिङ्कबाट पहिचान गरिएका अंश पढ्नुहोस्।</p>'
            f'<ul>{items}</ul></details>')


def write_prosody_pages(context, page, assets, catalogue):
    output = context.site / "chhandas"
    output.mkdir(exist_ok=True)
    present = sorted(catalogue.by_metre, key=lambda key: catalogue.metres[key]["name"])
    poetic_count = sum((meta.get("genre") or [""])[0] in POETIC_GENRES for _, meta, _ in catalogue.records)
    cards = "".join(
        f'<a class="card" href="{identifier}/"><b>{esc(catalogue.metres[identifier]["name"])}</b>'
        f'<span class="n">{devnum(len(catalogue.by_metre[identifier]))} कृति</span></a>'
        for identifier in present
    )
    body = ('<nav class="crumb"><a href="../">← नेपाली अभिलेख</a></nav>'
            '<h1>छन्दअनुसार कविता</h1>'
            '<p class="genre-intro">छन्द छानेर त्यसमा लेखिएका कविता र लामो काव्यका मिल्दा अंश पढ्नुहोस्।</p>'
            f'<p class="lead">{devnum(catalogue.prosody_count)} कृतिको छन्द पहिचान समीक्षा गरिएको छ · '
            f'{devnum(poetic_count)} काव्यात्मक कृति अभिलेखमा।</p>'
            f'<div class="shelf">{cards}</div>'
            '<p class="prosody-note">पहिचान समीक्षा भएका कृतिहरू यहाँ थपिँदै जान्छन्। '
            'एउटै कृति एकभन्दा धेरै छन्दमा पर्न सक्छ।</p>'
            '<p><a href="../kavita-lekhan/">छन्दमा कविता लेख्नुहोस् →</a></p>')
    (output / "index.html").write_text(page(
        "छन्दअनुसार नेपाली कविता — " + SITE_NAME, body, css_depth=1, active="works",
        desc="छन्दअनुसार नेपाली कविता खोज्नुहोस्। समीक्षा गरिएका छन्दका रचना, लेखक र लामो काव्यका मिल्दा अंश पढ्नुहोस्।",
        canon="chhandas/", noindex=not present,
    ), encoding="utf-8")

    for identifier in present:
        metre = catalogue.metres[identifier]
        name = metre["name"]
        records = catalogue.by_metre[identifier]
        authors = sorted({meta["author"]["name"] for _, meta, _ in records})
        groups = []
        for author in authors:
            rows = []
            for work, meta, annotation in sorted(records, key=lambda item: item[1]["title"]):
                if meta["author"]["name"] != author:
                    continue
                base = Path(work["path"]).relative_to("archives").as_posix() + "/"
                targets = [target for target in catalogue.extras[work["path"]].get("prosody_targets", []) if target["metre"] == identifier]
                extra = ""
                if targets:
                    links = " · ".join(f'<a href="../../{esc(p["url"])}">{esc(p["label"])}</a>' for p in targets)
                    extra = f'<p class="prosody-passages">मिल्दा अंश: {links}</p>'
                href = "../../" + (targets[0]["url"] if targets else base)
                rows.append(catalogue.work_list_item(work, meta, esc(href), extra_html=extra))
            groups.append(f'<section class="group" data-author="{esc(author)}"><h2>{esc(author)}</h2><ul class="works">{"".join(rows)}</ul></section>')
        options = "".join(f'<option value="{esc(author)}">{esc(author)}</option>' for author in authors)
        writer = (f'<p><a class="prosody-write" href="../../kavita-lekhan/?metre={esc(metre["writer"])}">यस छन्दमा कविता लेख्नुहोस् →</a></p>'
                  if metre.get("writer") else "")
        heading = "मुक्तछन्दका कविता" if identifier == FREE_VERSE["id"] else f"{name} छन्दका कविता"
        body = ('<nav class="crumb"><a href="../">← छन्दअनुसार कविता</a></nav>'
                f'<h1>{esc(heading)}</h1><p class="genre-intro">पूरा कविता वा लामो काव्यभित्रका सम्बन्धित अंश छान्नुहोस्।</p>'
                f'<p class="lead">{devnum(len(records))} कृति · {devnum(len(authors))} लेखक</p>{writer}'
                f'<div class="prosody-filters"><label for="metre-author">लेखक <select id="metre-author"><option value="">सबै लेखक</option>{options}</select></label>'
                '<label class="search-label" for="q">खोज <input id="q" type="search" placeholder="शीर्षक वा पाठमा खोज्नुहोस्" autocomplete="off"></label></div>'
                '<p class="hint" id="hint"></p>'
                f'<div id="ft" data-base="../../" data-scope-metre="{identifier}"></div>{"".join(groups)}'
                f'<script src="../../search.js?v={assets.search_version}" defer></script>')
        folder = output / identifier
        folder.mkdir(exist_ok=True)
        (folder / "index.html").write_text(page(
            f"{heading} — {SITE_NAME}", body, css_depth=2, active="works",
            desc=f"{heading} पढ्नुहोस्। {devnum(len(records))} कृतिमा समीक्षा गरिएका छन्द, लेखकअनुसार छनोट र मूल पाठका अंश हेर्नुहोस्।",
            canon=f"chhandas/{identifier}/",
        ), encoding="utf-8")
