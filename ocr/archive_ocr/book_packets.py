"""Build immutable prompt packets for claimed built-in sub-agent tasks."""
from __future__ import annotations

from pathlib import Path

from .agent_profiles import resolve as resolve_routing
from .book_ocr import validate_ocr_job
from .book_prompts import (
    AGENT_PROFILE_BY_ROLE,
    AgentPromptRequest,
    AgentRole,
    TaskPage,
    build_prompt,
)
from .book_workflow import (
    BookWorkflow,
    InvalidTransition,
    NodeStatus,
    TaskRole,
    WorkflowError,
)


AGENT_ROLE_BY_TASK: dict[TaskRole, AgentRole] = {
    TaskRole.structure: AgentRole.structure,
    TaskRole.folio: AgentRole.folio,
    TaskRole.dedupe: AgentRole.dedupe,
    TaskRole.reconcile: AgentRole.section_reconciler,
    TaskRole.footnote: AgentRole.footnote_sweep,
    TaskRole.verify: AgentRole.targeted_verifier,
}


def build_task_packet(
    workflow: BookWorkflow,
    run_id: str,
    node_id: str,
    claim_token: str,
) -> dict[str, object]:
    """Return profile, result path, and prompt for one claimed leaf task."""
    run = workflow.load_run(run_id)
    try:
        node = run.nodes[node_id]
    except KeyError as exc:
        raise WorkflowError(f"unknown node: {node_id}") from exc
    if (
        node.status != NodeStatus.claimed
        or node.claim_token != claim_token
        or node.task is None
    ):
        raise InvalidTransition("task must be claimed with this token first")
    try:
        agent_role = AGENT_ROLE_BY_TASK[node.role]
    except KeyError as exc:
        raise InvalidTransition(f"{node.role.value} is a coordinator task") from exc
    if not run.ocr_job_id:
        raise InvalidTransition("run has no reusable OCR job attached")
    checked = validate_ocr_job(run, run.ocr_job_id, workflow.ocr_jobs_root)

    page_numbers = node.task.inputs.get("pages")
    if page_numbers is None:
        images = list(checked.pages)
    else:
        wanted = {int(page) for page in page_numbers}
        images = [
            path for path in checked.pages
            if int(path.stem.split("-")[1]) in wanted
        ]
        found = {int(path.stem.split("-")[1]) for path in images}
        if found != wanted:
            raise WorkflowError(
                f"OCR job is missing assigned page images: {sorted(wanted - found)}"
            )
    if not images:
        raise WorkflowError(f"OCR job {run.ocr_job_id!r} has no rendered page images")

    artifact_ref = (
        Path("tasks") / node.id / f"attempt-{node.attempts}" / "result.json"
    )
    output_path = (workflow.run_dir(run.id) / artifact_ref).resolve()
    relative_result = str(output_path)
    pages = []
    for image in images:
        page = int(image.stem.split("-")[1])
        ocr_path = checked.directory / "ocr" / "ensemble" / f"{image.stem}.txt"
        pages.append(
            TaskPage(
                page=page,
                image_path=str(image),
                ocr_path=str(ocr_path) if ocr_path.is_file() else None,
            )
        )
    review = checked.review_path
    catalogue = workflow.repo_root / "archives" / "index.json"
    request = AgentPromptRequest(
        task_id=node.task.id,
        role=agent_role,
        result_path=relative_result,
        pages=pages,
        review_path=str(review) if review.is_file() else None,
        catalogue_index_path=(
            str(catalogue)
            if catalogue.is_file()
            else str(workflow.authors_root)
        ),
        task_payload=node.task.inputs,
    )
    routing = resolve_routing(
        node.task.capability,
        preferred_model=node.task.preferred_model,
        reasoning_effort=node.task.reasoning_effort,
    )
    return {
        "run_id": run.id,
        "node_id": node.id,
        "agent_role": agent_role.value,
        "agent_profile": AGENT_PROFILE_BY_ROLE[agent_role],
        "profile_set": routing.profile,
        "capability": routing.capability,
        "model": routing.model,
        "reasoning_effort": routing.reasoning_effort,
        "result_path": relative_result,
        "artifact_ref": artifact_ref.as_posix(),
        "prompt": build_prompt(request),
    }


__all__ = ["AGENT_ROLE_BY_TASK", "build_task_packet"]
