#!/usr/bin/env python3
"""Storage layer spec: ids, persistence roundtrip, page-number padding.

Run: python3 ocr/tests/test_storage.py (uses an isolated temp work dir).
"""
import os
import re
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="ocr-test-")
os.environ["OCR_WORK_DIR"] = _tmp                     # before package import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from archive_ocr import storage
from archive_ocr.models import EngineRun, Job, JobStatus

bad = []


def check(cond, msg):
    if not cond:
        bad.append(msg)


# ids: readable slug + entropy, always filesystem-safe
jid = storage.new_job_id("LaxmiPrasadDevkota2028BS_Prometheus.pdf")
check(re.fullmatch(r"[a-z0-9-]+", jid), f"id charset: {jid}")
check(jid.startswith("laxmiprasaddevkota2028bs-prometheus-"), f"id slug: {jid}")
check(storage.new_job_id("॥॥.pdf").startswith("job-"), "degenerate name falls back")

# persistence: what we save is exactly what we load
job = Job(id=jid, source_name="x.pdf", engines=["tesseract"], dpi=300,
          status=JobStatus.running, runs=[EngineRun(engine="tesseract", seconds=1.5)])
storage.job_dir(jid).mkdir(parents=True)
storage.save_job(job)
loaded = storage.load_job(jid)
check(loaded == job, "save/load roundtrip must be identity")
check(storage.load_job("nope") is None, "missing job loads as None")

# page files: pdftoppm pads to 2 digits (<100 pp) or 3 digits (>=100 pp) —
# page_text must find both
d = storage.engine_dir(jid, "tesseract")
d.mkdir(parents=True)
(d / "pg-07.txt").write_text("two-digit", encoding="utf-8")
(d / "pg-107.txt").write_text("three-digit", encoding="utf-8")
check(storage.page_text(jid, "tesseract", 7) == "two-digit", "2-digit padding")
check(storage.page_text(jid, "tesseract", 107) == "three-digit", "3-digit padding")
check(storage.page_text(jid, "tesseract", 8) is None, "missing page is None")
check(storage.engine_page_numbers(jid, "tesseract") == [7, 107], "page listing")

if bad:
    print("FAIL")
    for b in bad:
        print(" ", b)
    raise SystemExit(1)
print("OK: storage spec passes")
