"""Repository-serialized, journaled wrapper around Gate-2 promotion."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .book_journal import load_journal, promotion_lock, write_journal
from .book_promotion import (
    PromotionError,
    PromotionResult,
    _allowed_target,
    _atomic_copy,
    _exact_gate_approval,
    _git,
    _promote_transaction,
    _unstage,
    verify_stage,
)
from .book_workflow import BookWorkflow, StageEntry, StageManifest, sha256_file


def _recovery_entries(
    workflow: BookWorkflow,
    run_id: str,
    manifest_file: Path,
    manifest_hash: str,
    journal: dict[str, Any],
) -> tuple[StageManifest, list[tuple[StageEntry, Path, Path]]]:
    """Rebuild recovery paths from the approved manifest, never the journal."""
    manifest = StageManifest.model_validate_json(manifest_file.read_bytes())
    run = workflow.load_run(run_id)
    if manifest.run_id != run.id or manifest.source_sha256 != run.source_sha256:
        raise PromotionError("approved manifest identifies another run or source PDF")
    if (
        journal.get("run_id") != run_id
        or journal.get("base_commit") != manifest.base_commit
        or journal.get("manifest_sha256") != manifest_hash
    ):
        raise PromotionError("promotion journal does not match the approved manifest")

    raw_entries = journal.get("entries")
    if not isinstance(raw_entries, list) or len(raw_entries) != len(manifest.entries):
        raise PromotionError("promotion journal is malformed")

    repo_root = workflow.repo_root.resolve()
    authors_root = workflow.authors_root.resolve()
    run_root = workflow.run_dir(run_id).resolve()
    backup_root_path = run_root / "promotion-backup"
    if backup_root_path.is_symlink():
        raise PromotionError("promotion backup root may not be a symlink")
    backup_root = backup_root_path.resolve()
    try:
        backup_root.relative_to(run_root)
    except ValueError as exc:
        raise PromotionError("promotion backup root escaped its run") from exc
    seen: set[str] = set()
    rebuilt: list[tuple[StageEntry, Path, Path]] = []
    for entry, raw in zip(manifest.entries, raw_entries, strict=True):
        if not isinstance(raw, dict):
            raise PromotionError("promotion journal entry is malformed")
        if entry.target_path in seen:
            raise PromotionError(f"duplicate target path: {entry.target_path}")
        seen.add(entry.target_path)

        target_rel = Path(entry.target_path)
        if not _allowed_target(target_rel, run.author_id):
            raise PromotionError(
                f"target is not an allowed archive source: {entry.target_path}"
            )
        unresolved_target = repo_root / target_rel
        cursor = unresolved_target.parent
        while cursor != repo_root:
            if cursor.is_symlink():
                raise PromotionError(
                    f"target has symlink parent: {entry.target_path}"
                )
            cursor = cursor.parent
        if unresolved_target.is_symlink():
            raise PromotionError(f"target may not be a symlink: {entry.target_path}")
        target = unresolved_target.resolve(strict=False)
        try:
            target.relative_to(authors_root)
        except ValueError as exc:
            raise PromotionError("approved target escaped the authors root") from exc

        backup = backup_root / target_rel
        try:
            backup.relative_to(backup_root)
        except ValueError as exc:
            raise PromotionError("promotion backup escaped its run backup root") from exc
        cursor = backup.parent
        while cursor != backup_root:
            if cursor.is_symlink():
                raise PromotionError(
                    f"promotion backup has symlink parent: {entry.target_path}"
                )
            cursor = cursor.parent
        if backup.is_symlink():
            raise PromotionError(
                f"promotion backup may not be a symlink: {entry.target_path}"
            )

        expected_journal = {
            "target_path": entry.target_path,
            "sha256": entry.sha256,
            "prior_sha256": entry.prior_sha256,
            "existed": entry.operation == "update",
            "backup_path": str(backup),
        }
        if any(raw.get(key) != value for key, value in expected_journal.items()):
            raise PromotionError(
                "promotion journal entry does not match approved manifest: "
                f"{entry.target_path}"
            )
        if set(raw) != set(expected_journal):
            raise PromotionError(
                f"promotion journal entry has unexpected fields: {entry.target_path}"
            )
        rebuilt.append((entry, target, backup))
    return manifest, rebuilt


def _prepare_journal(workflow: BookWorkflow, verified) -> dict[str, object]:
    run_root = workflow.run_dir(verified.manifest.run_id)
    backup_root = run_root / "promotion-backup"
    backup_root.mkdir(parents=True, exist_ok=True)
    entries = []
    for entry, target in zip(
        verified.manifest.entries, verified.target_files, strict=True
    ):
        backup = backup_root / entry.target_path
        existed = target.is_file()
        if existed:
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        entries.append(
            {
                "target_path": entry.target_path,
                "sha256": entry.sha256,
                "prior_sha256": entry.prior_sha256,
                "existed": existed,
                "backup_path": str(backup),
            }
        )
    journal: dict[str, object] = {
        "version": 1,
        "phase": "prepared",
        "run_id": verified.manifest.run_id,
        "base_commit": verified.manifest.base_commit,
        "manifest_sha256": verified.manifest_sha256,
        "entries": entries,
    }
    write_journal(run_root, journal)
    return journal


def recover_promotion(
    workflow: BookWorkflow,
    run_id: str,
    manifest_path: str | Path,
) -> PromotionResult | dict[str, object]:
    """Roll back a partial write, or record an exact already-created commit."""
    run_root = workflow.run_dir(run_id)
    with promotion_lock(workflow.repo_root):
        journal = load_journal(run_root)
        if journal is None:
            raise PromotionError("no promotion journal exists")
        supplied = Path(manifest_path)
        if not supplied.is_absolute():
            supplied = run_root / supplied
        manifest_file = supplied.resolve(strict=True)
        manifest_hash = _exact_gate_approval(workflow, run_id, manifest_file)
        manifest, entries = _recovery_entries(
            workflow, run_id, manifest_file, manifest_hash, journal
        )
        base = manifest.base_commit
        head = _git(workflow.repo_root, "rev-parse", "HEAD").stdout.strip()
        targets = [entry.target_path for entry, _, _ in entries]

        if head == base:
            for entry, _, backup in entries:
                if entry.operation != "update":
                    continue
                if not backup.is_file():
                    raise PromotionError("required promotion backup is missing")
                if sha256_file(backup) != entry.prior_sha256:
                    raise PromotionError("required promotion backup changed")
            _unstage(workflow.repo_root, targets)
            for entry, target, backup in reversed(entries):
                if entry.operation == "update":
                    _atomic_copy(backup, target)
                elif target.exists():
                    target.unlink()
            journal["phase"] = "rolled_back"
            write_journal(run_root, journal)
            return {"run_id": run_id, "recovered": "rolled_back"}

        parent = _git(workflow.repo_root, "rev-parse", f"{head}^").stdout.strip()
        if parent != base:
            raise PromotionError(
                "repository moved beyond the journal; human Git recovery is required"
            )
        expected_changed = {
            entry.target_path
            for entry, _, _ in entries
            if entry.prior_sha256 != entry.sha256
        }
        actual_changed = set(
            _git(
                workflow.repo_root,
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                head,
            ).stdout.splitlines()
        )
        if actual_changed != expected_changed:
            raise PromotionError("journaled commit path set does not match HEAD")
        for entry, target, _ in entries:
            if not target.is_file() or sha256_file(target) != entry.sha256:
                raise PromotionError("journaled commit bytes do not match HEAD")
        workflow.record_promotion(run_id, head, manifest_hash, targets)
        journal["phase"] = "recorded"
        journal["commit_sha"] = head
        write_journal(run_root, journal)
        return PromotionResult(run_id, manifest_hash, head, tuple(targets))


def promote(
    workflow: BookWorkflow,
    run_id: str,
    manifest_path: str | Path,
    claim_token: str,
) -> PromotionResult:
    """Serialize and journal the exact Gate-2 transaction; never push."""
    run_root = workflow.run_dir(run_id)
    with promotion_lock(workflow.repo_root):
        existing = load_journal(run_root)
        if existing and existing.get("phase") not in {"rolled_back"}:
            raise PromotionError(
                "unfinished promotion journal exists; run recover-promotion first"
            )
        verified = verify_stage(
            workflow, run_id, manifest_path, require_approval=True
        )
        journal = _prepare_journal(workflow, verified)
        try:
            result = _promote_transaction(
                workflow, run_id, manifest_path, claim_token
            )
        except Exception:
            head = _git(
                workflow.repo_root, "rev-parse", "HEAD", check=False
            ).stdout.strip()
            journal["phase"] = (
                "commit_pending_record"
                if head != verified.manifest.base_commit
                else "rolled_back"
            )
            write_journal(run_root, journal)
            raise
        journal["phase"] = "recorded"
        journal["commit_sha"] = result.commit_sha
        write_journal(run_root, journal)
        return result


__all__ = ["promote", "recover_promotion"]
