"""CLI entry points.

    python -m archive_ocr serve [--port 8100]
    python -m archive_ocr run book.pdf [--engines ensemble] [--first N --last M]
    python -m archive_ocr health
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="archive_ocr")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="start the FastAPI server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8100)

    run = sub.add_parser("run", help="run a job locally, wait, print summary")
    run.add_argument("pdf", type=Path)
    run.add_argument("--engines", default="ensemble")
    run.add_argument("--dpi", type=int, default=None)
    run.add_argument("--first", type=int, default=None)
    run.add_argument("--last", type=int, default=None)

    sub.add_parser("health", help="report engine availability")
    book = sub.add_parser("book", help="manage resumable scanned-book workflows")
    from .book_cli import configure_parser
    configure_parser(book)

    args = parser.parse_args()

    if args.command == "serve":
        import uvicorn
        uvicorn.run("archive_ocr.server:app", host=args.host, port=args.port)

    elif args.command == "health":
        from .engines import ENGINES
        for name, engine in ENGINES.items():
            ok, detail = engine.available()
            print(f"{'OK ' if ok else '-- '} {name}: {detail}")
        sys.exit(0 if any(e.available()[0] for e in ENGINES.values()) else 1)

    elif args.command == "run":
        from . import jobs, storage
        job = jobs.submit(args.pdf.read_bytes(), args.pdf.name,
                          [e.strip() for e in args.engines.split(",")],
                          args.dpi, args.first, args.last)
        print(f"job {job.id} submitted; waiting…")
        while True:
            time.sleep(2)
            job = storage.load_job(job.id)
            assert job is not None
            if job.status in ("done", "failed"):
                break
        print(json.dumps(job.model_dump(mode="json"), indent=2, ensure_ascii=False))
        print(f"artifacts: {storage.job_dir(job.id)}")
        sys.exit(0 if job.status == "done" else 1)

    elif args.command == "book":
        from .book_cli import run as run_book_command
        sys.exit(run_book_command(args))


if __name__ == "__main__":
    main()
