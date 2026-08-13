#!/usr/bin/env python3
"""Plain-assert regression spec for the scanned-book workflow graph."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from archive_ocr.agent_profiles import FAST_READER, STRONG_READER, active_profile_name
from archive_ocr.book_graph import (
    ApprovedStructurePlan,
    PlannedSection,
    PlannedWork,
    QAReport,
    QAIssue,
    advance_after_qa,
    expand_approved_plan,
)
from archive_ocr.book_packets import build_task_packet
from archive_ocr.book_workflow import (
    ApprovalGate,
    ArtifactMismatch,
    BookRun,
    BookWorkflow,
    InvalidTransition,
    Node,
    NodeKind,
    NodeStatus,
    RunStatus,
    StageEntry,
    StageManifest,
    Task,
    TaskRole,
    WorkflowError,
    sha256_file,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
BASE_COMMIT = "c" * 40


@contextmanager
def expect(exception):
    try:
        yield
    except exception:
        return
    raise AssertionError(f"expected {exception.__name__}")


def make_workflow(root: Path) -> tuple[BookWorkflow, Path]:
    repo = root / "repo"
    metadata = (
        repo
        / "archives"
        / "authors"
        / "known_author"
        / "existing_work"
        / "metadata.json"
    )
    metadata.parent.mkdir(parents=True)
    metadata.write_text(
        json.dumps({"author": {"id": "known_author"}}),
        encoding="utf-8",
    )
    source = repo / "incoming" / "book.pdf"
    source.parent.mkdir()
    source.write_bytes(b"%PDF-1.4\nisolated workflow fixture\n%%EOF\n")
    jobs_root = repo / "ocr-jobs"
    job = jobs_root / "fixture-job"
    (job / "pages").mkdir(parents=True)
    (job / "ocr" / "ensemble").mkdir(parents=True)
    (job / "source.pdf").write_bytes(source.read_bytes())
    for page in range(1, 9):
        stem = f"pg-{page:03d}"
        (job / "pages" / f"{stem}.png").write_bytes(b"png")
        (job / "ocr" / "ensemble" / f"{stem}.txt").write_text(
            "परीक्षण पाठ\n", encoding="utf-8"
        )
    (job / "ocr" / "ensemble" / "review.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (job / "job.json").write_text(json.dumps({
        "id": "fixture-job", "source_name": source.name, "status": "done",
        "engines": ["ensemble"], "dpi": 300, "page_count": 8,
        "runs": [{"engine": "ensemble", "pages_done": 8, "seconds": 1.0, "error": None}],
    }), encoding="utf-8")
    workflow = BookWorkflow(
        repo_root=repo,
        work_root=repo / ".ocr-work" / "book-runs",
        ocr_jobs_root=jobs_root,
    )
    return workflow, source


def fixture_result(workflow: BookWorkflow, run_id: str, node_id: str):
    node = workflow.load_run(run_id).nodes[node_id]
    task = node.task
    if task is None or node.role in {TaskRole.preflight, TaskRole.ocr}:
        return None
    pages = [int(page) for page in task.inputs.get("pages", [1])]
    base = {
        "contract_version": "book-agent/v1", "task_id": task.id,
        "role": {
            TaskRole.structure: "structure", TaskRole.folio: "folio",
            TaskRole.dedupe: "dedupe", TaskRole.reconcile: "section_reconciler",
            TaskRole.footnote: "footnote_sweep", TaskRole.verify: "targeted_verifier",
        }.get(node.role),
        "source_pages": pages, "evidence": [], "uncertainties": [],
    }
    if node.role == TaskRole.structure:
        base.update({"pages": [{"page": page, "kind": "literary_content", "action": "include", "reason": "fixture"} for page in pages], "sections": [], "printed_to_pdf_offset_notes": []})
    elif node.role == TaskRole.folio:
        base.update({"folios": [{"pdf_page": page, "printed_label": str(page), "state": "normal", "header_text": None, "footer_text": None} for page in pages], "anomalies": []})
    elif node.role == TaskRole.dedupe:
        base.update({"decisions": [{"proposed_section_id": "section_one", "action": "new", "matches": [], "reason": "fixture"}]})
    elif node.role == TaskRole.reconcile:
        base.update({"section_id": task.inputs["section_id"], "title_printed": task.inputs["title_printed"], "text": "विश्वसनीय पाठ", "numbering_mode": "none", "numbering": [], "footnotes": [], "resolved_disagreement_ids": []})
    elif node.role == TaskRole.footnote:
        base.update({"pages": [{"page": page, "findings": [], "continuation_or_marginalia": None} for page in pages]})
    elif node.role == TaskRole.verify:
        base.update({"issues": [{"issue_id": issue_id, "verdict": "source_correct", "explanation": "fixture", "replacement_text": None, "page": pages[0]} for issue_id in task.inputs["issue_ids"]]})
    else:
        return None
    return base


def complete(workflow: BookWorkflow, run_id: str, node_id: str, result=None):
    if result is None:
        result = fixture_result(workflow, run_id, node_id)
    claim = workflow.claim_task(run_id, node_id, "test-worker")
    return workflow.complete_task(
        run_id,
        node_id,
        claim.claim_token,
        result=result,
    )


def complete_initial_planning(workflow: BookWorkflow, run_id: str) -> None:
    complete(workflow, run_id, "preflight")
    workflow.set_ocr_job(run_id, "fixture-job")
    complete(workflow, run_id, "ocr")
    assert {task.id for task in workflow.ready_tasks(run_id)} == {
        "plan_structure",
        "plan_folios",
        "plan_dedupe",
    }
    for node_id in ("plan_structure", "plan_folios", "plan_dedupe"):
        complete(workflow, run_id, node_id)
    complete(workflow, run_id, "merge_structure", structure_plan(run_id, workflow.load_run(run_id).source_sha256))


def structure_plan(run_id: str, source_sha256: str) -> ApprovedStructurePlan:
    return ApprovedStructurePlan(
        run_id=run_id,
        source_sha256=source_sha256,
        author_id="known_author",
        works=[
            PlannedWork(
                id="main_work",
                title_printed="मुख्य कृति",
                genre="kavita",
                source_pdf_target=(
                    "archives/authors/known_author/main_work/extracted.pdf"
                ),
            )
        ],
        sections=[
            PlannedSection(
                id="section_one",
                work_id="main_work",
                title_printed="प्रथम सर्ग",
                start_page=5,
                end_page=8,
            ),
            PlannedSection(
                id="modern_preface",
                work_id="main_work",
                title_printed="सम्पादकीय",
                start_page=1,
                end_page=4,
                include=False,
                exclusion_reason="modern editorial front matter",
            ),
        ],
        retained_book_target=(
            "archives/authors/known_author/original_book/original.pdf"
        ),
    )


def approve_and_expand(
    workflow: BookWorkflow,
    run_id: str,
) -> ApprovedStructurePlan:
    run = workflow.load_run(run_id)
    plan = structure_plan(run_id, run.source_sha256)
    artifact = workflow.run_dir(run_id) / run.nodes["merge_structure"].artifact_path
    expected_hash = sha256_file(artifact)

    with expect(ArtifactMismatch):
        workflow.approve_artifact(
            run_id,
            ApprovalGate.structure,
            artifact,
            SHA_A,
            "human",
        )

    workflow.approve_artifact(
        run_id,
        ApprovalGate.structure,
        artifact,
        expected_hash,
        "human",
    )
    approved_bytes = artifact.read_bytes()
    artifact.write_bytes(approved_bytes + b" ")
    with expect(InvalidTransition):
        expand_approved_plan(workflow, run_id)
    artifact.write_bytes(approved_bytes)

    assert workflow.load_run(run_id).status == RunStatus.active
    expanded = expand_approved_plan(workflow, run_id)
    graph = workflow.load_run(run_id).nodes
    assert expanded == plan
    assert "reconcile_section_one" in graph
    assert "footnotes_section_one" in graph
    assert "reconcile_modern_preface" not in graph
    assert "footnotes_modern_preface" not in graph
    assert graph["reconcile_section_one"].role == TaskRole.reconcile
    assert graph["reconcile_section_one"].task.capability == STRONG_READER
    assert graph["reconcile_section_one"].task.preferred_model is None
    assert graph["footnotes_section_one"].role == TaskRole.footnote
    assert graph["footnotes_section_one"].task.capability == FAST_READER
    assert set(graph["qa_0"].depends_on) == {
        "reconcile_section_one",
        "footnotes_section_one",
    }
    return plan


def test_expand_repairs_qa_after_cascade_reset(root: Path) -> None:
    workflow, source = make_workflow(root)
    run = workflow.create_run(source, "known_author", run_id="repair-expanded")
    complete_initial_planning(workflow, run.id)
    plan = approve_and_expand(workflow, run.id)

    workflow.reset_task(run.id, "reconcile_section_one", cascade=True)
    reset_graph = workflow.load_run(run.id).nodes
    assert "qa_0" not in reset_graph
    assert reset_graph["reconcile_section_one"].status == NodeStatus.pending
    assert reset_graph["footnotes_section_one"].status == NodeStatus.pending

    assert expand_approved_plan(workflow, run.id) == plan
    repaired_graph = workflow.load_run(run.id).nodes
    assert set(repaired_graph["qa_0"].depends_on) == {
        "reconcile_section_one",
        "footnotes_section_one",
    }
    with expect(InvalidTransition):
        expand_approved_plan(workflow, run.id)


def test_expand_accepts_a_legacy_model_pinned_run(root: Path) -> None:
    """A pre-capability run still matches its approved plan after the upgrade.

    Routing is advisory, so a stored task pinned to an old local agent must not
    read as "differs from approved plan" when the graph is rebuilt.
    """
    workflow, source = make_workflow(root)
    run = workflow.create_run(source, "known_author", run_id="legacy-pinned")
    complete_initial_planning(workflow, run.id)
    plan = approve_and_expand(workflow, run.id)
    workflow.reset_task(run.id, "reconcile_section_one", cascade=True)

    # Rewrite state the way the pre-capability code would have persisted it.
    state_path = workflow.run_dir(run.id) / "run.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    legacy = state["nodes"]["reconcile_section_one"]["task"]
    legacy["capability"] = None
    legacy["preferred_model"] = "legacy-strong-model"
    legacy["reasoning_effort"] = "high"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    assert expand_approved_plan(workflow, run.id) == plan
    repaired = workflow.load_run(run.id).nodes
    assert "qa_0" in repaired
    # The legacy pin survives untouched, and still wins at packet time.
    assert repaired["reconcile_section_one"].task.preferred_model == "legacy-strong-model"


def issue(round_number: int) -> QAReport:
    return QAReport(
        run_id="known-run",
        round=round_number,
        issues=[
            QAIssue(
                id=f"numbering_{round_number}",
                category="numbering",
                severity="high",
                pages=[7],
                detail="Printed verse number needs image verification.",
            )
        ],
        deterministic_checks_passed=False,
        ready_to_stage=False,
    )


def finish_qa_round(
    workflow: BookWorkflow,
    run_id: str,
    round_number: int,
) -> Path:
    report = issue(round_number)
    path = workflow.write_artifact(
        run_id,
        f"artifacts/qa-{round_number}.json",
        report,
    )
    claim = workflow.claim_task(run_id, f"qa_{round_number}", "qa-worker")
    workflow.complete_task(
        run_id,
        f"qa_{round_number}",
        claim.claim_token,
        artifact_path=path,
    )
    return path


def test_initial_dag_and_unknown_author(root: Path) -> None:
    workflow, source = make_workflow(root)
    run = workflow.create_run(source, "known_author", run_id="known-run")
    assert run.status == RunStatus.active
    assert run.ocr_job_id == "fixture-job"
    assert [task.id for task in workflow.ready_tasks(run.id)] == ["preflight"]
    assert set(run.nodes) == {
        "preflight",
        "ocr",
        "plan_structure",
        "plan_folios",
        "plan_dedupe",
        "merge_structure",
        "approve_structure",
    }
    assert run.nodes["ocr"].task.inputs["engines"] == ["ensemble"]

    unknown = workflow.create_run(source, "unknown_author", run_id="unknown-run")
    assert unknown.status == RunStatus.blocked
    assert unknown.blocked_reason == "unknown_author"
    assert unknown.nodes["preflight"].status == NodeStatus.blocked
    assert workflow.ready_tasks(unknown.id) == []


def test_packet_uses_validated_custom_ocr_root(root: Path) -> None:
    workflow, source = make_workflow(root)
    run = workflow.create_run(source, "known_author", run_id="packet-run")
    complete(workflow, run.id, "preflight")
    workflow.set_ocr_job(run.id, "fixture-job")
    complete(workflow, run.id, "ocr")
    claim = workflow.claim_task(run.id, "plan_structure", "packet-worker")
    packet = build_task_packet(
        workflow, run.id, "plan_structure", claim.claim_token
    )
    expected_root = workflow.ocr_jobs_root.resolve()
    expected_pages = sorted((expected_root / "fixture-job" / "pages").glob("pg-*.png"))
    assert expected_pages
    for page in expected_pages:
        assert str(page.resolve()) in packet["prompt"]
    assert str(expected_root / "fixture-job" / "ocr" / "ensemble") in packet["prompt"]
    # The packet is where a capability may receive a private local binding.
    assert packet["capability"] == STRONG_READER
    assert packet["agent_profile"] == "ocr_structure"
    assert packet["profile_set"] == active_profile_name()
    assert set(packet) >= {"model", "reasoning_effort", "profile_set", "capability"}
    # A concrete agent ID must never have persisted into run state to get here.
    assert workflow.load_run(run.id).nodes["plan_structure"].task.preferred_model is None


def test_gate_one_expansion_and_two_round_verifier_cap(root: Path) -> None:
    workflow, source = make_workflow(root)
    run = workflow.create_run(source, "known_author", run_id="known-run")
    complete_initial_planning(workflow, run.id)
    approve_and_expand(workflow, run.id)

    complete(workflow, run.id, "reconcile_section_one")
    complete(workflow, run.id, "footnotes_section_one")
    qa0 = finish_qa_round(workflow, run.id, 0)
    advance_after_qa(workflow, run.id, qa0)
    graph = workflow.load_run(run.id).nodes
    assert graph["verify_1"].depends_on == ["qa_0"]
    assert graph["qa_1"].depends_on == ["verify_1"]
    assert graph["verify_1"].task.inputs["pages"] == [7]

    complete(workflow, run.id, "verify_1")
    qa1 = finish_qa_round(workflow, run.id, 1)
    advance_after_qa(workflow, run.id, qa1)
    graph = workflow.load_run(run.id).nodes
    assert graph["verify_2"].depends_on == ["qa_1"]
    assert graph["qa_2"].depends_on == ["verify_2"]

    complete(workflow, run.id, "verify_2")
    qa2 = finish_qa_round(workflow, run.id, 2)
    with expect(InvalidTransition):
        advance_after_qa(workflow, run.id, qa2)
    graph = workflow.load_run(run.id).nodes
    assert "verify_3" not in graph
    assert "qa_3" not in graph


def test_stage_manifest_create_update_and_safe_paths(root: Path) -> None:
    entries = [
        StageEntry(
            staged_path=(
                "stage/archives/authors/known_author/main_work/text.txt"
            ),
            target_path="archives/authors/known_author/main_work/text.txt",
            sha256=SHA_A,
            operation="create",
        ),
        StageEntry(
            staged_path=(
                "stage/archives/authors/known_author/main_work/metadata.json"
            ),
            target_path="archives/authors/known_author/main_work/metadata.json",
            sha256=SHA_B,
            operation="update",
            prior_sha256=SHA_A,
        ),
    ]
    manifest = StageManifest(
        run_id="known-run",
        source_sha256=SHA_A,
        base_commit=BASE_COMMIT,
        entries=entries,
        retained_book_scan=(
            "archives/authors/known_author/original_book/original.pdf"
        ),
        commit_message="Add scanned book sources",
    )
    assert manifest.entries[0].prior_sha256 is None
    assert manifest.entries[1].prior_sha256 == SHA_A

    with expect(ValidationError):
        StageEntry(
            staged_path="stage/file.txt",
            target_path="file.txt",
            sha256=SHA_A,
            operation="create",
            prior_sha256=SHA_B,
        )
    with expect(ValidationError):
        StageEntry(
            staged_path="stage/file.txt",
            target_path="file.txt",
            sha256=SHA_A,
            operation="update",
        )
    with expect(ValidationError):
        StageEntry(
            staged_path="../escape.txt",
            target_path="archives/authors/known_author/work/text.txt",
            sha256=SHA_A,
        )

    workflow, source = make_workflow(root / "paths")
    run = workflow.create_run(source, "known_author", run_id="safe-run")
    with expect(WorkflowError):
        workflow.write_artifact(run.id, "../escape.json", {"unsafe": True})
    outside = root / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")
    with expect(WorkflowError):
        workflow.approve_artifact(
            run.id,
            ApprovalGate.structure,
            outside,
            hashlib.sha256(outside.read_bytes()).hexdigest(),
            "human",
        )


def test_dynamic_nodes_are_pristine_and_promotion_is_canonical(root: Path) -> None:
    workflow, source = make_workflow(root)
    run = workflow.create_run(source, "known_author", run_id="known-run")

    def supplied(node_id: str, role: TaskRole, **changes) -> Node:
        values = {
            "id": node_id,
            "kind": NodeKind.coordinator,
            "role": role,
            "depends_on": ["preflight"],
            "task": Task(
                id=node_id, node_id=node_id, role=role, summary="fixture"
            ),
        }
        values.update(changes)
        return Node(**values)

    for status in (NodeStatus.completed, NodeStatus.skipped, NodeStatus.claimed):
        with expect(InvalidTransition):
            workflow.add_nodes(
                run.id,
                [supplied(f"injected_{status.value}", TaskRole.qa, status=status)],
            )
    with expect(InvalidTransition):
        workflow.add_nodes(
            run.id,
            [supplied(
                "injected_artifact", TaskRole.qa,
                artifact_path="artifact.json", artifact_sha256=SHA_A,
            )],
        )
    with expect(InvalidTransition):
        workflow.add_nodes(
            run.id, [supplied("injected_attempt", TaskRole.qa, attempts=1)]
        )
    with expect(InvalidTransition):
        workflow.add_nodes(run.id, [supplied("promote", TaskRole.qa)])
    with expect(InvalidTransition):
        workflow.add_nodes(
            run.id, [supplied("not_promote", TaskRole.promote)]
        )

    false_complete = run.model_dump(mode="json")
    false_complete["status"] = RunStatus.completed.value
    with expect(ValidationError):
        BookRun.model_validate(false_complete)


def test_artifact_change_blocks_claim_approval_and_advancement(root: Path) -> None:
    workflow, source = make_workflow(root / "claim")
    run = workflow.create_run(source, "known_author", run_id="known-run")
    complete(workflow, run.id, "preflight")
    workflow.set_ocr_job(run.id, "fixture-job")
    complete(workflow, run.id, "ocr")
    complete(workflow, run.id, "plan_structure")
    active_claim = workflow.claim_task(run.id, "plan_folios", "test-worker")
    structure_node = workflow.load_run(run.id).nodes["plan_structure"]
    structure_artifact = workflow.run_dir(run.id) / structure_node.artifact_path
    structure_artifact.write_bytes(structure_artifact.read_bytes() + b" ")

    with expect(InvalidTransition):
        workflow.complete_task(
            run.id, "plan_folios", active_claim.claim_token,
            result=fixture_result(workflow, run.id, "plan_folios"),
        )
    blocked = workflow.status(run.id)
    assert blocked.status == RunStatus.blocked
    assert blocked.blocked_reason == "artifact_changed:plan_structure"
    assert blocked.ready_nodes == []
    with expect(InvalidTransition):
        workflow.claim_task(run.id, "plan_dedupe", "test-worker")
    with expect(InvalidTransition):
        workflow.add_nodes(
            run.id,
            [Node(
                id="downstream", kind=NodeKind.coordinator, role=TaskRole.qa,
                depends_on=["ocr"],
                task=Task(
                    id="downstream", node_id="downstream", role=TaskRole.qa,
                    summary="must not be added after an integrity block",
                ),
            )],
        )

    approval_workflow, approval_source = make_workflow(root / "approval")
    approval_run = approval_workflow.create_run(
        approval_source, "known_author", run_id="approval-run"
    )
    complete_initial_planning(approval_workflow, approval_run.id)
    current = approval_workflow.load_run(approval_run.id)
    changed_node = current.nodes["plan_structure"]
    changed_path = (
        approval_workflow.run_dir(approval_run.id) / changed_node.artifact_path
    )
    changed_path.write_bytes(changed_path.read_bytes() + b" ")
    merge_node = current.nodes["merge_structure"]
    merge_path = (
        approval_workflow.run_dir(approval_run.id) / merge_node.artifact_path
    )
    with expect(InvalidTransition):
        approval_workflow.approve_artifact(
            approval_run.id, ApprovalGate.structure, merge_path,
            sha256_file(merge_path), "human",
        )
    after_approval_attempt = approval_workflow.load_run(approval_run.id)
    assert after_approval_attempt.status == RunStatus.blocked
    assert (
        after_approval_attempt.blocked_reason
        == "artifact_changed:plan_structure"
    )


def test_record_promotion_rejects_fabricated_commit_data(root: Path) -> None:
    workflow, source = make_workflow(root)
    repo = workflow.repo_root

    def git(*arguments: str) -> str:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return completed.stdout.strip()

    git("init", "-q")
    git("config", "user.name", "Workflow Fixture")
    git("config", "user.email", "workflow@example.invalid")
    git("add", ".")
    git("commit", "-qm", "baseline")
    baseline = git("rev-parse", "HEAD")

    run = workflow.create_run(source, "known_author", run_id="promotion-record")
    complete_initial_planning(workflow, run.id)
    approve_and_expand(workflow, run.id)
    complete(workflow, run.id, "reconcile_section_one")
    complete(workflow, run.id, "footnotes_section_one")
    ready_report = QAReport(
        run_id=run.id,
        round=0,
        issues=[],
        deterministic_checks_passed=True,
        ready_to_stage=True,
    )
    qa_path = workflow.write_artifact(
        run.id, "artifacts/qa-ready.json", ready_report
    )
    qa_claim = workflow.claim_task(run.id, "qa_0", "qa-worker")
    workflow.complete_task(
        run.id, "qa_0", qa_claim.claim_token, artifact_path=qa_path
    )
    advance_after_qa(workflow, run.id, qa_path)

    target_relative = (
        "archives/authors/known_author/promoted_work/text.txt"
    )
    expected_content = "विश्वसनीय प्रकाशित पाठ\n".encode()
    staged = workflow.run_dir(run.id) / "stage" / target_relative
    staged.parent.mkdir(parents=True)
    staged.write_bytes(expected_content)
    manifest = StageManifest(
        run_id=run.id,
        source_sha256=run.source_sha256,
        base_commit=baseline,
        entries=[
            StageEntry(
                staged_path=(Path("stage") / target_relative).as_posix(),
                target_path=target_relative,
                sha256=hashlib.sha256(expected_content).hexdigest(),
                operation="create",
            )
        ],
        commit_message="Add promoted fixture",
    )
    manifest_path = workflow.write_artifact(
        run.id, "artifacts/stage-manifest.json", manifest
    )
    stage_claim = workflow.claim_task(run.id, "stage", "stage-worker")
    workflow.complete_task(
        run.id, "stage", stage_claim.claim_token,
        artifact_path=manifest_path,
    )
    manifest_hash = sha256_file(manifest_path)
    workflow.approve_artifact(
        run.id, ApprovalGate.promotion, manifest_path,
        manifest_hash, "human",
    )

    target = repo / target_relative
    target.parent.mkdir(parents=True)
    target.write_bytes(b"different committed bytes\n")
    git("add", "--", target_relative)
    git("commit", "-qm", "tampered promotion")
    tampered_head = git("rev-parse", "HEAD")

    with expect(InvalidTransition):
        workflow.record_promotion(
            run.id, "a" * 40, manifest_hash, [target_relative]
        )
    with expect(InvalidTransition):
        workflow.record_promotion(
            run.id, tampered_head, manifest_hash, ["wrong/path.txt"]
        )
    with expect(InvalidTransition):
        workflow.record_promotion(
            run.id, tampered_head, manifest_hash, [target_relative]
        )

    target.write_bytes(expected_content)
    git("add", "--", target_relative)
    git("commit", "--amend", "--no-edit", "-q")
    valid_head = git("rev-parse", "HEAD")
    completed = workflow.record_promotion(
        run.id, valid_head, manifest_hash, [target_relative]
    )
    assert completed.status == RunStatus.completed
    assert completed.commit_sha == valid_head


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="book-workflow-test-") as temp:
        root = Path(temp)
        test_initial_dag_and_unknown_author(root / "initial")
        test_packet_uses_validated_custom_ocr_root(root / "packet")
        test_gate_one_expansion_and_two_round_verifier_cap(root / "graph")
        test_expand_repairs_qa_after_cascade_reset(root / "cascade-repair")
        test_expand_accepts_a_legacy_model_pinned_run(root / "legacy-pin")
        test_stage_manifest_create_update_and_safe_paths(root / "manifest")
        test_dynamic_nodes_are_pristine_and_promotion_is_canonical(root / "node-safety")
        test_artifact_change_blocks_claim_approval_and_advancement(root / "integrity")
        test_record_promotion_rejects_fabricated_commit_data(
            root / "record-promotion"
        )
    print("OK: scanned-book workflow graph regression spec passes")


if __name__ == "__main__":
    main()
