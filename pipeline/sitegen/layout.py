"""Shared HTML document shell and navigation."""

from dataclasses import dataclass

from .assets import AssetBundle
from .config import SITE_NAME, SITE_TAGLINE, SITE_TAGLINE_EN, SITE_URL
from .text import esc


@dataclass(frozen=True)
class PageRenderer:
    assets: AssetBundle

    def __call__(
        self,
        title,
        body,
        *,
        desc="",
        css_depth=0,
        extra_head="",
        active="",
        canon="",
        noindex=False,
    ):
        up = "../" * css_depth
        canon_url = SITE_URL + canon
        desc = (
            f"{desc} · {SITE_TAGLINE_EN}"
            if desc
            else f"{SITE_TAGLINE} — {SITE_TAGLINE_EN}"
        )
        robots = (
            '<meta name="robots" content="noindex,follow">\n'
            if noindex
            else ""
        )
        og = (
            f'<link rel="canonical" href="{esc(canon_url)}">\n'
            '<meta property="og:type" content="'
            + (
                "article"
                if active == "works"
                and canon.startswith("authors/")
                and canon.rstrip("/").count("/") >= 2
                else "website"
            )
            + '">\n'
            f'<meta property="og:title" content="{esc(title)}">\n'
            f'<meta property="og:description" content="{esc(desc)}">\n'
            f'<meta property="og:url" content="{esc(canon_url)}">\n'
            f'<meta property="og:site_name" content="{SITE_NAME}">\n'
        )
        nav = "".join(
            f'<a href="{(up + href) or "./"}"'
            f'{" class=on" if active == key else ""}>{label}</a>'
            for key, href, label in [
                ("home", "", "गृह"),
                ("works", "authors/", "लेखकहरू"),
                ("type", "type/", "टाइप"),
                ("patro", "patro/", "पात्रो"),
                ("about", "about.html", "बारेमा"),
            ]
        )
        return f"""<!DOCTYPE html>
<html lang="ne">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>(function(){{try{{var t=localStorage.getItem('theme');if(t==='dark'||t==='light')document.documentElement.setAttribute('data-theme',t);}}catch(e){{}}}})();</script>
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{robots}<link rel="icon" type="image/png" href="{up}favicon.png">
<link rel="apple-touch-icon" href="{up}apple-touch-icon.png">
<link rel="preload" as="font" type="font/woff2" href="{up}fonts/nsd-devanagari-400.woff2" crossorigin>
<link rel="stylesheet" href="{up}style.css?v={self.assets.css_version}">
{og}{extra_head}<script src="{up}ui.js?v={self.assets.ui_version}" defer></script>
</head>
<body>
<div id="prog" class="prog"></div>
<header class="site">
  <a class="brand" href="{up or './'}"><span>{SITE_NAME}</span></a>
  <nav>{nav}<button id="themed" class="themebtn" type="button" aria-label="उज्यालो/अँध्यारो"></button></nav>
</header>
<main>
{body}
</main>
<footer class="site">
  <p>{SITE_NAME} — {SITE_TAGLINE}. सार्वजनिक डोमेन।</p>
  <p class="foot-en">{SITE_TAGLINE_EN}</p>
</footer>
</body>
</html>
"""
