import json
from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_patro_coverage import coverage


class CalendarCoverageTests(unittest.TestCase):
    def test_counts_contiguous_dates_and_does_not_skip_a_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            content = Path(directory)
            (content / "panchanga-2026-10.json").write_text(json.dumps({"days": {
                "2026-10-30": {"ad": "2026-10-30"}, "2026-10-31": {"ad": "2026-10-31"},
            }}))
            (content / "panchanga-2026-11.json").write_text(json.dumps({"days": {
                "2026-11-01": {"ad": "2026-11-01"}, "2026-11-03": {"ad": "2026-11-03"},
            }}))
            self.assertEqual(coverage(content, date(2026, 10, 30)), date(2026, 11, 1))
            self.assertIsNone(coverage(content, date(2026, 11, 2)))

    def test_rejects_data_labelled_with_the_wrong_date(self):
        with tempfile.TemporaryDirectory() as directory:
            content = Path(directory)
            (content / "panchanga-2026-10.json").write_text(json.dumps({"days": {
                "2026-10-30": {"ad": "2026-10-29"},
            }}))
            with self.assertRaisesRegex(ValueError, "date mismatch"):
                coverage(content, date(2026, 10, 30))
