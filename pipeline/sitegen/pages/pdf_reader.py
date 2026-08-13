"""Lazy, range-loading source-PDF reader page."""

from ..text import esc

def write_pdf_reader(context, page, assets, out_dir, depth, rel, pdf_fn, meta, aslug_, aname):
    """Write out_dir/pdf/index.html — the lazy pdf.js reader for a PDF-bearing work."""
    rdepth = depth + 1
    up = "../" * rdepth
    pdf_url = (f'{context.archive_base.rstrip("/")}/{rel.as_posix()}/{esc(pdf_fn)}'
               if context.archive_base else f'../{esc(pdf_fn)}')
    title = meta["title"]
    title_full = f"{title} — {meta['author']['name']} — मूल पृष्ठ"
    head = (f'<script src="{up}pdfjs/pdf.min.js"></script>\n'
            f'<style>{assets.pdf_reader_css}</style>\n')
    js = assets.pdf_reader_js.replace("__WORKER_URL__", f"{up}pdfjs/pdf.worker.min.js")
    body = f"""<nav class="crumb"><a href="{up}authors/{aslug_}/">← {esc(aname)}</a> · <a href="../">{esc(title)}</a></nav>
<div class="pdftop">
  <h1 class="pdfh1">{esc(title)} — मूल पृष्ठ</h1>
  <div class="pdfbar"><a class="pdfback" href="../">← पाठ पढ्नुहोस्</a><span id="pdfstatus" class="pdfstat"></span><span class="pdfzoom"><button id="pdfminus" type="button" aria-label="सानो">−</button><button id="pdfplus" type="button" aria-label="ठूलो">+</button></span></div>
</div>
<div id="pdfpages" class="pdfpages" data-url="{pdf_url}"></div>
<noscript><p class="pdferr">PDF रिडरलाई JavaScript चाहिन्छ। <a href="{pdf_url}">सिधै PDF हेर्नुहोस्</a>।</p></noscript>
<script>{js}</script>"""
    pdir = out_dir / "pdf"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "index.html").write_text(
        page(title_full, body, desc=title_full, css_depth=rdepth, active="works",
             canon=rel.as_posix() + "/pdf/", extra_head=head, noindex=True),
        encoding="utf-8")
