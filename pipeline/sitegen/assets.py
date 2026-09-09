"""Tracked web assets, content hashes, and common-site asset installation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil

from .config import GENRE
from .context import BuildContext


def asset_version(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:8]


@dataclass(frozen=True)
class AssetBundle:
    css: str
    search_js: str
    ui_js: str
    type_css: str
    patro_css: str
    patro_js: str
    pdf_reader_css: str
    pdf_reader_js: str

    @classmethod
    def load(cls, root: Path) -> "AssetBundle":
        source = Path(root) / "assets" / "site"

        def read(name: str) -> str:
            return (source / name).read_text(encoding="utf-8")

        search_js = read("search.js").replace(
            "__GENRE_MAP__",
            json.dumps(
                {genre: labels[0] for genre, labels in GENRE.items()},
                ensure_ascii=False,
            ),
        )
        return cls(
            css=read("style.css"),
            search_js=search_js,
            ui_js=read("ui.js"),
            type_css=read("type.css"),
            patro_css=read("patro.css"),
            patro_js=read("patro.js"),
            pdf_reader_css=read("pdf-reader.css"),
            pdf_reader_js=read("pdf-reader.js"),
        )

    @property
    def css_version(self) -> str:
        return asset_version(self.css)

    @property
    def search_version(self) -> str:
        return asset_version(self.search_js)

    @property
    def ui_version(self) -> str:
        return asset_version(self.ui_js)


def install_common_assets(context: BuildContext, assets: AssetBundle) -> None:
    """Create the output root and install assets shared by generated pages."""
    root, site = context.root, context.site
    if site.exists():
        shutil.rmtree(site)
    site.mkdir(parents=True)

    font_face = root / "assets" / "fonts" / "fontface.css"
    css = (
        font_face.read_text(encoding="utf-8") + "\n" + assets.css
        if font_face.exists()
        else assets.css
    )
    (site / "style.css").write_text(css, encoding="utf-8")
    (site / "search.js").write_text(assets.search_js, encoding="utf-8")
    (site / "ui.js").write_text(assets.ui_js, encoding="utf-8")

    verification = root / "assets" / "BingSiteAuth.xml"
    if verification.exists():
        shutil.copyfile(verification, site / verification.name)

    font_dir = site / "fonts"
    font_dir.mkdir(exist_ok=True)
    for source in sorted((root / "assets" / "fonts").glob("*.woff2")):
        shutil.copy(source, font_dir / source.name)

    copyright_act = root / "Pratilipi Adhikar Ain_2059(1)_1573120368.pdf"
    if copyright_act.exists():
        (site / "docs").mkdir(exist_ok=True)
        shutil.copy(
            copyright_act,
            site / "docs" / "pratilipi-adhikar-ain-2059.pdf",
        )

    logo = root / "assets" / "logo"
    for source_name, output_name in [
        ("favicon-48.png", "favicon.png"),
        ("favicon-180.png", "apple-touch-icon.png"),
        ("final-logo.png", "logo.png"),
        ("logo-pressed.png", "logo-pressed.png"),
        ("final-logo-dark.png", "logo-dark.png"),
        ("logo-pressed-dark.png", "logo-pressed-dark.png"),
        ("hover-mark.svg", "logo-hover-mark.svg"),
        ("hover-book.svg", "logo-hover-book.svg"),
    ]:
        source = logo / source_name
        if source.exists():
            shutil.copy(source, site / output_name)

    pdfjs = root / "assets" / "pdfjs"
    if pdfjs.exists():
        output = site / "pdfjs"
        output.mkdir(exist_ok=True)
        for source in pdfjs.iterdir():
            if source.is_file():
                shutil.copy(source, output / source.name)
