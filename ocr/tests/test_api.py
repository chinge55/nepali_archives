#!/usr/bin/env python3
"""API contract spec — the routes must behave identically for ANY engine
name, and failure paths must fail loudly with the right status codes.

Run: ~/miniconda3/envs/ocr_env/bin/python ocr/tests/test_api.py
(needs fastapi; uses an isolated temp work dir, touches no real jobs).
"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["OCR_WORK_DIR"] = tempfile.mkdtemp(prefix="ocr-api-test-")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from archive_ocr.server import app

client = TestClient(app)
bad = []


def check(cond, msg):
    if not cond:
        bad.append(msg)


# health names every registered engine and never 500s
r = client.get("/health")
check(r.status_code == 200, f"health status {r.status_code}")
check(set(r.json()["engines"]) >= {"tesseract", "surya", "ensemble"},
      f"health engines: {list(r.json()['engines'])}")

# unknown engine is rejected before anything is written
r = client.post("/jobs", files={"file": ("x.pdf", b"%PDF-1.4 junk")},
                data={"engines": "gpt9000"})
check(r.status_code == 422, f"unknown engine -> 422, got {r.status_code}")
check(client.get("/jobs").json() == [], "rejected submit must write nothing")

# a corrupt PDF becomes a FAILED job (never a hung or lying one)
r = client.post("/jobs", files={"file": ("broken.pdf", b"not a pdf at all")},
                data={"engines": "tesseract"})
check(r.status_code == 201, f"submit status {r.status_code}")
job_id = r.json()["id"]
for _ in range(50):
    job = client.get(f"/jobs/{job_id}").json()
    if job["status"] in ("done", "failed"):
        break
    time.sleep(0.2)
check(job["status"] == "failed", f"corrupt pdf must fail, got {job['status']}")
check(job["error"], "failed job must carry an error message")

# 404 semantics are uniform across engine names (the engine-agnostic contract)
check(client.get("/jobs/does-not-exist").status_code == 404, "missing job 404")
for engine in ("tesseract", "surya", "ensemble"):
    r = client.get(f"/jobs/{job_id}/text", params={"engine": engine})
    check(r.status_code == 404, f"no output ({engine}) -> 404, got {r.status_code}")
    r = client.get(f"/jobs/{job_id}/pages/1", params={"engine": engine})
    check(r.status_code == 404, f"no page ({engine}) -> 404, got {r.status_code}")
check(client.get(f"/jobs/{job_id}/review").status_code == 404,
      "no review.json -> 404")

if bad:
    print("FAIL")
    for b in bad:
        print(" ", b)
    raise SystemExit(1)
print("OK: api spec passes")
