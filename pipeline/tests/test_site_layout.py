import sys
import tempfile
import unittest
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE))

from sitegen.assets import AssetBundle, asset_version
from sitegen.context import BuildContext
from sitegen.layout import PageRenderer
from sitegen.pages.ocr import write_ocr_page


ROOT = PIPELINE.parent
ASSETS = AssetBundle.load(ROOT)
PAGE = PageRenderer(ASSETS)


class LayoutTests(unittest.TestCase):
    def test_depth_controls_relative_assets_and_navigation(self):
        rendered = PAGE(
            "शीर्षक", "<p>पाठ</p>", css_depth=3, active="works",
            canon="authors/example/work/",
        )
        self.assertIn('href="../../../style.css?v=', rendered)
        self.assertIn('src="../../../ui.js?v=', rendered)
        self.assertIn('href="../../../authors/" class=on', rendered)

    def test_canonical_and_open_graph_urls_match(self):
        rendered = PAGE(
            "शीर्षक", "", canon="authors/example/work/"
        )
        url = "https://www.nepaliarchives.org/authors/example/work/"
        self.assertIn(f'<link rel="canonical" href="{url}">', rendered)
        self.assertIn(f'<meta property="og:url" content="{url}">', rendered)

    def test_noindex_and_extra_head_are_preserved(self):
        rendered = PAGE(
            "PDF", "", noindex=True, extra_head="<meta name=test>\n"
        )
        self.assertIn('<meta name="robots" content="noindex,follow">', rendered)
        self.assertIn("<meta name=test>", rendered)

    def test_asset_version_changes_with_content(self):
        self.assertEqual(asset_version("same"), asset_version("same"))
        self.assertNotEqual(asset_version("one"), asset_version("two"))

    def test_ocr_source_link_is_safe(self):
        with tempfile.TemporaryDirectory() as td:
            context = BuildContext.for_root(ROOT, output_dir=Path(td))
            write_ocr_page(context, PAGE)
            rendered = (context.site / "ocr" / "index.html").read_text(
                encoding="utf-8"
            )
        self.assertIn("docs/ocr-workflow.md", rendered)
        self.assertIn('target="_blank" rel="noopener"', rendered)


if __name__ == "__main__":
    unittest.main()
