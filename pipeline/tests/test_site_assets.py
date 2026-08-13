import sys
import tempfile
import unittest
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[1]
ROOT = PIPELINE.parent
sys.path.insert(0, str(PIPELINE))

from sitegen.assets import AssetBundle, install_common_assets
from sitegen.context import BuildContext


class AssetInstallationTests(unittest.TestCase):
    def test_missing_optional_assets_do_not_break_common_install(self):
        with tempfile.TemporaryDirectory() as td:
            temporary_root = Path(td)
            context = BuildContext.for_root(temporary_root)
            assets = AssetBundle.load(ROOT)
            install_common_assets(context, assets)
            self.assertTrue((context.site / "style.css").is_file())
            self.assertTrue((context.site / "search.js").is_file())
            self.assertTrue((context.site / "ui.js").is_file())
            self.assertFalse((context.site / "pdfjs").exists())


if __name__ == "__main__":
    unittest.main()
