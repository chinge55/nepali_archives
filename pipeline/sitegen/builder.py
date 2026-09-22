"""Explicit orchestration for a complete static-site build."""

from __future__ import annotations

import stats

from .assets import AssetBundle, install_common_assets
from .config import GENRE, PROSE_GENRES, SITE_NAME, SITE_URL
from .context import BuildContext, BuildStats
from .layout import PageRenderer
from .model import load_catalogue
from .pages.about import write_about_page
from .pages.catalogue import write_catalogue_pages
from .pages.ocr import write_ocr_page
from .pages.patro import write_patro_page
from .pages.type_tool import write_type_page
from .pages.works import write_work_pages
from .search import write_search_data
from .seo import write_sitemaps


def write_site_metadata(context):
    write_sitemaps(context.site)
    (context.site / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n",
        encoding="utf-8",
    )
    (context.site / ".nojekyll").write_text("", encoding="utf-8")
    domain = SITE_URL.split("//", 1)[-1].strip("/")
    (context.site / "CNAME").write_text(domain + "\n", encoding="utf-8")


def build(
    context: BuildContext,
    *,
    normalize_key,
    translit_word_keys,
) -> BuildStats:
    assets = AssetBundle.load(context.root)
    page = PageRenderer(assets)
    catalogue = load_catalogue(context)
    install_common_assets(context, assets)

    search_rows, word_counts = write_work_pages(
        context, page, assets, catalogue
    )
    write_search_data(
        context,
        search_rows,
        word_counts,
        normalize_key=normalize_key,
        translit_word_keys=translit_word_keys,
    )
    write_catalogue_pages(context, page, assets, catalogue)
    write_about_page(context, page, catalogue)
    write_ocr_page(context, page)
    write_type_page(context, page, assets)
    write_patro_page(context, page, assets)
    stats.build_stats_page(
        catalogue.records,
        catalogue.collections,
        page=page,
        GENRE=GENRE,
        PROSE_GENRES=PROSE_GENRES,
        site=context.site,
        site_name=SITE_NAME,
    )
    write_site_metadata(context)

    pages = sum(1 for _ in context.site.rglob("*.html"))
    return BuildStats(
        pages=pages,
        works=len(catalogue.records),
        authors=len(catalogue.by_author),
        genres=len(catalogue.genres_present),
        collections=len(catalogue.collections),
        search_index_bytes=(
            context.site / "search-index.json"
        ).stat().st_size,
    )
