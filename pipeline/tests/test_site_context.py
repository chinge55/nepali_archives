import tempfile
import sys
import unittest
from datetime import date
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE))

from sitegen.context import BuildContext, output_manifest


class BuildContextTests(unittest.TestCase):
    def test_context_resolves_paths_and_injected_date(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "preview"
            ctx = BuildContext.for_root(
                root,
                output_dir=output,
                archive_base="https://archive.example",
                build_date=date(2026, 8, 13),
            )
            self.assertEqual(ctx.root, root.resolve())
            self.assertEqual(ctx.archives, root.resolve() / "archives")
            self.assertEqual(ctx.site, output.resolve())
            self.assertEqual(ctx.build_date, date(2026, 8, 13))

    def test_output_manifest_ignores_creation_order(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "b").write_text("दुई", encoding="utf-8")
            (root / "a").write_text("एक", encoding="utf-8")
            first = output_manifest(root)
            (root / "a").unlink()
            (root / "a").write_text("एक", encoding="utf-8")
            second = output_manifest(root)
            self.assertEqual(first, second)
            self.assertEqual([row["path"] for row in first.files], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
