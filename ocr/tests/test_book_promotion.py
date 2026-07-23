#!/usr/bin/env python3
"""Plain-assert integration test for Gate-2 exact-path promotion."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from archive_ocr.book_cli import _json_value
from archive_ocr.book_graph import (
    ApprovedStructurePlan, PlannedSection, PlannedWork, QAReport, advance_after_qa,
)
from archive_ocr.book_promotion import PromotionError, verify_stage
from archive_ocr.book_journal import load_journal, write_journal
from archive_ocr.book_promotion_guard import (
    _prepare_journal,
    promote,
    recover_promotion,
)
from archive_ocr.book_workflow import (
    ApprovalGate,
    BookWorkflow,
    StageEntry,
    StageManifest,
    TaskRole,
    sha256_file,
)


PROJECT = Path(__file__).resolve().parents[2]


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.strip()


def complete(workflow: BookWorkflow, run_id: str, node_id: str, artifact=None) -> None:
    result = None
    node = workflow.load_run(run_id).nodes[node_id]
    task = node.task
    if artifact is None and task is not None:
        pages = [int(page) for page in task.inputs.get("pages", [1])]
        base = {"contract_version": "book-agent/v1", "task_id": task.id, "source_pages": pages, "evidence": [], "uncertainties": []}
        if node.role == TaskRole.structure:
            result = {**base, "role": "structure", "pages": [{"page": page, "kind": "literary_content", "action": "include", "reason": "fixture"} for page in pages], "sections": [], "printed_to_pdf_offset_notes": []}
        elif node.role == TaskRole.folio:
            result = {**base, "role": "folio", "folios": [{"pdf_page": page, "printed_label": str(page), "state": "normal", "header_text": None, "footer_text": None} for page in pages], "anomalies": []}
        elif node.role == TaskRole.dedupe:
            result = {**base, "role": "dedupe", "decisions": [{"proposed_section_id": "section_one", "action": "new", "matches": [], "reason": "fixture"}]}
        elif node.role == TaskRole.merge_structure:
            run = workflow.load_run(run_id)
            result = ApprovedStructurePlan(run_id=run_id, source_sha256=run.source_sha256, author_id=run.author_id, works=[PlannedWork(id="new_work", title_printed="नयाँ कृति", genre="kavita", source_pdf_target="archives/authors/known_author/new_work/new_work.pdf")], sections=[PlannedSection(id="section_one", work_id="new_work", title_printed="नयाँ कृति", start_page=1, end_page=1)], retained_book_target="archives/authors/known_author/_source_books/original.pdf")
    claim = workflow.claim_task(run_id, node_id, "fixture")
    workflow.complete_task(
        run_id,
        node_id,
        claim.claim_token,
        artifact_path=artifact,
        result=result,
    )


def metadata() -> dict:
    return {
        "id": "new_work",
        "title": "नयाँ कृति",
        "author": {
            "id": "known_author",
            "name": "ज्ञात लेखक",
            "name_roman": "Known Author",
        },
        "language": "ne",
        "script": "Devanagari",
        "genre": ["kavita"],
        "rights": {
            "status": "public-domain",
            "basis": "Fixture public-domain basis.",
        },
        "source": {
            "name": "Fixture scan",
            "url": None,
            "pdf": "new_work.pdf",
            "html": None,
        },
        "text": {
            "extraction_method": "ocr",
            "ocr_status": "ocr-done",
            "proofread": False,
            "quality": "good",
        },
        "formats": {
            "pdf": "new_work.pdf",
            "txt": "text.txt",
            "html": None,
            "epub": None,
        },
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="book-promotion-test-") as temp:
        repo = Path(temp) / "repo"
        (repo / "pipeline").mkdir(parents=True)
        shutil.copy2(PROJECT / "pipeline" / "validate.py", repo / "pipeline")
        shutil.copy2(PROJECT / "metadata.schema.json", repo)
        existing = (
            repo
            / "archives"
            / "authors"
            / "known_author"
            / "existing_work"
        )
        existing.mkdir(parents=True)
        (existing / "metadata.json").write_text(
            json.dumps(
                {
                    **metadata(),
                    "id": "existing_work",
                    "title": "पुरानो कृति",
                    "source": {
                        "name": "Fixture",
                        "url": "https://example.invalid/source",
                        "pdf": None,
                        "html": None,
                    },
                    "formats": {
                        "pdf": None,
                        "txt": "text.txt",
                        "html": None,
                        "epub": None,
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (existing / "text.txt").write_text("पुरानो पाठ\n", encoding="utf-8")
        source = repo / "incoming.pdf"
        source.write_bytes(b"%PDF-1.4\nfixture\n%%EOF\n")
        unrelated = repo / "notes.txt"
        unrelated.write_text("baseline\n", encoding="utf-8")

        git(repo, "init", "-q")
        git(repo, "config", "user.name", "OCR Fixture")
        git(repo, "config", "user.email", "ocr@example.invalid")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "fixture baseline")
        baseline = git(repo, "rev-parse", "HEAD")
        unrelated.write_text("unrelated dirty work\n", encoding="utf-8")

        jobs_root = repo / "ocr-jobs"
        job = jobs_root / "fixture-job"
        (job / "pages").mkdir(parents=True)
        (job / "ocr" / "ensemble").mkdir(parents=True)
        (job / "source.pdf").write_bytes(source.read_bytes())
        (job / "pages" / "pg-001.png").write_bytes(b"png")
        (job / "ocr" / "ensemble" / "pg-001.txt").write_text("पाठ\n", encoding="utf-8")
        (job / "ocr" / "ensemble" / "review.json").write_text("{}\n", encoding="utf-8")
        (job / "job.json").write_text(json.dumps({"id": "fixture-job", "source_name": source.name, "status": "done", "engines": ["ensemble"], "dpi": 300, "page_count": 1, "runs": [{"engine": "ensemble", "pages_done": 1, "seconds": 1.0, "error": None}]}), encoding="utf-8")
        workflow = BookWorkflow(
            repo, repo / ".ocr-work" / "book-runs", jobs_root
        )
        run = workflow.create_run(source, "known_author", run_id="promotion-run")
        complete(workflow, run.id, "preflight")
        workflow.set_ocr_job(run.id, "fixture-job")
        complete(workflow, run.id, "ocr")
        for node_id in ("plan_structure", "plan_folios", "plan_dedupe"):
            complete(workflow, run.id, node_id)
        complete(workflow, run.id, "merge_structure")
        merged = workflow.load_run(run.id).nodes["merge_structure"]
        structure = workflow.run_dir(run.id) / merged.artifact_path
        workflow.approve_artifact(
            run.id,
            ApprovalGate.structure,
            structure,
            sha256_file(structure),
            "fixture-human",
        )

        # This integration fixture needs only the post-QA tail; graph expansion
        # itself is covered by test_book_workflow.py.
        from archive_ocr.book_workflow import Node, NodeKind, Task, TaskRole

        qa_task = Task(
            id="qa_0", node_id="qa_0", role=TaskRole.qa, summary="fixture QA", inputs={"round": 0}
        )
        workflow.add_nodes(
            run.id,
            [
                Node(
                    id="qa_0",
                    kind=NodeKind.coordinator,
                    role=TaskRole.qa,
                    depends_on=["approve_structure"],
                    task=qa_task,
                )
            ],
        )
        qa = QAReport(
            run_id=run.id,
            round=0,
            issues=[],
            deterministic_checks_passed=True,
            ready_to_stage=True,
        )
        qa_path = workflow.write_artifact(run.id, "artifacts/qa-0.json", qa)
        complete(workflow, run.id, "qa_0", qa_path)
        advance_after_qa(workflow, run.id, qa_path)

        stage_root = workflow.run_dir(run.id) / "stage"
        targets = {
            "archives/authors/known_author/new_work/metadata.json": (
                json.dumps(metadata(), ensure_ascii=False, indent=2) + "\n"
            ).encode(),
            "archives/authors/known_author/new_work/text.txt": "नयाँ विश्वसनीय पाठ\n".encode(),
            "archives/authors/known_author/new_work/new_work.pdf": b"%PDF-1.4\nslice\n%%EOF\n",
            "archives/authors/known_author/_source_books/original.pdf": source.read_bytes(),
            "archives/authors/known_author/existing_work/text.txt": (
                "सच्याइएको पुरानो पाठ\n".encode()
            ),
        }
        entries = []
        for target, content in targets.items():
            staged = stage_root / target
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(content)
            canonical = repo / target
            operation = "update" if canonical.is_file() else "create"
            entries.append(
                StageEntry(
                    staged_path=(Path("stage") / target).as_posix(),
                    target_path=target,
                    sha256=sha256_file(staged),
                    operation=operation,
                    prior_sha256=(
                        sha256_file(canonical) if operation == "update" else None
                    ),
                )
            )
        manifest = StageManifest(
            run_id=run.id,
            source_sha256=run.source_sha256,
            base_commit=baseline,
            entries=entries,
            retained_book_scan=(
                "archives/authors/known_author/_source_books/original.pdf"
            ),
            commit_message="Add fixture scanned book",
        )
        manifest_path = workflow.write_artifact(
            run.id, "artifacts/staging-manifest.json", manifest
        )
        verified = verify_stage(
            workflow, run.id, manifest_path, require_approval=False
        )
        assert len(verified.target_files) == 5
        json.dumps(_json_value(verified))
        complete(workflow, run.id, "stage", manifest_path)
        workflow.approve_artifact(
            run.id,
            ApprovalGate.promotion,
            manifest_path,
            sha256_file(manifest_path),
            "fixture-human",
        )
        run_root = workflow.run_dir(run.id)
        prepared = _prepare_journal(workflow, verified)
        poisoned_target = json.loads(json.dumps(prepared))
        poisoned_target["entries"][0]["target_path"] = "notes.txt"
        write_journal(run_root, poisoned_target)
        try:
            recover_promotion(workflow, run.id, manifest_path)
        except PromotionError:
            pass
        else:
            raise AssertionError("recovery trusted a journal target path")
        assert unrelated.read_text(encoding="utf-8") == "unrelated dirty work\n"

        prepared = _prepare_journal(workflow, verified)
        poisoned_backup = json.loads(json.dumps(prepared))
        update_item = next(
            item
            for item in poisoned_backup["entries"]
            if item["prior_sha256"] is not None
        )
        update_item["backup_path"] = str(
            run_root / "promotion-backup" / ".." / ".." / "notes.txt"
        )
        original_existing = (existing / "text.txt").read_bytes()
        for staged, target in zip(
            verified.staged_files, verified.target_files, strict=True
        ):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged, target)
        git(repo, "add", "--", *targets)
        write_journal(run_root, poisoned_backup)
        try:
            recover_promotion(workflow, run.id, manifest_path)
        except PromotionError:
            pass
        else:
            raise AssertionError("recovery trusted a journal backup path")
        assert (existing / "text.txt").read_bytes() == targets[
            "archives/authors/known_author/existing_work/text.txt"
        ]
        assert set(
            git(repo, "diff", "--cached", "--name-only").splitlines()
        ) == set(targets)

        write_journal(run_root, prepared)
        recovered = recover_promotion(workflow, run.id, manifest_path)
        assert recovered == {"run_id": run.id, "recovered": "rolled_back"}
        assert (existing / "text.txt").read_bytes() == original_existing

        claim = workflow.claim_task(run.id, "promote", "coordinator")
        result = promote(
            workflow, run.id, manifest_path, claim.claim_token
        )

        json.dumps(_json_value(result))
        assert result.commit_sha == git(repo, "rev-parse", "HEAD")
        assert git(repo, "status", "--porcelain", "--", "notes.txt")
        assert unrelated.read_text(encoding="utf-8") == "unrelated dirty work\n"
        changed = set(git(repo, "show", "--pretty=", "--name-only", "HEAD").splitlines())
        assert changed == set(targets)
        final = workflow.load_run(run.id)
        assert final.commit_sha == result.commit_sha
        assert final.status.value == "completed"
        assert load_journal(workflow.run_dir(run.id))["phase"] == "recorded"
        assert not (repo / ".git" / "refs" / "remotes").exists()

    print("OK: Gate-2 promotion integration spec passes")


if __name__ == "__main__":
    main()
