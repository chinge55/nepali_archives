"""Reading pages, long-work sections, downloads, and PDF entry points."""

from collections import Counter
import json
from pathlib import Path
import re
import shutil

from ..config import GENRE, PROSE_GENRES, SITE_URL
from ..text import devnum, esc, paginate_work, work_html
from .pdf_reader import write_pdf_reader


DEVANAGARI_WORD = re.compile(r"[ऀ-ॣ०-ॿ]+")


def write_work_pages(context, page, assets, catalogue):
    search_rows = []
    word_counts = Counter()
    for author_slug, author_records in catalogue.by_author.items():
        author_name = catalogue.author_info(
            author_slug, author_records[0][1]
        )[0]
        for index, (work, meta, text) in enumerate(author_records):
            word_counts.update(DEVANAGARI_WORD.findall(text))
            relative = Path(work["path"]).relative_to("archives")
            output = context.site / relative
            output.mkdir(parents=True, exist_ok=True)
            depth = len(relative.parts)
            up = "../" * depth
            collections = work.get("collection") or []

            filters = (
                '<span data-pagefind-filter="author[data-v]" '
                f'data-v="{esc(meta["author"]["name"])}"></span>'
            )
            filters += "".join(
                '<span data-pagefind-filter="collection[data-v]" '
                f'data-v="{esc(collection)}"></span>'
                for collection in collections
            )
            if meta["genre"]:
                filters += (
                    '<span data-pagefind-filter="genre[data-v]" '
                    f'data-v="{esc(meta["genre"][0])}"></span>'
                )

            genre = meta["genre"][0] if meta["genre"] else ""
            verse = genre not in PROSE_GENRES
            genre_name = GENRE.get(genre, (genre, ""))[0] if genre else ""
            meta_bits = [
                (
                    f'<a href="{up}authors/{author_slug}/#{genre}">'
                    f"{esc(genre_name)}</a>"
                    if genre_name
                    else ""
                )
            ]
            for collection in collections:
                meta_bits.append(
                    f'सङ्ग्रह: <a href="{up}collections/'
                    f'{catalogue.collection_slugs[collection]}/">'
                    f"{esc(collection)}</a>"
                )

            formats = meta.get("formats", {})
            source_info = meta.get("source", {})
            editions = source_info.get("pdf_editions") or []
            source_dir = context.root / work["path"]
            pdf_filename = formats.get("pdf")
            primary_edition = next(
                (edition for edition in editions if edition.get("file") == pdf_filename),
                None,
            )
            format_links = {}
            for kind in ("pdf", "epub", "txt"):
                filename = formats.get(kind)
                if not filename:
                    continue
                if context.archive_base:
                    format_links[kind] = (
                        f'{context.archive_base.rstrip("/")}/{relative}/'
                        f"{esc(filename)}"
                    )
                elif (source_dir / filename).exists():
                    shutil.copy(source_dir / filename, output / filename)
                    format_links[kind] = esc(filename)

            # Every declared edition is a downloadable source.  The canonical
            # formats.pdf file is retained and copied only once when repeated.
            def edition_display_label(edition):
                label = edition["label"]
                if edition.get("kind") == "typeset" and "डिजिटल संस्करण" not in label:
                    return label + " — डिजिटल संस्करण"
                return label

            edition_links = []
            for edition in editions:
                filename = edition["file"]
                if context.archive_base:
                    direct = f'{context.archive_base.rstrip("/")}/{relative}/{esc(filename)}'
                elif (source_dir / filename).exists():
                    if filename != pdf_filename or "pdf" not in format_links:
                        shutil.copy(source_dir / filename, output / filename)
                    direct = esc(filename)
                else:
                    continue
                edition_links.append((edition, direct))

            download_links = [
                f'<a href="{format_links[kind]}">{label}</a>'
                for kind, label in [
                    ("epub", "EPUB"),
                    ("txt", "मूल पाठ (TXT)"),
                ]
                if kind in format_links
            ]
            pdf_button = ""
            if pdf_filename:
                direct_download = (
                    f' <a class="pdfread" href="{format_links["pdf"]}" download>⬇ PDF डाउनलोड</a>'
                    if "pdf" in format_links else ""
                )
                primary_label = edition_display_label(primary_edition) if primary_edition else "मूल पृष्ठ"
                primary_href = "pdf/"
                links = [
                    f'<a class="pdfread" href="{primary_href}">📖 {esc(primary_label)} हेर्नुहोस्</a>'
                ]
                for edition, direct in edition_links:
                    if edition.get("file") == pdf_filename:
                        continue
                    eid = edition["id"]
                    links.append(
                        f'<a class="pdfread" href="pdf/{esc(eid)}/">📖 {esc(edition_display_label(edition))} हेर्नुहोस्</a>'
                        f' <a href="{direct}" download>⬇ PDF</a>'
                    )
                pdf_button = '\n  <p class="pdfacts">' + " ".join(links) + direct_download + "</p>"

            def section_pdf_link(section_label):
                # The reader joins a printed heading/subtitle with an em dash.
                # Compare that layout form without changing the source label.
                def label_key(value):
                    return re.sub(r"\s+", " ", value.replace("\n", " — ")).strip()
                links = []
                seen = set()
                for edition in editions:
                    for section in edition.get("sections") or []:
                        labels = [section.get("label", "")] + section.get("aliases", [])
                        if not any(label_key(label) == label_key(section_label) for label in labels):
                            continue
                        eid = edition.get("id") if edition.get("file") != pdf_filename else None
                        href = "../pdf/" if not eid else f"../pdf/{esc(eid)}/"
                        href += f'?page={int(section["page_start"])}'
                        if href in seen:
                            continue
                        seen.add(href)
                        links.append(
                            f'<a class="pdfread" href="{href}">'
                            f'📖 {esc(edition_display_label(edition))} · {esc(section_label)}</a>'
                        )
                return '<p class="pdf-section">' + " ".join(links) + '</p>' if links else ""

            source_name = meta["source"].get("name") or ""
            source_url = meta["source"].get("url") or ""
            source_html = (
                f'<a href="{esc(source_url)}" rel="nofollow">'
                f"{esc(source_name or source_url)}</a>"
                if source_url
                else (esc(source_name) or "—")
            )

            sequence = []
            if index > 0:
                previous_id = author_records[index - 1][0]["id"]
                previous_title = author_records[index - 1][1]["title"]
                sequence.append(
                    f'<a class="pv" href="../{esc(previous_id)}/">'
                    '<span class="lbl">अघिल्लो</span>← '
                    f"{esc(previous_title)}</a>"
                )
            if index < len(author_records) - 1:
                next_id = author_records[index + 1][0]["id"]
                next_title = author_records[index + 1][1]["title"]
                sequence.append(
                    f'<a class="nx" href="../{esc(next_id)}/">'
                    '<span class="lbl">अर्को</span>'
                    f"{esc(next_title)} →</a>"
                )

            linked_data = json.dumps(
                {
                    "@context": "https://schema.org",
                    "@type": "CreativeWork",
                    "name": meta["title"],
                    "author": {
                        "@type": "Person",
                        "name": meta["author"]["name"],
                    },
                    "inLanguage": "ne",
                    "isAccessibleForFree": True,
                    "license": (
                        "https://creativecommons.org/publicdomain/mark/1.0/"
                    ),
                    "url": SITE_URL + str(relative) + "/",
                },
                ensure_ascii=False,
            )
            downloads = (
                '<p class="downloads">डाउनलोड: '
                f'{" ".join(download_links) if download_links else "—"}<br>'
                '<span style="font-size:.78rem">स्रोत: '
                f"{source_html} · सार्वजनिक डोमेन (असत्यापित)</span></p>"
            )
            sequence_nav = f'<nav class="seqnav">{"".join(sequence)}</nav>'
            full_title = f"{meta['title']} — {meta['author']['name']}"
            rendered_text = work_html(text, verse)
            sections = paginate_work(
                text, balance=len(rendered_text) > 150000
            )

            if not sections:
                body = f"""<nav class="crumb"><a href="{up}authors/{author_slug}/">← {esc(author_name)}</a></nav>
<article>
  <h1>{esc(meta['title'])}</h1>
  <p class="byline">{esc(meta['author']['name'])}</p>
  <p class="meta">{" · ".join(bit for bit in meta_bits if bit)}</p>{pdf_button}
  <div class="work {'verse' if verse else 'prose'}" data-pagefind-body>{filters}
{rendered_text}
  </div>
  {downloads}
</article>
{sequence_nav}"""
                (output / "index.html").write_text(
                    page(
                        full_title,
                        body,
                        desc=full_title,
                        css_depth=depth,
                        active="works",
                        canon=str(relative) + "/",
                        extra_head=(
                            '<script type="application/ld+json">'
                            f"{linked_data}</script>\n"
                        ),
                    ),
                    encoding="utf-8",
                )
            else:
                section_count = len(sections)
                contents = "".join(
                    f'<li><a href="{section_index + 1}/">{esc(label)}</a></li>'
                    for section_index, (label, _) in enumerate(sections)
                )
                contents_body = f"""<nav class="crumb"><a href="{up}authors/{author_slug}/">← {esc(author_name)}</a></nav>
<article>
  <h1>{esc(meta['title'])}</h1>
  <p class="byline">{esc(meta['author']['name'])}</p>
  <p class="meta">{" · ".join(bit for bit in meta_bits if bit)}</p>{pdf_button}
  <p class="tochint">{devnum(section_count)} खण्डमा विभाजित — कुनै पनि खण्ड छानेर पढ्नुहोस् :</p>
  <ol class="toc">{contents}</ol>
  {downloads}
</article>
{sequence_nav}"""
                (output / "index.html").write_text(
                    page(
                        full_title,
                        contents_body,
                        desc=full_title,
                        css_depth=depth,
                        active="works",
                        canon=str(relative) + "/",
                        extra_head=(
                            '<script type="application/ld+json">'
                            f"{linked_data}</script>\n"
                        ),
                    ),
                    encoding="utf-8",
                )
                for section_index, (label, content) in enumerate(sections):
                    section_dir = output / str(section_index + 1)
                    section_dir.mkdir(parents=True, exist_ok=True)
                    section_depth = depth + 1
                    section_up = "../" * section_depth
                    section_nav = [
                        (
                            f'<a class="pv" href="../{section_index}/">'
                            '<span class="lbl">अघिल्लो</span>← '
                            f"{esc(sections[section_index - 1][0])}</a>"
                            if section_index > 0
                            else (
                                '<a class="pv" href="../">'
                                '<span class="lbl">सूची</span>← सूची</a>'
                            )
                        )
                    ]
                    if section_index < section_count - 1:
                        section_nav.append(
                            f'<a class="nx" href="../{section_index + 2}/">'
                            '<span class="lbl">अर्को</span>'
                            f"{esc(sections[section_index + 1][0])} →</a>"
                        )
                    section_body = f"""<nav class="crumb"><a href="{section_up}authors/{author_slug}/">← {esc(author_name)}</a> · <a href="../">{esc(meta['title'])} (सूची)</a></nav>
<article>
  <h1>{esc(label)}</h1>
  <p class="byline"><a href="../">{esc(meta['title'])}</a> · {esc(meta['author']['name'])} · {devnum(section_index + 1)}/{devnum(section_count)}</p>
  {section_pdf_link(label)}
  <div class="work {'verse' if verse else 'prose'}" data-pagefind-body>{filters}
{work_html(content, verse)}
  </div>
</article>
<nav class="seqnav">{''.join(section_nav)}</nav>"""
                    (section_dir / "index.html").write_text(
                        page(
                            f"{label} — {full_title}",
                            section_body,
                            desc=f"{label} — {full_title}",
                            css_depth=section_depth,
                            active="works",
                            canon=(
                                str(relative)
                                + f"/{section_index + 1}/"
                            ),
                        ),
                        encoding="utf-8",
                    )

            if pdf_filename:
                write_pdf_reader(
                    context, page, assets, output, depth, relative,
                    pdf_filename, meta, author_slug, author_name,
                    reader_label=edition_display_label(primary_edition) if primary_edition else None,
                )
                for edition, _direct in edition_links:
                    if edition.get("file") == pdf_filename:
                        continue
                    write_pdf_reader(
                        context, page, assets, output, depth, relative,
                        edition["file"], meta, author_slug, author_name,
                        edition_id=edition["id"], reader_label=edition_display_label(edition),
                    )
            search_rows.append(
                {
                    "t": meta["title"],
                    "r": meta.get("title_roman") or "",
                    "s": work["id"].replace("_", " "),
                    "a": meta["author"].get("name_roman") or "",
                    "c": "; ".join(collections) if collections else "",
                    "g": genre,
                    "m": catalogue.extras[work["path"]]["min"],
                    "f": 1 if catalogue.extras[work["path"]]["pdf"] else 0,
                    "p": str(relative) + "/",
                }
            )
    return search_rows, word_counts
