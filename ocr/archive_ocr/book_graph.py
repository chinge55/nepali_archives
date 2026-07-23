"""Dynamic graph expansion for approved scanned-book plans.

The persistent workflow starts with planning and Gate 1.  This module turns the
exact approved structure plan into bounded section tasks, then extends the DAG
after each deterministic QA pass.  It still does not launch a model: the Codex
coordinator claims ready tasks and delegates them to built-in sub-agents.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .book_workflow import (
    ApprovalGate,
    BookWorkflow,
    InvalidTransition,
    Node,
    NodeKind,
    NodeStatus,
    Task,
    TaskRole,
    safe_id,
    sha256_file,
)


PLAN_VERSION = "book-plan/v1"
QA_VERSION = "book-qa/v1"
MAX_VERIFICATION_ROUNDS = 2


class GraphModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlannedWork(GraphModel):
    id: str
    title_printed: str = Field(min_length=1)
    genre: str = Field(min_length=1)
    source_pdf_target: str

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        return safe_id(value, label="work id")

    @field_validator("source_pdf_target")
    @classmethod
    def safe_source_target(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".pdf":
            raise ValueError("source_pdf_target must be a safe relative PDF path")
        return path.as_posix()


class PlannedSection(GraphModel):
    id: str
    work_id: str
    title_printed: str = Field(min_length=1)
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)
    include: bool = True
    exclusion_reason: str | None = None

    @field_validator("id", "work_id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        return safe_id(value)

    @model_validator(mode="after")
    def coherent_range(self) -> "PlannedSection":
        if self.end_page < self.start_page:
            raise ValueError("section end_page precedes start_page")
        if not self.include and not self.exclusion_reason:
            raise ValueError("excluded sections require exclusion_reason")
        return self

    @property
    def pages(self) -> list[int]:
        return list(range(self.start_page, self.end_page + 1))


class ApprovedStructurePlan(GraphModel):
    contract_version: Literal[PLAN_VERSION] = PLAN_VERSION
    run_id: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    author_id: str
    works: list[PlannedWork] = Field(min_length=1)
    sections: list[PlannedSection] = Field(min_length=1)
    retained_book_target: str
    notes: list[str] = Field(default_factory=list)

    @field_validator("run_id", "author_id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        return safe_id(value)

    @field_validator("retained_book_target")
    @classmethod
    def safe_retained_target(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".pdf":
            raise ValueError("retained_book_target must be a safe relative PDF path")
        return path.as_posix()

    @model_validator(mode="after")
    def valid_relationships(self) -> "ApprovedStructurePlan":
        work_ids = [work.id for work in self.works]
        section_ids = [section.id for section in self.sections]
        if len(work_ids) != len(set(work_ids)):
            raise ValueError("work ids must be unique")
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("section ids must be unique")
        unknown = {section.work_id for section in self.sections} - set(work_ids)
        if unknown:
            raise ValueError(f"sections reference unknown works: {sorted(unknown)}")
        if not any(section.include for section in self.sections):
            raise ValueError("plan must include at least one semantic section")
        return self


class QAIssue(GraphModel):
    id: str
    category: Literal[
        "ensemble_disagreement",
        "numbering",
        "footnote",
        "folio",
        "structure",
        "metadata",
        "illegible",
        "other",
    ]
    severity: Literal["low", "medium", "high", "blocking"]
    pages: list[int] = Field(min_length=1)
    detail: str = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        return safe_id(value, label="issue id")

    @field_validator("pages")
    @classmethod
    def unique_pages(cls, value: list[int]) -> list[int]:
        if any(page < 1 for page in value) or len(value) != len(set(value)):
            raise ValueError("issue pages must be unique one-based numbers")
        return value


class QAReport(GraphModel):
    contract_version: Literal[QA_VERSION] = QA_VERSION
    run_id: str
    round: int = Field(ge=0, le=MAX_VERIFICATION_ROUNDS)
    issues: list[QAIssue] = Field(default_factory=list)
    deterministic_checks_passed: bool
    ready_to_stage: bool

    @field_validator("run_id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        return safe_id(value, label="run id")

    @model_validator(mode="after")
    def stage_state_is_consistent(self) -> "QAReport":
        unresolved = [
            issue for issue in self.issues
            if issue.severity in {"high", "blocking"}
        ]
        if self.ready_to_stage and (not self.deterministic_checks_passed or unresolved):
            raise ValueError("ready_to_stage conflicts with unresolved QA risk")
        return self


def _task_node(
    node_id: str,
    role: TaskRole,
    dependencies: list[str],
    summary: str,
    *,
    inputs: dict[str, object] | None = None,
    preferred_model: str | None = None,
    reasoning_effort: str | None = None,
) -> Node:
    task = Task(
        id=node_id,
        node_id=node_id,
        role=role,
        summary=summary,
        inputs=inputs or {},
        preferred_model=preferred_model,
        reasoning_effort=reasoning_effort,
    )
    return Node(
        id=node_id,
        kind=NodeKind.coordinator if role in {TaskRole.qa, TaskRole.stage, TaskRole.promote} else NodeKind.agent,
        role=role,
        depends_on=dependencies,
        task=task,
    )


def _approved_artifact(
    workflow: BookWorkflow,
    run_id: str,
    gate: ApprovalGate,
) -> Path:
    run = workflow.load_run(run_id)
    approval = next((item for item in run.approvals if item.gate == gate), None)
    if approval is None:
        raise InvalidTransition(f"{gate.value} approval is required")
    artifact = workflow.run_dir(run_id) / approval.artifact_path
    if not artifact.is_file() or sha256_file(artifact) != approval.artifact_sha256:
        raise InvalidTransition(f"{gate.value} approved artifact changed")
    return artifact


def expand_approved_plan(
    workflow: BookWorkflow,
    run_id: str,
) -> ApprovedStructurePlan:
    """Add one reconciler and footnote sweep per included semantic section."""
    artifact = _approved_artifact(workflow, run_id, ApprovalGate.structure)
    plan = ApprovedStructurePlan.model_validate_json(artifact.read_bytes())
    run = workflow.load_run(run_id)
    if (
        plan.run_id != run.id
        or plan.source_sha256 != run.source_sha256
        or plan.author_id != run.author_id
    ):
        raise InvalidTransition("approved structure plan does not identify this run")
    if any(node.role == TaskRole.reconcile for node in run.nodes.values()):
        raise InvalidTransition("approved structure plan is already expanded")

    worker_nodes: list[Node] = []
    for section in plan.sections:
        if not section.include:
            continue
        common = {
            "section_id": section.id,
            "work_id": section.work_id,
            "title_printed": section.title_printed,
            "start_page": section.start_page,
            "end_page": section.end_page,
            "pages": section.pages,
            "structure_plan": artifact.relative_to(workflow.run_dir(run_id)).as_posix(),
        }
        worker_nodes.append(
            _task_node(
                f"reconcile_{section.id}",
                TaskRole.reconcile,
                ["approve_structure"],
                f"Reconcile the complete semantic section {section.title_printed!r}.",
                inputs=common,
                preferred_model="gpt-5.6-sol",
                reasoning_effort="high",
            )
        )
        worker_nodes.append(
            _task_node(
                f"footnotes_{section.id}",
                TaskRole.footnote,
                ["approve_structure"],
                f"Independently sweep every page of {section.title_printed!r} for footnotes.",
                inputs=common,
                preferred_model="gpt-5.6-terra",
                reasoning_effort="medium",
            )
        )

    worker_ids = [node.id for node in worker_nodes]
    worker_nodes.append(
        _task_node(
            "qa_0",
            TaskRole.qa,
            worker_ids,
            "Run deterministic completeness, numbering, footnote, and OCR disagreement checks.",
            inputs={"round": 0, "structure_plan": artifact.name},
        )
    )
    workflow.add_nodes(run_id, worker_nodes)
    return plan


def advance_after_qa(
    workflow: BookWorkflow,
    run_id: str,
    report_path: str | Path,
) -> QAReport:
    """Add a targeted verifier or the staging/gate-2 tail after a QA result."""
    report_file = Path(report_path)
    if not report_file.is_absolute():
        report_file = workflow.run_dir(run_id) / report_file
    report_file = report_file.resolve(strict=True)
    try:
        relative_report = report_file.relative_to(workflow.run_dir(run_id).resolve())
    except ValueError as exc:
        raise InvalidTransition("QA report must be inside this run") from exc
    report = QAReport.model_validate_json(report_file.read_bytes())
    if report.run_id != run_id:
        raise InvalidTransition("QA report identifies another run")

    run = workflow.load_run(run_id)
    qa_id = f"qa_{report.round}"
    qa_node = run.nodes.get(qa_id)
    if qa_node is None or qa_node.status != NodeStatus.completed:
        raise InvalidTransition(f"{qa_id} must be completed before advancing")
    if (
        qa_node.artifact_path != relative_report.as_posix()
        or qa_node.artifact_sha256 != sha256_file(report_file)
    ):
        raise InvalidTransition(f"{qa_id} is not bound to this exact QA report")

    if report.ready_to_stage:
        if "stage" in run.nodes:
            raise InvalidTransition("staging tail already exists")
        tail = [
            _task_node(
                "stage",
                TaskRole.stage,
                [qa_id],
                "Materialize source-only files in the isolated staging tree and emit its manifest.",
                inputs={"qa_report": relative_report.as_posix()},
            ),
            Node(
                id="approve_promotion",
                kind=NodeKind.approval,
                role=TaskRole.promotion_approval,
                depends_on=["stage"],
                max_attempts=1,
            ),
            _task_node(
                "promote",
                TaskRole.promote,
                ["approve_promotion"],
                "Promote the exact approved manifest, validate, and create one exact-path commit.",
            ),
        ]
        workflow.add_nodes(run_id, tail)
        return report

    if report.round >= MAX_VERIFICATION_ROUNDS:
        raise InvalidTransition(
            "QA still has risk after two verification rounds; human correction is required"
        )
    if not report.issues:
        raise InvalidTransition("non-stageable QA report must name targeted issues")
    next_round = report.round + 1
    verifier_id = f"verify_{next_round}"
    next_qa_id = f"qa_{next_round}"
    if verifier_id in run.nodes or next_qa_id in run.nodes:
        raise InvalidTransition(f"verification round {next_round} already exists")
    pages = sorted({page for issue in report.issues for page in issue.pages})
    nodes = [
        _task_node(
            verifier_id,
            TaskRole.verify,
            [qa_id],
            f"Independently verify {len(report.issues)} targeted QA issues.",
            inputs={
                "round": next_round,
                "qa_report": relative_report.as_posix(),
                "issue_ids": [issue.id for issue in report.issues],
                "pages": pages,
            },
            preferred_model="gpt-5.6-sol",
            reasoning_effort="high",
        ),
        _task_node(
            next_qa_id,
            TaskRole.qa,
            [verifier_id],
            f"Re-run deterministic QA after targeted verification round {next_round}.",
            inputs={
                "round": next_round,
                "previous_qa_report": relative_report.as_posix(),
            },
        ),
    ]
    workflow.add_nodes(run_id, nodes)
    return report


def load_plan(path: str | Path) -> ApprovedStructurePlan:
    return ApprovedStructurePlan.model_validate_json(Path(path).read_bytes())


def load_qa_report(path: str | Path) -> QAReport:
    return QAReport.model_validate_json(Path(path).read_bytes())


__all__ = [
    "ApprovedStructurePlan",
    "GraphModel",
    "MAX_VERIFICATION_ROUNDS",
    "PLAN_VERSION",
    "PlannedSection",
    "PlannedWork",
    "QAIssue",
    "QAReport",
    "QA_VERSION",
    "advance_after_qa",
    "expand_approved_plan",
    "load_plan",
    "load_qa_report",
]
