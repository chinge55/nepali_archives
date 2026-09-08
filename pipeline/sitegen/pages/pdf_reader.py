"""Lazy, range-loading source-PDF reader pages."""

from ..text import esc


def write_pdf_reader(
    context, page, assets, out_dir, depth, rel, pdf_fn, meta, aslug_, aname,
    *, edition_id=None, reader_label=None,
):
    """Write a lazy pdf.js reader for the primary or an alternate PDF edition."""
    subdir = "pdf" if edition_id is None else f"pdf/{edition_id}"
    reader_depth = depth + (1 if edition_id is None else 2)
    up = "../" * reader_depth
    local_up = "../" * (1 if edition_id is None else 2)
    pdf_url = (
        f'{context.archive_base.rstrip("/")}/{rel.as_posix()}/{esc(pdf_fn)}'
        if context.archive_base else f'{local_up}{esc(pdf_fn)}'
    )
    title = meta["title"]
    label = reader_label or "मूल पृष्ठ"
    edition = next(
        (item for item in (meta.get("source", {}).get("pdf_editions") or [])
         if item.get("file") == pdf_fn),
        None,
    )
    section_rows = []
    seen_sections = set()
    for section in (edition or {}).get("sections") or []:
        section_label = section.get("label")
        page_start = section.get("page_start")
        key = (section_label, page_start)
        if (not isinstance(section_label, str) or not section_label.strip()
                or isinstance(page_start, bool) or not isinstance(page_start, int)
                or page_start < 1 or key in seen_sections):
            continue
        seen_sections.add(key)
        section_rows.append((section_label, page_start))
    section_toc = ""
    if len(section_rows) > 1:
        items = "".join(
            f'<li><a href="?page={page_start}">{esc(section_label)}</a></li>'
            for section_label, page_start in section_rows
        )
        section_toc = (
            f'<details class="pdftoc"><summary>विषयसूची</summary>'
            f'<ol class="toc">{items}</ol></details>\n'
        )
    title_full = f"{title} — {meta['author']['name']} — {label}"
    head = (f'<script src="{up}pdfjs/pdf.min.js"></script>\n'
            f'<style>{assets.pdf_reader_css}</style>\n')
    js = assets.pdf_reader_js.replace("__WORKER_URL__", f"{up}pdfjs/pdf.worker.min.js")
    back = "../" if edition_id is None else "../../"
    body = f"""<nav class="crumb"><a href="{up}authors/{aslug_}/">← {esc(aname)}</a> · <a href="{back}">{esc(title)}</a></nav>
<div class="pdftop">
  <h1 class="pdfh1">{esc(title)} — {esc(label)}</h1>
  <div class="pdfbar"><a class="pdfback" href="{back}">← पाठ पढ्नुहोस्</a><span id="pdfstatus" class="pdfstat"></span><span class="pdfzoom"><button id="pdfminus" type="button" aria-label="सानो">−</button><button id="pdfplus" type="button" aria-label="ठूलो">+</button></span></div>
</div>
{section_toc}<div id="pdfpages" class="pdfpages" data-url="{pdf_url}"></div>
<noscript><p class="pdferr">PDF रिडरलाई JavaScript चाहिन्छ। <a href="{pdf_url}">सिधै PDF हेर्नुहोस्</a>।</p></noscript>
<script>{js}</script>"""
    pdir = out_dir / "pdf" if edition_id is None else out_dir / "pdf" / edition_id
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "index.html").write_text(
        page(title_full, body, desc=title_full, css_depth=reader_depth,
             active="works", canon=rel.as_posix() + f"/{subdir}/", extra_head=head,
             noindex=True),
        encoding="utf-8")
