"""Guarded Gate-2 promotion for staged scanned-book sources.

Promotion is intentionally the only component allowed to write canonical
``archives/authors`` paths. It verifies the exact approved manifest, refuses
dirty or changed targets, validates the archive, commits only the manifest
paths, and never pushes.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .book_journal import load_journal, promotion_lock, write_journal
from .book_workflow import (
    ApprovalGate,
    ArtifactMismatch,
    BookWorkflow,
    InvalidTransition,
    StageEntry,
    StageManifest,
    WorkflowError,
    sha256_file,
)


class PromotionError(WorkflowError):
    """The staged tree is unsafe, stale, or invalid."""


@dataclass(frozen=True)
class VerifiedStage:
    manifest_path: Path
    manifest_sha256: str
    manifest: StageManifest
    staged_files: tuple[Path, ...]
    target_files: tuple[Path, ...]


@dataclass(frozen=True)
class PromotionResult:
    run_id: str
    manifest_sha256: str
    commit_sha: str
    committed_paths: tuple[str, ...]


def _git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise PromotionError(f"git {' '.join(args)} failed: {detail}")
    return completed


def _allowed_target(target: Path, author_id: str) -> bool:
    parts = target.parts
    if parts[:3] != ("archives", "authors", author_id):
        return False
    relative = parts[3:]
    if len(relative) < 2:
        return False
    if relative[0] == "_source_books":
        return len(relative) == 2 and target.suffix.lower() == ".pdf"
    try:
        from .book_workflow import safe_id
        safe_id(relative[0], label="work id")
    except ValueError:
        return False
    if target.name in {"reader.html", "reader.epub"}:
        return False
    if len(relative) == 2:
        return (
            target.name in {"metadata.json", "text.txt"}
            or target.suffix.lower() in {".pdf", ".html"}
        )
    return (
        len(relative) == 3
        and relative[1] == "extracted"
        and target.suffix.lower() == ".html"
    )


def _exact_gate_approval(
    workflow: BookWorkflow,
    run_id: str,
    manifest_path: Path,
) -> str:
    run = workflow.load_run(run_id)
    approval = next(
        (item for item in run.approvals if item.gate == ApprovalGate.promotion),
        None,
    )
    if approval is None:
        raise InvalidTransition("Gate 2 promotion approval is required")
    try:
        relative = manifest_path.relative_to(workflow.run_dir(run_id).resolve()).as_posix()
    except ValueError as exc:
        raise PromotionError("manifest must be inside this run") from exc
    actual = sha256_file(manifest_path)
    if approval.artifact_path != relative or approval.artifact_sha256 != actual:
        raise ArtifactMismatch("manifest is not the exact Gate-2-approved artifact")
    return actual


def verify_stage(
    workflow: BookWorkflow,
    run_id: str,
    manifest_path: str | Path,
    *,
    require_approval: bool = True,
) -> VerifiedStage:
    """Validate manifest paths, hashes, baseline, operations, and staged sources."""
    supplied = Path(manifest_path)
    if not supplied.is_absolute():
        supplied = workflow.run_dir(run_id) / supplied
    manifest_file = supplied.resolve(strict=True)
    run_root = workflow.run_dir(run_id).resolve()
    try:
        manifest_file.relative_to(run_root)
    except ValueError as exc:
        raise PromotionError("manifest must be inside this run") from exc

    manifest_hash = (
        _exact_gate_approval(workflow, run_id, manifest_file)
        if require_approval else sha256_file(manifest_file)
    )
    manifest = StageManifest.model_validate_json(manifest_file.read_bytes())
    run = workflow.load_run(run_id)
    if manifest.run_id != run.id or manifest.source_sha256 != run.source_sha256:
        raise PromotionError("manifest identifies another run or source PDF")
    head = _git(workflow.repo_root, "rev-parse", "HEAD").stdout.strip()
    if manifest.base_commit != head:
        raise PromotionError(
            f"repository moved since staging: expected {manifest.base_commit}, got {head}"
        )
    if not manifest.entries:
        raise PromotionError("manifest contains no source files")

    staged_files: list[Path] = []
    target_files: list[Path] = []
    seen_targets: set[str] = set()
    entry_by_target: dict[str, StageEntry] = {}
    for entry in manifest.entries:
        if entry.target_path in seen_targets:
            raise PromotionError(f"duplicate target path: {entry.target_path}")
        seen_targets.add(entry.target_path)
        entry_by_target[entry.target_path] = entry
        target_rel = Path(entry.target_path)
        if not _allowed_target(target_rel, run.author_id):
            raise PromotionError(f"target is not an allowed archive source: {entry.target_path}")
        expected_staged = Path("stage") / target_rel
        if Path(entry.staged_path) != expected_staged:
            raise PromotionError(
                f"staged path must mirror target under stage/: {entry.staged_path}"
            )
        staged = (run_root / entry.staged_path).resolve(strict=True)
        unresolved_target = workflow.repo_root / entry.target_path
        cursor = unresolved_target.parent
        while cursor != workflow.repo_root:
            if cursor.is_symlink():
                raise PromotionError(f"target has symlink parent: {entry.target_path}")
            cursor = cursor.parent
        if unresolved_target.is_symlink():
            raise PromotionError(f"target may not be a symlink: {entry.target_path}")
        target = unresolved_target.resolve(strict=False)
        try:
            staged.relative_to(run_root / "stage")
            target.relative_to(workflow.authors_root)
        except ValueError as exc:
            raise PromotionError("manifest path escaped its allowed root") from exc
        if not staged.is_file() or sha256_file(staged) != entry.sha256:
            raise ArtifactMismatch(f"staged file changed: {entry.staged_path}")

        dirty = _git(
            workflow.repo_root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            entry.target_path,
        ).stdout
        if dirty:
            raise PromotionError(f"refusing to overwrite dirty target: {entry.target_path}")

        if entry.operation == "create":
            if target.exists():
                raise PromotionError(f"create target already exists: {entry.target_path}")
        else:
            if not target.is_file():
                raise PromotionError(f"update target is absent: {entry.target_path}")
            if sha256_file(target) != entry.prior_sha256:
                raise ArtifactMismatch(f"update target changed: {entry.target_path}")
        staged_files.append(staged)
        target_files.append(target)

    if (
        manifest.retained_book_scan is None
        or manifest.retained_book_scan not in entry_by_target
        or Path(manifest.retained_book_scan).suffix.lower() != ".pdf"
    ):
        raise PromotionError("manifest must retain the original book scan as a PDF entry")
    retained = entry_by_target[manifest.retained_book_scan]
    if retained.sha256 != run.source_sha256:
        raise ArtifactMismatch("retained original scan does not match source PDF checksum")

    for target_name, entry in entry_by_target.items():
        target = Path(target_name)
        if target.name != "metadata.json":
            continue
        text_target = (target.parent / "text.txt").as_posix()
        if text_target not in entry_by_target:
            raise PromotionError(f"metadata has no matching text.txt: {target.parent}")
        metadata = json.loads((run_root / entry.staged_path).read_text(encoding="utf-8"))
        for field in ("pdf", "html"):
            source_name = (metadata.get("source") or {}).get(field)
            if source_name:
                source_path = Path(source_name)
                if source_path.is_absolute() or ".." in source_path.parts:
                    raise PromotionError(f"unsafe metadata source.{field}: {source_name}")
                source_target = (target.parent / source_path).as_posix()
                if source_target not in entry_by_target:
                    raise PromotionError(
                        f"metadata source.{field} is absent from stage: {source_target}"
                    )

    staged_authors = run_root / "stage" / "archives" / "authors"
    if not any(staged_authors.glob("*/*/metadata.json")):
        raise PromotionError("staged manifest contains no validated archive work")
    staged_validation = subprocess.run(
        [
            sys.executable,
            str(workflow.repo_root / "pipeline" / "validate.py"),
            "--authors-root",
            str(staged_authors),
        ],
        cwd=workflow.repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if staged_validation.returncode:
        raise PromotionError(
            "staged archive validation failed:\n" + staged_validation.stdout
        )
    return VerifiedStage(
        manifest_path=manifest_file,
        manifest_sha256=manifest_hash,
        manifest=manifest,
        staged_files=tuple(staged_files),
        target_files=tuple(target_files),
    )


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.ocr-promote.tmp")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def _restore_targets(
    verified: VerifiedStage,
    backups: dict[Path, Path | None],
) -> None:
    for target in reversed(verified.target_files):
        if target not in backups:
            continue
        backup = backups[target]
        if backup is None:
            if target.exists():
                target.unlink()
        else:
            _atomic_copy(backup, target)


def _unstage(repo_root: Path, target_paths: Iterable[str]) -> None:
    completed = _git(
        repo_root,
        "restore",
        "--staged",
        "--source=HEAD",
        "--",
        *target_paths,
        check=False,
    )
    if completed.returncode:
        raise PromotionError(
            "promotion failed and exact-path index cleanup also failed: "
            + (completed.stderr.strip() or completed.stdout.strip())
        )


def _promote_transaction(
    workflow: BookWorkflow,
    run_id: str,
    manifest_path: str | Path,
    claim_token: str,
) -> PromotionResult:
    """Promote, validate, exact-path commit, record completion; never push."""
    workflow.renew_claim(run_id, "promote", claim_token, lease_seconds=3600)
    verified = verify_stage(workflow, run_id, manifest_path, require_approval=True)
    run_root = workflow.run_dir(run_id)
    backup_root = run_root / "promotion-backup"
    backup_root.mkdir(parents=True, exist_ok=True)
    backups: dict[Path, Path | None] = {}
    targets = [entry.target_path for entry in verified.manifest.entries]

    try:
        for entry, staged, target in zip(
            verified.manifest.entries,
            verified.staged_files,
            verified.target_files,
            strict=True,
        ):
            if target.exists():
                backup = backup_root / entry.target_path
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                backups[target] = backup
            else:
                backups[target] = None
            _atomic_copy(staged, target)

        validation = subprocess.run(
            [sys.executable, str(workflow.repo_root / "pipeline" / "validate.py")],
            cwd=workflow.repo_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if validation.returncode:
            raise PromotionError("canonical validation failed:\n" + validation.stdout)

        _git(workflow.repo_root, "add", "--", *targets)
        _git(
            workflow.repo_root,
            "commit",
            "--only",
            "-m",
            verified.manifest.commit_message,
            "--",
            *targets,
        )
        commit_sha = _git(workflow.repo_root, "rev-parse", "HEAD").stdout.strip()
    except Exception:
        try:
            _unstage(workflow.repo_root, targets)
        finally:
            _restore_targets(verified, backups)
        raise

    workflow.record_promotion(
        run_id,
        commit_sha,
        verified.manifest_sha256,
        targets,
    )
    return PromotionResult(
        run_id=run_id,
        manifest_sha256=verified.manifest_sha256,
        commit_sha=commit_sha,
        committed_paths=tuple(targets),
    )


__all__ = [
    "PromotionError",
    "PromotionResult",
    "VerifiedStage",
    "verify_stage",
]
