"""Home, collection, genre, and author browse pages."""

from pathlib import Path

from ..config import GENRE, GENRE_ORDER, SITE_NAME, SITE_TAGLINE, SITE_TAGLINE_EN
from ..introductions import GENRE_INTROS
from ..text import DEVNUM, devnum, esc


def write_catalogue_pages(context, page, assets, catalogue):
    site = context.site

    collection_dir = site / "collections"
    collection_dir.mkdir(parents=True, exist_ok=True)

    def collection_cards(entries, base):
        cards = []
        for collection, items in entries:
            authors = list(dict.fromkeys(meta["author"]["name"] for _, meta in items))
            cards.append(
                f'<a class="card" href="{base}{catalogue.collection_slugs[collection]}/">'
                f'<b>{esc(collection)}</b><span class="en">{esc(" · ".join(authors))}</span>'
                f'<span class="n">{devnum(len(items))} कृति</span></a>'
            )
        return '<div class="shelf">' + "".join(cards) + '</div>'

    collection_groups = []
    for author in catalogue.author_order:
        entries = sorted(
            (name, items) for name, items in catalogue.collections.items()
            if any(catalogue.author_slug(work) == author for work, _ in items)
        )
        if entries:
            name = catalogue.author_info(author, catalogue.by_author[author][0][1])[0]
            collection_groups.append(
                f'<section><h2><a href="../authors/{author}/">{esc(name)}</a></h2>'
                + collection_cards(entries, "") + '</section>'
            )
    collections_body = (
        f'<nav class="crumb"><a href="../">← {esc(SITE_NAME)}</a></nav>'
        '<h1>सङ्ग्रह</h1><p class="genre-intro">प्रकाशित सङ्ग्रहभित्रका कविता, गीत र निबन्धलाई छुट्टाछुट्टै पढ्नुहोस्।</p>'
        f'<p class="lead">{devnum(len(catalogue.collections))} सङ्ग्रह। तलका सङ्ख्या यहाँ उपलब्ध कृतिका हुन्।</p>'
        + "".join(collection_groups)
    )
    (collection_dir / "index.html").write_text(
        page("सङ्ग्रह — " + SITE_NAME, collections_body, css_depth=1, active="works",
             desc="लेखकअनुसार नेपाली साहित्यका प्रकाशित सङ्ग्रह र तिनमा उपलब्ध कृतिहरू।", canon="collections/"),
        encoding="utf-8",
    )
    for alias, names in catalogue.collection_aliases.items():
        output = collection_dir / alias
        output.mkdir(parents=True, exist_ok=True)
        body = ('<nav class="crumb"><a href="../">← सङ्ग्रह</a></nav>'
                '<h1>सङ्ग्रह छान्नुहोस्</h1><p class="genre-intro">पढ्न चाहनुभएको भाग छान्नुहोस्।</p>'
                + collection_cards([(name, catalogue.collections[name]) for name in names], "../"))
        (output / "index.html").write_text(
            page("सङ्ग्रह छान्नुहोस् — " + SITE_NAME, body, css_depth=2,
                 active="works", canon=f"collections/{alias}/"), encoding="utf-8",
        )

    for collection, items in catalogue.collections.items():
        output = collection_dir / catalogue.collection_slugs[collection]
        output.mkdir(parents=True, exist_ok=True)
        list_items = "".join(
            catalogue.work_list_item(
                work,
                meta,
                (
                    "../../"
                    + esc(
                        Path(work["path"])
                        .relative_to("archives")
                        .as_posix()
                    )
                    + "/"
                ),
                chip=True,
            )
            for work, meta in items
        )
        body = (
            f'<nav class="crumb"><a href="../">← सङ्ग्रह</a></nav>'
            f'<h1>{esc(collection)}</h1><p class="genre-intro">यस सङ्ग्रहबाट अभिलेखमा उपलब्ध {devnum(len(items))} कृति छुट्टाछुट्टै पढ्नुहोस्।</p>'
            '<p><input id="q" type="search" placeholder="यस सङ्ग्रहभित्र खोज्नुहोस् — शीर्षक वा पाठ" '
            'autocomplete="off" aria-label="खोज"></p><p class="hint" id="hint"></p>'
            f'<div id="ft" data-base="../../" data-scope-collection="{esc(collection)}"></div>'
            f'<ul class="works">{list_items}</ul>'
            f'<script src="../../search.js?v={assets.search_version}" defer></script>'
        )
        (output / "index.html").write_text(
            page(
                f"{collection} — सङ्ग्रह",
                body,
                css_depth=2,
                active="works",
                desc=f"{collection} — {len(items)} कृति",
                canon=(
                    f"collections/{catalogue.collection_slugs[collection]}/"
                ),
            ),
            encoding="utf-8",
        )

    for genre in catalogue.genres_present:
        genre_name, genre_english = GENRE.get(genre, (genre, ""))
        genre_items = catalogue.by_genre[genre]
        groups = []
        for author in catalogue.author_order:
            author_items = sorted(
                (
                    item
                    for item in genre_items
                    if catalogue.author_slug(item[0]) == author
                ),
                key=lambda item: item[1]["title"],
            )
            if not author_items:
                continue
            author_name = catalogue.author_info(
                author, author_items[0][1]
            )[0]
            list_items = "".join(
                catalogue.work_list_item(
                    work,
                    meta,
                    f'../../authors/{author}/{esc(work["id"])}/',
                )
                for work, meta in author_items
            )
            groups.append(
                f'<div class="group"><h2><a href="../../authors/{author}/">'
                f"{esc(author_name)}</a> "
                f'<span class="count">{len(author_items)}</span></h2>'
                f'<ul class="works">{list_items}</ul></div>'
            )
        body = (
            f'<nav class="crumb"><a href="../../">← {esc(SITE_NAME)}</a></nav>'
            f'<h1>{esc(genre_name)}</h1><p class="byline">{esc(genre_english)}</p>'
            f'<p class="genre-intro">{esc(GENRE_INTROS.get(genre, ""))}</p>'
            f'<p class="lead">{devnum(len(genre_items))} कृति।</p>'
            f'<p><input id="q" type="search" placeholder="{esc(genre_name)}भित्र खोज्नुहोस् — शीर्षक वा पाठ" '
            'autocomplete="off" aria-label="खोज"></p><p class="hint" id="hint"></p>'
            f'<div id="ft" data-base="../../" data-scope-genre="{genre}"></div>'
            f'{"".join(groups)}'
            f'<script src="../../search.js?v={assets.search_version}" defer></script>'
        )
        output = site / "genres" / genre
        output.mkdir(parents=True, exist_ok=True)
        (output / "index.html").write_text(
            page(
                f"{genre_name} — {SITE_NAME}",
                body,
                css_depth=2,
                active="works",
                desc=(
                    f"{genre_name} — {GENRE_INTROS.get(genre, '')} "
                    f"यहाँ {devnum(len(genre_items))} कृति पढ्नुहोस्।"
                ),
                canon=f"genres/{genre}/",
            ),
            encoding="utf-8",
        )

    genres_body = (
        f'<nav class="crumb"><a href="../">← {esc(SITE_NAME)}</a></nav>'
        f'<h1>विधा</h1><p class="lead">{devnum(len(catalogue.genres_present))} विधा · '
        f"{devnum(len(catalogue.records))} कृति।</p>"
        + catalogue.genre_cards("../")
    )
    (site / "genres").mkdir(parents=True, exist_ok=True)
    (site / "genres" / "index.html").write_text(
        page(
            "विधा — " + SITE_NAME,
            genres_body,
            css_depth=1,
            active="works",
            desc=(
                f"विधा अनुसार ब्राउज गर्नुहोस् — "
                f"{len(catalogue.records)} कृति"
            ),
            canon="genres/",
        ),
        encoding="utf-8",
    )

    for author in catalogue.author_order:
        author_records = catalogue.by_author[author]
        author_name, author_roman, author_dates = catalogue.author_info(
            author, author_records[0][1]
        )
        by_genre = {}
        for work, meta, _ in author_records:
            genre = meta["genre"][0] if meta["genre"] else "kavita"
            by_genre.setdefault(genre, []).append((work, meta))
        present = [
            genre
            for genre in GENRE_ORDER
            + [key for key in by_genre if key not in GENRE_ORDER]
            if by_genre.get(genre)
        ]
        toc = " ".join(
            f'<a href="#{genre}">{esc(GENRE.get(genre, (genre, ""))[0])} '
            f'<span class="count">{len(by_genre[genre])}</span></a>'
            for genre in present
        )
        author_collections = [
            collection
            for collection in sorted(
                catalogue.collections,
                key=lambda item: -len(catalogue.collections[item]),
            )
            if any(
                catalogue.author_slug(work) == author
                for work, _ in catalogue.collections[collection]
            )
        ]
        collection_links = " · ".join(
            f'<a href="../../collections/{catalogue.collection_slugs[collection]}/">'
            f"{esc(collection)}</a>"
            for collection in author_collections
        )
        groups = []
        for genre in present:
            items = sorted(
                by_genre[genre], key=lambda item: item[1]["title"]
            )
            genre_name, genre_english = GENRE.get(genre, (genre, ""))
            list_items = "".join(
                catalogue.work_list_item(
                    work, meta, f'{esc(work["id"])}/'
                )
                for work, meta in items
            )
            groups.append(
                f'<div class="group" id="{genre}"><h2>'
                f'<a href="../../genres/{genre}/">{esc(genre_name)}</a> '
                f'<span class="count">{genre_english} · {len(items)}</span></h2>'
                f'<ul class="works">{list_items}</ul></div>'
            )
        body = f"""<nav class="crumb"><a href="../../">← {esc(SITE_NAME)}</a></nav>
<h1>{esc(author_name)}</h1>
<p class="byline">{esc(author_roman)}{' · ' + author_dates if author_dates else ''}</p>
<p class="lead">{len(author_records)} कृति।</p>
<p><input id="q" type="search" placeholder="{esc(author_name)}का कृतिभित्र खोज्नुहोस् — शीर्षक वा पाठ (रोमनमा पनि)" autocomplete="off" aria-label="खोज"></p>
<p class="hint" id="hint"></p>
<div id="ft" data-base="../../" data-scope-author="{esc(author_name)}"></div>
<p class="toc">{toc}</p>
{f'<p class="meta">सङ्ग्रह: {collection_links}</p>' if collection_links else ''}
{''.join(groups)}
<script src="../../search.js?v={assets.search_version}" defer></script>"""
        output = site / "authors" / author
        output.mkdir(parents=True, exist_ok=True)
        (output / "index.html").write_text(
            page(
                f"{author_name} — कृतिहरू",
                body,
                css_depth=2,
                active="works",
                desc=f"{author_name}का {len(author_records)} कृति",
                canon=f"authors/{author}/",
            ),
            encoding="utf-8",
        )

    def author_list_item(author, base):
        name, roman, _ = catalogue.author_info(
            author, catalogue.by_author[author][0][1]
        )
        return (
            f'<li><a class="row-link" href="{base}authors/{author}/">{esc(name)}'
            f'<span class="r">{esc(roman)} · '
            f"{len(catalogue.by_author[author])} कृति</span></a></li>"
        )

    authors_body = (
        f'<h1>लेखकहरू</h1><p class="lead">{len(catalogue.by_author)} लेखक · '
        f'{len(catalogue.records)} कृति।</p><ul class="works">'
        + "".join(
            author_list_item(author, "../")
            for author in catalogue.author_order
        )
        + "</ul>"
    )
    (site / "authors").mkdir(parents=True, exist_ok=True)
    (site / "authors" / "index.html").write_text(
        page(
            "लेखकहरू — " + SITE_NAME,
            authors_body,
            css_depth=1,
            active="works",
            desc=(
                f"{len(catalogue.by_author)} लेखक · "
                f"{len(catalogue.records)} कृति"
            ),
            canon="authors/",
        ),
        encoding="utf-8",
    )

    home_body = f"""<div class="home-hero">
<h1 class="home-title">{SITE_TAGLINE}</h1>
<p class="tagline-en">{SITE_TAGLINE_EN}</p>
</div>
<div class="home-discovery">
<nav class="browse-links" aria-label="कृति खोज्ने तरिका"><a href="authors/">लेखकअनुसार</a><a href="genres/">विधाअनुसार</a><a href="collections/">सङ्ग्रहअनुसार</a></nav>
<p class="lead home-summary">{str(len(catalogue.by_author)).translate(DEVNUM)} लेखकका {str(len(catalogue.records)).translate(DEVNUM)} कृति — नि:शुल्क, सधैँभरि। दर्ता छैन, विज्ञापन छैन।</p>
<p class="home-search"><input id="q" type="search" placeholder="खोज्नुहोस् — शीर्षक, पाठ वा रोमन" autocomplete="off" aria-label="खोज"></p>
<p class="hint" id="hint">जस्तै: <a href="?q=pagal">pagal</a><a href="?q=muna madan">muna madan</a><a href="?q=hunxa">hunxa</a><a href="?q=फूल">फूल</a></p>
<ul class="works" id="results" data-base=""></ul>
<div id="ft"></div>
</div>
<div class="home-browse">
<div class="home-sec"><h2><a href="genres/">विधा</a></h2>{catalogue.genre_cards("")}</div>
<div class="home-sec"><h2><a href="collections/">सङ्ग्रह</a></h2>
{collection_cards(sorted(catalogue.collections.items(), key=lambda item: (-len(item[1]), item[0]))[:6], "collections/")}
<p><a href="collections/">सबै {devnum(len(catalogue.collections))} सङ्ग्रह हेर्नुहोस् →</a></p></div>
<div class="home-sec"><h2>लेखकहरू</h2><ul class="works">{"".join(author_list_item(author, "") for author in catalogue.author_order)}</ul></div>
<p class="statlink"><a href="stats/">📊 अभिलेख एक नजरमा — तथ्याङ्क र रोचक तथ्य →</a></p>
</div>
<script src="search.js?v={assets.search_version}" defer></script>"""
    (site / "index.html").write_text(
        page(
            SITE_NAME,
            home_body,
            desc="",
            css_depth=0,
            active="home",
            canon="",
        ),
        encoding="utf-8",
    )
