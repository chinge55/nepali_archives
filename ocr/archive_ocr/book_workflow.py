"""Persistent, resumable workflow graph for scanned-book digitization.

This module is deliberately an orchestration *state machine*, not an agent
runner.  Codex (or a future CLI) asks for ready tasks, claims them, runs local
OCR or subscription-backed sub-agents, and records their results here.  No
OpenAI API client is imported and no method in this module writes to canonical
``archives/`` paths.

Run state is stored as inspectable JSON under ``BOOK_WORK_DIR`` when that
environment variable is set, otherwise under ``.ocr-work/book-runs`` in the
repository.  Every state transition takes a per-run ``flock`` and replaces
``run.json`` atomically, allowing interrupted sessions to resume safely.
"""
from __future__ import annotations

import ast
import fcntl
import hashlib
import json
import os
import re
import secrets
import subprocess
from collections import Counter, deque
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


GRAPH_VERSION = 1
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,95}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def utcnow() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file without loading a book-sized PDF into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def safe_id(value: str, *, label: str = "id") -> str:
    """Validate an identifier that may become a filesystem component."""
    if not _SAFE_ID.fullmatch(value):
        raise ValueError(
            f"{label} must match {_SAFE_ID.pattern!r}; got {value!r}"
        )
    return value


def _slug(value: str, limit: int = 48) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:limit]
    return result or "book"


class StrictModel(BaseModel):
    """Base class for durable contracts; silently ignored fields are unsafe."""

    model_config = ConfigDict(extra="forbid")


class RunStatus(str, Enum):
    active = "active"
    blocked = "blocked"
    waiting_approval = "waiting_approval"
    completed = "completed"
    aborted = "aborted"


class NodeKind(str, Enum):
    coordinator = "coordinator"
    agent = "agent"
    approval = "approval"


class NodeStatus(str, Enum):
    pending = "pending"
    claimed = "claimed"
    completed = "completed"
    failed = "failed"
    blocked = "blocked"
    skipped = "skipped"


class TaskRole(str, Enum):
    preflight = "preflight"
    ocr = "ocr"
    structure = "structure"
    folio = "folio"
    dedupe = "dedupe"
    merge_structure = "merge_structure"
    structure_approval = "structure_approval"
    reconcile = "reconcile"
    footnote = "footnote"
    qa = "qa"
    verify = "verify"
    stage = "stage"
    promotion_approval = "promotion_approval"
    promote = "promote"


class ApprovalGate(str, Enum):
    structure = "structure"
    promotion = "promotion"


