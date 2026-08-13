import sys
import tempfile
import unittest
from pathlib import Path


PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE))

from check_site_links import find_broken_links


class InternalLinkTests(unittest.TestCase):
    def test_accepts_files_directories_fragments_and_external_links(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td)
            (site / "nested").mkdir()
            (site / "nested" / "index.html").write_text(
                '<a href="../">home</a><a href="#part">part</a>',
                encoding="utf-8",
            )
            (site / "index.html").write_text(
                '<a href="nested/">nested</a>'
                '<a href="https://example.org/">external</a>',
                encoding="utf-8",
            )
            self.assertEqual(find_broken_links(site), [])

    def test_reports_missing_and_escaping_links(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td)
            (site / "index.html").write_text(
                '<a href="missing/">missing</a>'
                '<img src="../outside.png">',
                encoding="utf-8",
            )
            problems = find_broken_links(site)
            self.assertEqual(len(problems), 2)
            self.assertTrue(any("missing" in problem for problem in problems))
            self.assertTrue(any("escapes site" in problem for problem in problems))


if __name__ == "__main__":
    unittest.main()
