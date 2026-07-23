"""Build and complete a Gate-2 manifest from an isolated staged source tree."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .book_promotion import verify_stage
from .book_workflow import (
    BookWorkflow,
    StageEntry,
    StageManifest,
    WorkflowError,
    sha256_file,
)


def complete_stage(
    workflow: BookWorkflow,
    run_id: str,
    claim_token: str,
    retained_book_scan: str,
    commit_message: str,
) -> StageManifest:
    run = workflow.load_run(run_id)
    stage_root = workflow.run_dir(run_id) / "stage"
    author_root = (
        stage_root / "archives" / "authors" / run.author_id
    )
    if not author_root.is_dir():
        raise WorkflowError(f"staged author tree is absent: {author_root}")
    entries = []
    for staged in sorted(path for path in author_root.rglob("*") if path.is_file()):
        staged_relative = staged.relative_to(workflow.run_dir(run_id)).as_posix()
        target_relative = staged.relative_to(stage_root).as_posix()
        target = workflow.repo_root / target_relative
        if target.is_file():
            entries.append(
                StageEntry(
                    staged_path=staged_relative,
                    target_path=target_relative,
                    sha256=sha256_file(staged),
                    operation="update",
                    prior_sha256=sha256_file(target),
                )
            )
        else:
            entries.append(
                StageEntry(
                    staged_path=staged_relative,
                    target_path=target_relative,
                    sha256=sha256_file(staged),
                    operation="create",
                )
            )
    if not entries:
        raise WorkflowError("staged author tree contains no source files")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workflow.repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    manifest = StageManifest(
        run_id=run.id,
        source_sha256=run.source_sha256,
        base_commit=head,
        entries=entries,
        retained_book_scan=retained_book_scan,
        validation_commands=[["python3", "pipeline/validate.py"]],
        commit_message=commit_message,
    )
    path = workflow.write_artifact(
        run_id, "artifacts/staging-manifest.json", manifest
    )
    verify_stage(workflow, run_id, path, require_approval=False)
    workflow.complete_task(
        run_id, "stage", claim_token, artifact_path=path
    )
    return manifest


__all__ = ["complete_stage"]