class Task(StrictModel):
    """Immutable instructions handed to a coordinator or Codex sub-agent."""

    id: str
    node_id: str
    role: TaskRole
    prompt_version: str = "1"
    summary: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected_result: dict[str, Any] = Field(default_factory=dict)
    preferred_model: str | None = None
    reasoning_effort: str | None = None

    @field_validator("id", "node_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return safe_id(value)


class Node(StrictModel):
    """One graph node, including its claim lease and result reference."""

    id: str
    kind: NodeKind
    role: TaskRole
    depends_on: list[str] = Field(default_factory=list)
    status: NodeStatus = NodeStatus.pending
    task: Task | None = None
    max_attempts: int = Field(default=3, ge=1, le=20)
    attempts: int = Field(default=0, ge=0)
    claimed_by: str | None = None
    claim_token: str | None = None
    claimed_at: datetime | None = None
    lease_expires_at: datetime | None = None
    artifact_path: str | None = None
    artifact_sha256: str | None = None
    error: str | None = None
    completed_at: datetime | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return safe_id(value, label="node id")

    @field_validator("depends_on")
    @classmethod
    def validate_dependencies(cls, values: list[str]) -> list[str]:
        for value in values:
            safe_id(value, label="dependency id")
        if len(values) != len(set(values)):
            raise ValueError("depends_on may not contain duplicates")
        return values

    @field_validator("artifact_sha256")
    @classmethod
    def validate_hash(cls, value: str | None) -> str | None:
        if value is not None and not _SHA256.fullmatch(value):
            raise ValueError("artifact_sha256 must be a lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def validate_task(self) -> "Node":
        if self.kind == NodeKind.approval and self.task is not None:
            raise ValueError("approval nodes cannot have claimable tasks")
        if self.kind != NodeKind.approval:
            if self.task is None:
                raise ValueError("non-approval nodes require a task")
            if self.task.node_id != self.id or self.task.role != self.role:
                raise ValueError("task node_id and role must match its node")
        return self


class Approval(StrictModel):
    """Human approval bound to the exact bytes of one workflow artifact."""

    gate: ApprovalGate
    node_id: str
    artifact_path: str
    artifact_sha256: str
    approver: str
    approved_at: datetime = Field(default_factory=utcnow)

    @field_validator("node_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return safe_id(value, label="approval node id")

    @field_validator("artifact_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("artifact_sha256 must be a lowercase SHA-256")
        return value


class StageEntry(StrictModel):
    """One proposed source-tree write; this model does not perform the write."""

    staged_path: str
    target_path: str
    sha256: str
    operation: str = Field(pattern=r"^(create|update)$")
    prior_sha256: str | None = None

    @field_validator("staged_path", "target_path")
    @classmethod
    def relative_safe_path(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise ValueError("manifest paths must be safe relative paths")
        return path.as_posix()

    @field_validator("sha256", "prior_sha256")
    @classmethod
    def validate_hash(cls, value: str | None) -> str | None:
        if value is not None and not _SHA256.fullmatch(value):
            raise ValueError("sha256 must be a lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def operation_matches_prior_hash(self) -> "StageEntry":
        if self.operation == "update" and self.prior_sha256 is None:
            raise ValueError("update entries require prior_sha256")
        if self.operation == "create" and self.prior_sha256 is not None:
            raise ValueError("create entries may not set prior_sha256")
        return self


class StageManifest(StrictModel):
    """Gate-2 representation of staged changes, never a promotion command."""

    run_id: str
    source_sha256: str
    base_commit: str = Field(pattern=r"^[0-9a-f]{40}([0-9a-f]{24})?$")
    entries: list[StageEntry]
    retained_book_scan: str | None = None
    validation_commands: list[list[str]] = Field(default_factory=list)
    commit_message: str
    created_at: datetime = Field(default_factory=utcnow)

    @field_validator("run_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return safe_id(value, label="run id")

    @field_validator("source_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("source_sha256 must be a lowercase SHA-256")
        return value


class BookRun(StrictModel):
    """Complete persisted state for one source book."""

    graph_version: int = GRAPH_VERSION
    id: str
    source_path: str
    source_name: str
    source_sha256: str
    author_id: str
    author_known: bool
    ocr_job_id: str | None = None
    status: RunStatus = RunStatus.active
    blocked_reason: str | None = None
    nodes: dict[str, Node]
    approvals: list[Approval] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None
    commit_sha: str | None = None

    @field_validator("id", "author_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return safe_id(value)

    @field_validator("ocr_job_id")
    @classmethod
    def validate_optional_id(cls, value: str | None) -> str | None:
        if value is not None:
            safe_id(value, label="OCR job id")
        return value

    @field_validator("source_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("source_sha256 must be a lowercase SHA-256")
        return value

    @field_validator("commit_sha")
    @classmethod
    def validate_commit_hash(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(
            r"[0-9a-f]{40}([0-9a-f]{24})?", value
        ):
            raise ValueError("commit_sha must be a Git object id")
        return value

    @model_validator(mode="after")
    def validate_graph(self) -> "BookRun":
        if set(self.nodes) != {node.id for node in self.nodes.values()}:
            raise ValueError("nodes mapping keys must equal node ids")
        _validate_graph(self.nodes)
        promote = self.nodes.get("promote")
        canonical_promotion = (
            promote is not None
            and promote.role == TaskRole.promote
            and promote.kind == NodeKind.coordinator
            and promote.depends_on == ["approve_promotion"]
            and promote.status == NodeStatus.completed
            and promote.artifact_path == "artifacts/promote.json"
            and promote.artifact_sha256 is not None
        )
        if self.commit_sha is not None and not canonical_promotion:
            raise ValueError(
                "commit_sha requires the canonical completed promote node"
            )
        if self.status == RunStatus.completed and (
            self.commit_sha is None or not canonical_promotion
        ):
            raise ValueError(
                "completed runs require the canonical completed promote node "
                "and commit_sha"
            )
        return self


class TaskClaim(StrictModel):
    """A leased task returned to a worker."""

    run_id: str
    node_id: str
    claim_token: str
    lease_expires_at: datetime
    task: Task


class WorkflowSummary(StrictModel):
    """Structured status intended for CLI JSON or a concise human renderer."""

    run_id: str
    status: RunStatus
    blocked_reason: str | None
    source_name: str
    source_sha256: str
    author_id: str
    author_known: bool
    ocr_job_id: str | None
    node_counts: dict[str, int]
    ready_nodes: list[str]
    claimed_nodes: list[str]
    failed_nodes: list[str]
    waiting_approval: list[str]
    approvals: list[Approval]
    updated_at: datetime


class WorkflowError(RuntimeError):
    """Base exception for invalid workflow operations."""


class RunNotFound(WorkflowError):
    pass


class InvalidTransition(WorkflowError):
    pass


class ArtifactMismatch(WorkflowError):
    pass


def _validate_graph(nodes: Mapping[str, Node]) -> None:
    """Reject missing dependencies, self-edges, and dependency cycles."""
    ids = set(nodes)
    for node in nodes.values():
        missing = set(node.depends_on) - ids
        if missing:
            raise ValueError(f"node {node.id!r} has missing dependencies: {missing}")
        if node.id in node.depends_on:
            raise ValueError(f"node {node.id!r} depends on itself")

    indegree = {node_id: 0 for node_id in ids}
    children: dict[str, list[str]] = {node_id: [] for node_id in ids}
    for node in nodes.values():
        indegree[node.id] = len(node.depends_on)
        for dependency in node.depends_on:
            children[dependency].append(node.id)
    queue = deque(node_id for node_id, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for child in children[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(ids):
        raise ValueError("workflow graph contains a dependency cycle")


def _initial_nodes(source_path: str, source_sha: str, author_id: str) -> dict[str, Node]:
    common = {
        "source_path": source_path,
        "source_sha256": source_sha,
        "author_id": author_id,
    }

    def task_node(
        node_id: str,
        role: TaskRole,
        kind: NodeKind,
        dependencies: Sequence[str],
        summary: str,
        *,
        inputs: Mapping[str, Any] | None = None,
        preferred_model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> Node:
        task = Task(
            id=node_id,
            node_id=node_id,
            role=role,
            summary=summary,
            inputs={**common, **dict(inputs or {})},
            preferred_model=preferred_model,
            reasoning_effort=reasoning_effort,
        )
        return Node(
            id=node_id,
            kind=kind,
            role=role,
            depends_on=list(dependencies),
            task=task,
        )

    nodes = [
        task_node(
            "preflight",
            TaskRole.preflight,
            NodeKind.coordinator,
            [],
            "Verify source checksum, PDF shape, author, and archive conflicts.",
        ),
        task_node(
            "ocr",
            TaskRole.ocr,
            NodeKind.coordinator,
            ["preflight"],
            "Reuse or run the Surya-primary, Tesseract-shadow OCR ensemble.",
            inputs={"engines": ["ensemble"], "primary": "surya", "shadow": "tesseract"},
        ),
        task_node(
            "plan_structure",
            TaskRole.structure,
            NodeKind.agent,
            ["ocr"],
            "Classify pages, identify semantic sections, and flag front matter.",
            preferred_model="gpt-5.6-sol",
            reasoning_effort="high",
        ),
        task_node(
            "plan_folios",
            TaskRole.folio,
            NodeKind.agent,
            ["ocr"],
            "Verify physical folio order and printed-page to PDF-page mapping.",
            preferred_model="gpt-5.6-terra",
            reasoning_effort="medium",
        ),
        task_node(
            "plan_dedupe",
            TaskRole.dedupe,
            NodeKind.agent,
            ["ocr"],
            "Check proposed works against the archive and catalogue metadata.",
            preferred_model="gpt-5.6-terra",
            reasoning_effort="medium",
        ),
        task_node(
            "merge_structure",
            TaskRole.merge_structure,
            NodeKind.coordinator,
            ["plan_structure", "plan_folios", "plan_dedupe"],
            "Merge planning evidence into the Gate-1 structure plan.",
        ),
        Node(
            id="approve_structure",
            kind=NodeKind.approval,
            role=TaskRole.structure_approval,
            depends_on=["merge_structure"],
            max_attempts=1,
        ),
    ]
    return {node.id: node for node in nodes}


class BookWorkflow:
    """Filesystem-backed API for the book-processing DAG.

    The methods that accept artifact paths require those artifacts to resolve
    inside the run directory.  This is the key boundary that prevents task
    execution from mutating canonical archive files.
    """

    def __init__(
        self,
        repo_root: Path | str | None = None,
        work_root: Path | str | None = None,
        ocr_jobs_root: Path | str | None = None,
    ) -> None:
        inferred_repo = Path(__file__).resolve().parents[2]
        self.repo_root = Path(repo_root or inferred_repo).resolve()
        configured = work_root or os.environ.get("BOOK_WORK_DIR")
        self.work_root = (
            Path(configured).expanduser().resolve()
            if configured
            else self.repo_root / ".ocr-work" / "book-runs"
        )
        from . import storage
        self.ocr_jobs_root = (
            Path(ocr_jobs_root).expanduser().resolve()
            if ocr_jobs_root is not None
            else storage.jobs_root().resolve()
        )
        for forbidden in (self.repo_root / "archives", self.repo_root / ".git"):
            forbidden = forbidden.resolve()
            if (
                self.work_root == forbidden
                or self.work_root.is_relative_to(forbidden)
                or forbidden.is_relative_to(self.work_root)
            ):
                raise ValueError(
                    f"book work root overlaps protected repository data: {forbidden}"
                )

    @property
    def authors_root(self) -> Path:
        return self.repo_root / "archives" / "authors"

    def known_author_ids(self) -> set[str]:
        """Discover author IDs established by at least one valid work metadata."""
        authors: set[str] = set()
        if not self.authors_root.is_dir():
            return authors
        for metadata_path in self.authors_root.glob("*/*/metadata.json"):
            try:
                data = json.loads(metadata_path.read_text(encoding="utf-8"))
                author_id = data.get("author", {}).get("id")
            except (OSError, json.JSONDecodeError, AttributeError):
                continue
            if (
                isinstance(author_id, str)
                and _SAFE_ID.fullmatch(author_id)
                and author_id == metadata_path.parents[1].name
            ):
                authors.add(author_id)
        registry = self.repo_root / "pipeline" / "build_site.py"
        if registry.is_file():
            try:
                tree = ast.parse(registry.read_text(encoding="utf-8"))
                for statement in tree.body:
                    if not isinstance(statement, ast.Assign):
                        continue
                    if not any(
                        isinstance(target, ast.Name) and target.id == "AUTHORS"
                        for target in statement.targets
                    ) or not isinstance(statement.value, ast.Dict):
                        continue
                    for key in statement.value.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            if _SAFE_ID.fullmatch(key.value):
                                authors.add(key.value)
            except (OSError, SyntaxError, UnicodeError):
                pass
        return authors

    def is_known_author(self, author_id: str) -> bool:
        safe_id(author_id, label="author id")
        return author_id in self.known_author_ids()

    def run_dir(self, run_id: str) -> Path:
        return self.work_root / safe_id(run_id, label="run id")

    def create_run(
        self,
        source_pdf: Path | str,
        author_id: str,
        *,
        run_id: str | None = None,
        ocr_job_id: str | None = None,
    ) -> BookRun:
        """Create the durable initial graph without copying or altering the PDF."""
        source = Path(source_pdf).expanduser().resolve(strict=True)
        if not source.is_file():
            raise ValueError(f"source is not a file: {source}")
        if source.suffix.lower() != ".pdf":
            raise ValueError("source must be a PDF")
        safe_id(author_id, label="author id")
        provided_ocr_job = ocr_job_id is not None
        if ocr_job_id is not None:
            safe_id(ocr_job_id, label="OCR job id")
        source_sha = sha256_file(source)
        prior_runs = [
            prior for prior in self.find_by_source(source_sha)
            if prior.author_id == author_id
        ]
        if run_id is None and prior_runs:
            return prior_runs[0]
        if ocr_job_id is None:
            ocr_job_id = next(
                (prior.ocr_job_id for prior in prior_runs if prior.ocr_job_id),
                None,
            )
        generated_id = (
            f"{_slug(source.stem)}-{source_sha[:8]}-{secrets.token_hex(2)}"
        )
        chosen_id = safe_id(run_id or generated_id, label="run id")
        target = self.run_dir(chosen_id)
        try:
            target.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise WorkflowError(f"run already exists: {chosen_id}") from exc

        author_known = self.is_known_author(author_id)
        run = BookRun(
            id=chosen_id,
            source_path=str(source),
            source_name=source.name,
            source_sha256=source_sha,
            author_id=author_id,
            author_known=author_known,
            ocr_job_id=ocr_job_id,
            status=RunStatus.active if author_known else RunStatus.blocked,
            blocked_reason=None if author_known else "unknown_author",
            nodes=_initial_nodes(str(source), source_sha, author_id),
        )
        candidates = (
            [ocr_job_id]
            if ocr_job_id is not None
            else [child.name for child in self.ocr_jobs_root.iterdir()]
            if self.ocr_jobs_root.is_dir()
            else []
        )
        run.ocr_job_id = None
        for candidate in candidates:
            if candidate is None or not _SAFE_ID.fullmatch(candidate):
                continue
            try:
                self._bind_ocr_job(run, candidate)
                break
            except (OSError, ValueError, WorkflowError):
                if provided_ocr_job:
                    raise
        if not author_known:
            run.nodes["preflight"].status = NodeStatus.blocked
        with self._locked(chosen_id):
            self._save_unlocked(run)
        return run

    def list_runs(self) -> list[BookRun]:
        if not self.work_root.is_dir():
            return []
        runs: list[BookRun] = []
        for child in self.work_root.iterdir():
            if child.is_dir() and _SAFE_ID.fullmatch(child.name):
                try:
                    runs.append(self.load_run(child.name))
                except (RunNotFound, ValueError, json.JSONDecodeError):
                    continue
        return sorted(runs, key=lambda run: run.created_at, reverse=True)

    def load_run(self, run_id: str) -> BookRun:
        path = self.run_dir(run_id) / "run.json"
        if not path.is_file():
            raise RunNotFound(f"unknown run: {run_id}")
        return BookRun.model_validate_json(path.read_text(encoding="utf-8"))

    def find_by_source(self, source_sha256: str) -> list[BookRun]:
        if not _SHA256.fullmatch(source_sha256):
            raise ValueError("source_sha256 must be a lowercase SHA-256")
        return [run for run in self.list_runs() if run.source_sha256 == source_sha256]

    def refresh_author(self, run_id: str) -> BookRun:
        """Recheck the archive after the external add-author workflow completes."""
        with self._locked(run_id):
            run = self._load_unlocked(run_id)
            known = self.is_known_author(run.author_id)
            run.author_known = known
            preflight = run.nodes["preflight"]
            if known and preflight.status == NodeStatus.blocked:
                preflight.status = NodeStatus.pending
                run.blocked_reason = None
            elif not known and preflight.status == NodeStatus.pending:
                preflight.status = NodeStatus.blocked
                run.blocked_reason = "unknown_author"
            self._derive_run_status(run)
            self._save_unlocked(run)
            return run

    def ready_nodes(
        self,
        run_id: str,
        *,
        limit: int | None = None,
        kinds: set[NodeKind] | None = None,
    ) -> list[Node]:
        """Return dependency-ready nodes in insertion order after lease recovery."""
        with self._locked(run_id):
            run = self._load_unlocked(run_id)
            self._expire_claims(run)
            self._derive_run_status(run)
            self._save_unlocked(run)
            ready = [
                node.model_copy(deep=True)
                for node in run.nodes.values()
                if self._is_ready(run, node)
                and (kinds is None or node.kind in kinds)
            ]
            return ready[:limit] if limit is not None else ready

    def ready_tasks(self, run_id: str, *, limit: int | None = None) -> list[Task]:
        nodes = self.ready_nodes(
            run_id,
            limit=limit,
            kinds={NodeKind.coordinator, NodeKind.agent},
        )
        return [node.task for node in nodes if node.task is not None]

    def claim_task(
        self,
        run_id: str,
        node_id: str,
        worker_id: str,
        *,
        lease_seconds: int = 3600,
    ) -> TaskClaim:
        safe_id(node_id, label="node id")
        if not worker_id.strip() or "\x00" in worker_id or len(worker_id) > 160:
            raise ValueError("worker_id must be 1-160 safe display characters")
        if not 30 <= lease_seconds <= 86_400:
            raise ValueError("lease_seconds must be between 30 and 86400")
        with self._locked(run_id):
            run = self._load_unlocked(run_id)
            self._require_artifact_integrity_unlocked(run)
            self._expire_claims(run)
            node = self._node(run, node_id)
            if node.kind == NodeKind.approval or node.task is None:
                raise InvalidTransition("approval nodes cannot be claimed")
            if not self._is_ready(run, node):
                raise InvalidTransition(f"node is not ready: {node_id}")
            now = utcnow()
            token = secrets.token_urlsafe(24)
            node.status = NodeStatus.claimed
            node.attempts += 1
            node.claimed_by = worker_id
            node.claim_token = token
            node.claimed_at = now
            node.lease_expires_at = now + timedelta(seconds=lease_seconds)
            node.error = None
            self._derive_run_status(run)
            self._save_unlocked(run)
            return TaskClaim(
                run_id=run.id,
                node_id=node.id,
                claim_token=token,
                lease_expires_at=node.lease_expires_at,
                task=node.task,
            )

    def renew_claim(
        self,
        run_id: str,
        node_id: str,
        claim_token: str,
        *,
        lease_seconds: int = 3600,
    ) -> TaskClaim:
        if not 30 <= lease_seconds <= 86_400:
            raise ValueError("lease_seconds must be between 30 and 86400")
        with self._locked(run_id):
            run = self._load_unlocked(run_id)
            node = self._claimed_node(run, node_id, claim_token)
            node.lease_expires_at = utcnow() + timedelta(seconds=lease_seconds)
            self._save_unlocked(run)
            assert node.task is not None and node.claim_token is not None
            return TaskClaim(
                run_id=run.id,
                node_id=node.id,
                claim_token=node.claim_token,
                lease_expires_at=node.lease_expires_at,
                task=node.task,
            )

    def complete_task(
        self,
        run_id: str,
        node_id: str,
        claim_token: str,
        *,
        result: Mapping[str, Any] | BaseModel | None = None,
        artifact_path: Path | str | None = None,
    ) -> BookRun:
        """Complete a claim, storing results only within the workflow run."""
        with self._locked(run_id):
            run = self._load_unlocked(run_id)
            node = self._claimed_node(run, node_id, claim_token)
            if node.role == TaskRole.promote:
                raise InvalidTransition("use guarded book promote, not complete")
            if node.role == TaskRole.ocr:
                if not run.ocr_job_id:
                    raise InvalidTransition("attach a validated OCR job before completion")
                from .book_ocr import validate_ocr_job
                validate_ocr_job(run, run.ocr_job_id, self.ocr_jobs_root)
            if result is not None and artifact_path is not None:
                raise ValueError("provide result or artifact_path, not both")
            if result is not None:
                data = (
                    result.model_dump(mode="json")
                    if isinstance(result, BaseModel)
                    else dict(result)
                )
                relative = Path("tasks") / node.id / f"attempt-{node.attempts}.json"
                artifact = self._write_json_artifact_unlocked(run, relative, data)
            elif artifact_path is not None:
                artifact = self._artifact_in_run(run.id, artifact_path, must_exist=True)
            else:
                artifact = None
            if node.role not in {TaskRole.preflight, TaskRole.ocr}:
                if artifact is None:
                    raise InvalidTransition(
                        f"{node.role.value} completion requires a typed artifact"
                    )
                self._validate_task_artifact(run, node, artifact)

            node.status = NodeStatus.completed
            node.completed_at = utcnow()
            node.error = None
            if artifact is not None:
                node.artifact_path = artifact.relative_to(
                    self.run_dir(run.id).resolve()
                ).as_posix()
                node.artifact_sha256 = sha256_file(artifact)
            self._clear_claim(node)
            self._derive_run_status(run)
            self._save_unlocked(run)
            return run


    def _validate_task_artifact(self, run: BookRun, node: Node, artifact: Path) -> None:
        """Bind a completed artifact to its role, task identity, and page set."""
        if node.task is None:
            raise InvalidTransition("claimable node has no task")
        agent_roles = {
            TaskRole.structure: "structure",
            TaskRole.folio: "folio",
            TaskRole.dedupe: "dedupe",
            TaskRole.reconcile: "section_reconciler",
            TaskRole.footnote: "footnote_sweep",
            TaskRole.verify: "targeted_verifier",
        }
        if node.role in agent_roles:
            from .book_prompts import validate_result_json
            result = validate_result_json(agent_roles[node.role], artifact.read_bytes())
            if result.task_id != node.task.id:
                raise InvalidTransition("result task_id does not match claimed task")
            expected_pages = node.task.inputs.get("pages")
            if expected_pages is not None and set(result.source_pages) != {
                int(page) for page in expected_pages
            }:
                raise InvalidTransition("result pages do not match assigned pages")
            if (
                node.role == TaskRole.reconcile
                and result.section_id != node.task.inputs.get("section_id")
            ):
                raise InvalidTransition("result section_id does not match assignment")
            if node.role == TaskRole.verify:
                expected_issues = set(node.task.inputs.get("issue_ids", []))
                returned_issues = {issue.issue_id for issue in result.issues}
                if returned_issues != expected_issues:
                    raise InvalidTransition(
                        "verifier result does not cover exact issue IDs"
                    )
            return
        if node.role == TaskRole.merge_structure:
            from .book_graph import ApprovedStructurePlan
            plan = ApprovedStructurePlan.model_validate_json(artifact.read_bytes())
            if (
                plan.run_id != run.id
                or plan.source_sha256 != run.source_sha256
                or plan.author_id != run.author_id
            ):
                raise InvalidTransition("structure plan identifies another run")
            return
        if node.role == TaskRole.qa:
            from .book_graph import QAReport
            report = QAReport.model_validate_json(artifact.read_bytes())
            if (
                report.run_id != run.id
                or report.round != int(node.task.inputs.get("round", -1))
            ):
                raise InvalidTransition("QA report identifies another run or round")
            return
        if node.role == TaskRole.stage:
            manifest = StageManifest.model_validate_json(artifact.read_bytes())
            if manifest.run_id != run.id or manifest.source_sha256 != run.source_sha256:
                raise InvalidTransition("stage manifest identifies another run")
            return

    def fail_task(
        self,
        run_id: str,
        node_id: str,
        claim_token: str,
        error: str,
        *,
        retryable: bool = True,
    ) -> BookRun:
        with self._locked(run_id):
            run = self._load_unlocked(run_id)
            node = self._claimed_node(run, node_id, claim_token)
            node.error = error[:4000]
            node.status = (
                NodeStatus.pending
                if retryable and node.attempts < node.max_attempts
                else NodeStatus.failed
            )
            self._clear_claim(node)
            self._derive_run_status(run)
            self._save_unlocked(run)
            return run

    def reset_task(
        self,
        run_id: str,
        node_id: str,
        *,
        cascade: bool = False,
    ) -> BookRun:
        """Reset a node; completed descendants require an explicit cascade."""
        with self._locked(run_id):
            run = self._load_unlocked(run_id)
            if run.commit_sha is not None:
                raise InvalidTransition("committed promotions cannot be reset")
            node = self._node(run, node_id)
            descendants = self._descendants(run, node_id)
            completed = [
                item for item in descendants
                if run.nodes[item].status in {NodeStatus.completed, NodeStatus.skipped}
            ]
            if completed and not cascade:
                raise InvalidTransition(
                    f"completed descendants require cascade=True: {completed}"
                )
            reset_set = {node_id, *descendants} if cascade else {node_id}
            base_nodes = {
                "preflight", "ocr", "plan_structure", "plan_folios",
                "plan_dedupe", "merge_structure", "approve_structure",
            }
            if cascade:
                for generated_id in reversed(descendants):
                    if generated_id not in base_nodes:
                        del run.nodes[generated_id]
            reset_ids = [item for item in reset_set if item in run.nodes]
            for reset_id in reset_ids:
                item = run.nodes[reset_id]
                item.status = (
                    NodeStatus.blocked
                    if reset_id == "preflight" and not run.author_known
                    else NodeStatus.pending
                )
                item.attempts = 0
                item.artifact_path = None
                item.artifact_sha256 = None
                item.completed_at = None
                item.error = None
                self._clear_claim(item)
            run.approvals = [
                approval for approval in run.approvals
                if approval.node_id not in reset_set
            ]
            integrity_node = (
                (run.blocked_reason or "").removeprefix("artifact_changed:")
            )
            if integrity_node in reset_set:
                run.status = RunStatus.active
                run.blocked_reason = None
            self._derive_run_status(run)
            self._save_unlocked(run)
            return run

    def resume(self, run_id: str) -> BookRun:
        """Recover expired leases and recompute the durable run status."""
        with self._locked(run_id):
            run = self._load_unlocked(run_id)
            self._expire_claims(run)
            self._derive_run_status(run)
            self._save_unlocked(run)
            return run

    def add_nodes(self, run_id: str, nodes: Sequence[Node]) -> BookRun:
        """Append dynamically planned section/QA nodes after Gate 1."""
        with self._locked(run_id):
            run = self._load_unlocked(run_id)
            self._require_artifact_integrity_unlocked(run)
            additions = {node.id: node for node in nodes}
            if len(additions) != len(nodes):
                raise ValueError("new node ids must be unique")
            for node in additions.values():
                if (
                    node.status != NodeStatus.pending
                    or node.attempts != 0
                    or node.claimed_by is not None
                    or node.claim_token is not None
                    or node.claimed_at is not None
                    or node.lease_expires_at is not None
                    or node.artifact_path is not None
                    or node.artifact_sha256 is not None
                    or node.error is not None
                    or node.completed_at is not None
                ):
                    raise InvalidTransition(
                        f"new node must be pristine and pending: {node.id}"
                    )
                if node.id == "promote" and (
                    node.role != TaskRole.promote
                    or node.kind != NodeKind.coordinator
                    or node.depends_on != ["approve_promotion"]
                ):
                    raise InvalidTransition(
                        "promote must be the canonical promotion node"
                    )
                if node.role == TaskRole.promote and node.id != "promote":
                    raise InvalidTransition(
                        "promotion role is reserved for the canonical promote node"
                    )
            collisions = set(additions) & set(run.nodes)
            if collisions:
                raise ValueError(f"nodes already exist: {sorted(collisions)}")
            candidate = {**run.nodes, **additions}
            _validate_graph(candidate)
            run.nodes.update(additions)
            self._derive_run_status(run)
            self._save_unlocked(run)
            return run

    def approve_artifact(
        self,
        run_id: str,
        gate: ApprovalGate,
        artifact_path: Path | str,
        expected_sha256: str,
        approver: str,
    ) -> BookRun:
        """Complete an approval node only when the artifact bytes match exactly."""
        if not _SHA256.fullmatch(expected_sha256):
            raise ValueError("expected_sha256 must be a lowercase SHA-256")
        if not approver.strip() or "\x00" in approver:
            raise ValueError("approver is required")
        node_id = {
            ApprovalGate.structure: "approve_structure",
            ApprovalGate.promotion: "approve_promotion",
        }[gate]
        with self._locked(run_id):
            run = self._load_unlocked(run_id)
            self._require_artifact_integrity_unlocked(run)
            node = self._node(run, node_id)
            if node.kind != NodeKind.approval or not self._is_ready(run, node):
                raise InvalidTransition(f"approval gate is not ready: {gate.value}")
            artifact = self._artifact_in_run(run.id, artifact_path, must_exist=True)
            actual_sha = sha256_file(artifact)
            producer_id = {
                ApprovalGate.structure: "merge_structure",
                ApprovalGate.promotion: "stage",
            }[gate]
            producer = self._node(run, producer_id)
            producer_path = artifact.relative_to(
                self.run_dir(run.id).resolve()
            ).as_posix()
            if (
                producer.status != NodeStatus.completed
                or producer.artifact_path != producer_path
                or producer.artifact_sha256 != actual_sha
            ):
                raise InvalidTransition(
                    f"approval artifact is not the exact {producer_id} output"
                )
            if actual_sha != expected_sha256:
                raise ArtifactMismatch(
                    f"artifact changed: expected {expected_sha256}, got {actual_sha}"
                )
            relative = artifact.relative_to(self.run_dir(run.id).resolve()).as_posix()
            approval = Approval(
                gate=gate,
                node_id=node.id,
                artifact_path=relative,
                artifact_sha256=actual_sha,
                approver=approver,
            )
            run.approvals = [
                old for old in run.approvals if old.gate != gate
            ] + [approval]
            node.status = NodeStatus.completed
            node.artifact_path = relative
            node.artifact_sha256 = actual_sha
            node.completed_at = approval.approved_at
            self._derive_run_status(run)
            self._save_unlocked(run)
            return run

    def write_artifact(
        self,
        run_id: str,
        relative_path: Path | str,
        content: Mapping[str, Any] | BaseModel,
    ) -> Path:
        """Atomically write a JSON artifact inside a run for later approval."""
        relative = Path(relative_path)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or relative.parts[0] != "artifacts"
            or relative.suffix != ".json"
        ):
            raise WorkflowError("manual artifacts must be JSON under artifacts/")
        with self._locked(run_id):
            run = self._load_unlocked(run_id)
            protected = {approval.artifact_path for approval in run.approvals}
            protected.update(
                node.artifact_path for node in run.nodes.values()
                if node.status == NodeStatus.completed and node.artifact_path
            )
            if relative.as_posix() in protected:
                raise InvalidTransition("completed or approved artifacts are immutable")
            data = (
                content.model_dump(mode="json")
                if isinstance(content, BaseModel)
                else dict(content)
            )
            return self._write_json_artifact_unlocked(
                run, relative, data
            )

    def status(self, run_id: str) -> WorkflowSummary:
        with self._locked(run_id):
            run = self._load_unlocked(run_id)
            self._expire_claims(run)
            self._derive_run_status(run)
            self._save_unlocked(run)
            ready = [node.id for node in run.nodes.values() if self._is_ready(run, node)]
            waiting = [
                node.id for node in run.nodes.values()
                if node.kind == NodeKind.approval and self._is_ready(run, node)
            ]
            counts = Counter(node.status.value for node in run.nodes.values())
            return WorkflowSummary(
                run_id=run.id,
                status=run.status,
                blocked_reason=run.blocked_reason,
                source_name=run.source_name,
                source_sha256=run.source_sha256,
                author_id=run.author_id,
                author_known=run.author_known,
                ocr_job_id=run.ocr_job_id,
                node_counts=dict(sorted(counts.items())),
                ready_nodes=ready,
                claimed_nodes=[
                    node.id for node in run.nodes.values()
                    if node.status == NodeStatus.claimed
                ],
                failed_nodes=[
                    node.id for node in run.nodes.values()
                    if node.status == NodeStatus.failed
                ],
                waiting_approval=waiting,
                approvals=run.approvals,
                updated_at=run.updated_at,
            )

    def abort(self, run_id: str) -> BookRun:
        """Stop scheduling while retaining every artifact for inspection."""
        with self._locked(run_id):
            run = self._load_unlocked(run_id)
            if run.status == RunStatus.completed:
                raise InvalidTransition("a completed run cannot be aborted")
            run.status = RunStatus.aborted
            run.blocked_reason = "aborted"
            for node in run.nodes.values():
                if node.status == NodeStatus.claimed:
                    node.status = NodeStatus.pending
                    self._clear_claim(node)
            self._save_unlocked(run)
            return run

    def _bind_ocr_job(self, run: BookRun, ocr_job_id: str) -> None:
        from .book_ocr import validate_ocr_job
        checked = validate_ocr_job(run, ocr_job_id, self.ocr_jobs_root)
        run.ocr_job_id = ocr_job_id
        for node_id in ("plan_structure", "plan_folios", "plan_dedupe"):
            task = run.nodes[node_id].task
            assert task is not None
            task.inputs.update({
                "ocr_job_id": ocr_job_id,
                "pages": list(checked.page_numbers),
                "review_path": str(checked.review_path),
            })

    def set_ocr_job(self, run_id: str, ocr_job_id: str) -> BookRun:
        """Attach a reusable existing OCR job reference to the run."""
        safe_id(ocr_job_id, label="OCR job id")
        with self._locked(run_id):
            run = self._load_unlocked(run_id)
            if run.nodes["ocr"].status == NodeStatus.completed:
                raise InvalidTransition("OCR job is immutable after OCR completion")
            self._bind_ocr_job(run, ocr_job_id)
            self._save_unlocked(run)
            return run

    def record_promotion(
        self,
        run_id: str,
        commit_sha: str,
        manifest_sha256: str,
        committed_paths: Sequence[str],
    ) -> BookRun:
        """Durably finish a successfully committed promotion.

        This is separate from ``complete_task`` so a lease expiring immediately
        after ``git commit`` cannot make a safe, completed promotion rerun.
        """
        if not re.fullmatch(r"[0-9a-f]{40}([0-9a-f]{24})?", commit_sha):
            raise ValueError("commit_sha must be a Git object id")
        if not _SHA256.fullmatch(manifest_sha256):
            raise ValueError("manifest_sha256 must be a lowercase SHA-256")
        with self._locked(run_id):
            run = self._load_unlocked(run_id)
            self._require_artifact_integrity_unlocked(run)
            approval = next(
                (
                    item for item in run.approvals
                    if item.gate == ApprovalGate.promotion
                ),
                None,
            )
            if approval is None or approval.artifact_sha256 != manifest_sha256:
                raise InvalidTransition("exact Gate-2 approval is absent")
            manifest_path = self._artifact_in_run(
                run.id, approval.artifact_path, must_exist=True
            )
            if sha256_file(manifest_path) != manifest_sha256:
                raise InvalidTransition("Gate-2 approved manifest changed")
            manifest = StageManifest.model_validate_json(manifest_path.read_bytes())
            if (
                manifest.run_id != run.id
                or manifest.source_sha256 != run.source_sha256
            ):
                raise InvalidTransition("Gate-2 manifest identifies another run")
            expected_paths = [entry.target_path for entry in manifest.entries]
            if len(expected_paths) != len(set(expected_paths)):
                raise InvalidTransition("Gate-2 manifest target paths are not unique")
            if list(committed_paths) != expected_paths:
                raise InvalidTransition(
                    "committed_paths do not exactly match the Gate-2 manifest"
                )

            def git_read(*arguments: str) -> bytes:
                completed = subprocess.run(
                    ["git", *arguments],
                    cwd=self.repo_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                if completed.returncode:
                    detail = completed.stderr.decode(
                        "utf-8", errors="replace"
                    ).strip()
                    raise InvalidTransition(
                        f"cannot verify promotion commit: {detail}"
                    )
                return completed.stdout

            head = git_read("rev-parse", "--verify", "HEAD").decode().strip()
            if head != commit_sha:
                raise InvalidTransition("promotion commit is not current HEAD")
            parents = git_read(
                "rev-list", "--parents", "-n", "1", commit_sha
            ).decode().split()
            if (
                len(parents) != 2
                or parents[0] != commit_sha
                or parents[1] != manifest.base_commit
            ):
                raise InvalidTransition(
                    "promotion commit parent is not the Gate-2 base commit"
                )
            changed_raw = git_read(
                "diff-tree", "--root", "--no-commit-id", "--name-only",
                "-r", "-z", commit_sha,
            )
            changed_paths = [
                os.fsdecode(path) for path in changed_raw.split(b"\0") if path
            ]
            if (
                len(changed_paths) != len(expected_paths)
                or set(changed_paths) != set(expected_paths)
            ):
                raise InvalidTransition(
                    "promotion commit paths do not match the Gate-2 manifest"
                )
            for entry in manifest.entries:
                blob = git_read("cat-file", "blob", f"{commit_sha}:{entry.target_path}")
                if hashlib.sha256(blob).hexdigest() != entry.sha256:
                    raise InvalidTransition(
                        f"promotion commit blob differs from manifest: {entry.target_path}"
                    )
            node = self._node(run, "promote")
            if node.status not in {NodeStatus.pending, NodeStatus.claimed}:
                raise InvalidTransition("promotion node is not recordable")
            result = self._write_json_artifact_unlocked(
                run,
                Path("artifacts/promote.json"),
                {
                    "commit_sha": commit_sha,
                    "manifest_sha256": manifest_sha256,
                    "committed_paths": list(committed_paths),
                    "pushed": False,
                },
            )
            node.status = NodeStatus.completed
            node.artifact_path = result.relative_to(
                self.run_dir(run.id).resolve()
            ).as_posix()
            node.artifact_sha256 = sha256_file(result)
            node.completed_at = utcnow()
            node.error = None
            self._clear_claim(node)
            run.commit_sha = commit_sha
            self._derive_run_status(run)
            self._save_unlocked(run)
            return run

    def _is_ready(self, run: BookRun, node: Node) -> bool:
        if (
            run.status == RunStatus.aborted
            or not run.author_known
            or (
                run.status == RunStatus.blocked
                and (run.blocked_reason or "").startswith("artifact_changed:")
            )
        ):
            return False
        return (
            node.status == NodeStatus.pending
            and all(
                run.nodes[dependency].status
                in {NodeStatus.completed, NodeStatus.skipped}
                for dependency in node.depends_on
            )
        )

    def _derive_run_status(self, run: BookRun) -> None:
        if run.status == RunStatus.aborted:
            return
        if not run.author_known:
            run.status = RunStatus.blocked
            run.blocked_reason = "unknown_author"
            return
        if (
            run.status == RunStatus.blocked
            and (run.blocked_reason or "").startswith("artifact_changed:")
        ):
            return
        changed = self._changed_artifact(run)
        if changed is not None:
            run.status = RunStatus.blocked
            run.blocked_reason = f"artifact_changed:{changed}"
            return
        terminal_failures = [
            node for node in run.nodes.values()
            if node.status in {NodeStatus.failed, NodeStatus.blocked}
        ]
        if terminal_failures:
            run.status = RunStatus.blocked
            run.blocked_reason = f"failed_node:{terminal_failures[0].id}"
            return
        approval_ready = [
            node for node in run.nodes.values()
            if node.kind == NodeKind.approval and self._is_ready(run, node)
        ]
        if approval_ready:
            run.status = RunStatus.waiting_approval
            run.blocked_reason = None
            return
        promote_node = run.nodes.get("promote")
        if (
            promote_node is not None
            and promote_node.role == TaskRole.promote
            and promote_node.kind == NodeKind.coordinator
            and promote_node.depends_on == ["approve_promotion"]
            and promote_node.status == NodeStatus.completed
            and promote_node.artifact_path == "artifacts/promote.json"
            and run.commit_sha is not None
            and all(
                node.status in {NodeStatus.completed, NodeStatus.skipped}
                for node in run.nodes.values()
            )
        ):
            run.status = RunStatus.completed
            run.blocked_reason = None
            run.completed_at = run.completed_at or utcnow()
            return
        run.status = RunStatus.active
        run.blocked_reason = None
        run.completed_at = None

    def _expire_claims(self, run: BookRun) -> bool:
        now = utcnow()
        changed = False
        for node in run.nodes.values():
            if (
                node.status == NodeStatus.claimed
                and node.lease_expires_at is not None
                and node.lease_expires_at <= now
            ):
                node.status = (
                    NodeStatus.pending
                    if node.attempts < node.max_attempts
                    else NodeStatus.failed
                )
                node.error = "claim lease expired"
                self._clear_claim(node)
                changed = True
        return changed

    def _claimed_node(
        self, run: BookRun, node_id: str, claim_token: str
    ) -> Node:
        self._require_artifact_integrity_unlocked(run)
        node = self._node(run, node_id)
        if node.status != NodeStatus.claimed or node.claim_token != claim_token:
            raise InvalidTransition("claim is absent, expired, or token is invalid")
        if node.lease_expires_at is None or node.lease_expires_at <= utcnow():
            node.status = (
                NodeStatus.pending
                if node.attempts < node.max_attempts
                else NodeStatus.failed
            )
            node.error = "claim lease expired"
            self._clear_claim(node)
            self._derive_run_status(run)
            self._save_unlocked(run)
            raise InvalidTransition("claim lease expired")
        return node

    def _changed_artifact(self, run: BookRun) -> str | None:
        """Return the first completed node whose recorded artifact is not intact."""
        for completed in run.nodes.values():
            if completed.status != NodeStatus.completed or not completed.artifact_path:
                continue
            try:
                artifact = self._artifact_in_run(
                    run.id, completed.artifact_path, must_exist=True
                )
                intact = sha256_file(artifact) == completed.artifact_sha256
            except (OSError, WorkflowError):
                intact = False
            if not intact:
                return completed.id
        return None

    def _require_artifact_integrity_unlocked(self, run: BookRun) -> None:
        """Persist an integrity block and reject state advancement until reset."""
        if (
            run.status == RunStatus.blocked
            and (run.blocked_reason or "").startswith("artifact_changed:")
        ):
            changed = (run.blocked_reason or "").removeprefix("artifact_changed:")
            raise InvalidTransition(
                f"workflow artifact changed; reset {changed} before continuing"
            )
        changed = self._changed_artifact(run)
        if changed is None:
            return
        run.status = RunStatus.blocked
        run.blocked_reason = f"artifact_changed:{changed}"
        self._save_unlocked(run)
        raise InvalidTransition(
            f"workflow artifact changed; reset {changed} before continuing"
        )

    @staticmethod
    def _clear_claim(node: Node) -> None:
        node.claimed_by = None
        node.claim_token = None
        node.claimed_at = None
        node.lease_expires_at = None

    @staticmethod
    def _node(run: BookRun, node_id: str) -> Node:
        safe_id(node_id, label="node id")
        try:
            return run.nodes[node_id]
        except KeyError as exc:
            raise WorkflowError(f"unknown node: {node_id}") from exc

    @staticmethod
    def _descendants(run: BookRun, node_id: str) -> list[str]:
        found: list[str] = []
        queue = deque([node_id])
        seen = {node_id}
        while queue:
            current = queue.popleft()
            for candidate in run.nodes.values():
                if current in candidate.depends_on and candidate.id not in seen:
                    seen.add(candidate.id)
                    found.append(candidate.id)
                    queue.append(candidate.id)
        return found

    def _artifact_in_run(
        self,
        run_id: str,
        artifact_path: Path | str,
        *,
        must_exist: bool,
    ) -> Path:
        root = self.run_dir(run_id).resolve()
        supplied = Path(artifact_path)
        candidate = supplied if supplied.is_absolute() else root / supplied
        candidate = candidate.resolve(strict=must_exist)
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise WorkflowError("artifact must be inside the workflow run") from exc
        if must_exist and not candidate.is_file():
            raise WorkflowError(f"artifact is not a file: {candidate}")
        return candidate

    def _write_json_artifact_unlocked(
        self,
        run: BookRun,
        relative_path: Path,
        data: Mapping[str, Any],
    ) -> Path:
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise WorkflowError("artifact path must be a safe relative path")
        path = self._artifact_in_run(
            run.id, relative_path, must_exist=False
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            data, ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"
        self._atomic_text(path, payload)
        return path

    @contextmanager
    def _locked(self, run_id: str) -> Iterator[None]:
        directory = self.run_dir(run_id)
        directory.mkdir(parents=True, exist_ok=True)
        lock_path = directory / ".lock"
        with lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _load_unlocked(self, run_id: str) -> BookRun:
        path = self.run_dir(run_id) / "run.json"
        if not path.is_file():
            raise RunNotFound(f"unknown run: {run_id}")
        return BookRun.model_validate_json(path.read_text(encoding="utf-8"))

    def _save_unlocked(self, run: BookRun) -> None:
        run.updated_at = utcnow()
        payload = run.model_dump_json(indent=2) + "\n"
        self._atomic_text(self.run_dir(run.id) / "run.json", payload)

    @staticmethod
    def _atomic_text(path: Path, content: str) -> None:
        temp = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
        try:
            with temp.open("w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temp.exists():
                temp.unlink()


__all__ = [
    "Approval",
    "ApprovalGate",
    "ArtifactMismatch",
    "BookRun",
    "BookWorkflow",
    "InvalidTransition",
    "Node",
    "NodeKind",
    "NodeStatus",
    "RunNotFound",
    "RunStatus",
    "StageEntry",
    "StageManifest",
    "Task",
    "TaskClaim",
    "TaskRole",
    "WorkflowError",
    "WorkflowSummary",
    "safe_id",
    "sha256_file",
]
