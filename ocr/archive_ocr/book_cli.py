"""JSON CLI adapter for the persistent scanned-book workflow."""
from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from enum import Enum
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .book_workflow import (
    ApprovalGate, BookWorkflow, Node, NodeKind, WorkflowError, sha256_file,
)


def configure_parser(parser: argparse.ArgumentParser) -> None:
    """Register ``archive_ocr book`` options and subcommands."""
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--work-root", type=Path, default=None)
    parser.add_argument("--ocr-jobs-root", type=Path, default=None)
    commands = parser.add_subparsers(dest="book_command", required=True)

    init = commands.add_parser("init", help="initialize a scanned-book graph")
    init.add_argument("pdf", type=Path)
    init.add_argument("--author", required=True)
    init.add_argument("--run-id")
    init.add_argument("--ocr-job")
    commands.add_parser("list", help="list persisted book runs")

    for name in ("status", "ready", "resume", "refresh-author", "abort"):
        command = commands.add_parser(name)
        command.add_argument("run_id")
        if name == "ready":
            command.add_argument("--limit", type=int)
            command.add_argument(
                "--kind", action="append",
                choices=[kind.value for kind in NodeKind],
            )

    claim = commands.add_parser("claim")
    claim.add_argument("run_id")
    claim.add_argument("node_id")
    claim.add_argument("--worker", required=True)
    claim.add_argument("--lease", type=int, default=3600)

    renew = commands.add_parser("renew")
    renew.add_argument("run_id")
    renew.add_argument("node_id")
    renew.add_argument("--token", required=True)
    renew.add_argument("--lease", type=int, default=3600)

    complete = commands.add_parser("complete")
    complete.add_argument("run_id")
    complete.add_argument("node_id")
    complete.add_argument("--token", required=True)
    output = complete.add_mutually_exclusive_group()
    output.add_argument("--result-json", type=Path)
    output.add_argument("--artifact", type=Path)

    fail = commands.add_parser("fail")
    fail.add_argument("run_id")
    fail.add_argument("node_id")
    fail.add_argument("--token", required=True)
    fail.add_argument("--error", required=True)
    fail.add_argument("--terminal", action="store_true")

    reset = commands.add_parser("reset")
    reset.add_argument("run_id")
    reset.add_argument("node_id")
    reset.add_argument("--cascade", action="store_true")

    set_job = commands.add_parser("set-ocr-job")
    set_job.add_argument("run_id")
    set_job.add_argument("ocr_job_id")

    write = commands.add_parser("write-artifact")
    write.add_argument("run_id")
    write.add_argument("relative_path", type=Path)
    write.add_argument("json_file", type=Path)

    add = commands.add_parser("add-nodes")
    add.add_argument("run_id")
    add.add_argument("json_file", type=Path)

    approve = commands.add_parser("approve")
    approve.add_argument("run_id")
    approve.add_argument("gate", choices=[gate.value for gate in ApprovalGate])
    approve.add_argument("artifact", type=Path)
    approve.add_argument("--sha", required=True)
    approve.add_argument("--approver", required=True)

    expand = commands.add_parser("expand", help="expand the exact approved structure plan")
    expand.add_argument("run_id")

    advance = commands.add_parser("advance-qa", help="add verifier or staging nodes")
    advance.add_argument("run_id")
    advance.add_argument("report", type=Path)

    verify = commands.add_parser("verify-stage", help="validate a staged manifest before Gate 2")
    verify.add_argument("run_id")
    verify.add_argument("manifest", type=Path)

    promote_command = commands.add_parser(
        "promote", help="promote, validate, and exact-path commit"
    )
    promote_command.add_argument("run_id")
    promote_command.add_argument("manifest", type=Path)
    promote_command.add_argument("--token", required=True)

    stage = commands.add_parser(
        "stage", help="manifest and complete an isolated staged source tree"
    )
    stage.add_argument("run_id")
    stage.add_argument("--token", required=True)
    stage.add_argument("--retained", required=True)
    stage.add_argument("--message", required=True)

    preflight = commands.add_parser(
        "preflight", help="execute the claimed deterministic preflight"
    )
    preflight.add_argument("run_id")
    preflight.add_argument("--token", required=True)

    ocr = commands.add_parser("ocr", help="reuse or run claimed local ensemble OCR")
    ocr.add_argument("run_id")
    ocr.add_argument("--token", required=True)

    qa = commands.add_parser("qa", help="run deterministic QA for a claimed round")
    qa.add_argument("run_id")
    qa.add_argument("--round", type=int, required=True)
    qa.add_argument("--token", required=True)

    recover = commands.add_parser(
        "recover-promotion", help="reconcile an interrupted promotion journal"
    )
    recover.add_argument("run_id")
    recover.add_argument("manifest", type=Path)

    prompt = commands.add_parser("prompt", help="emit a claimed leaf-agent packet")
    prompt.add_argument("run_id")
    prompt.add_argument("node_id")
    prompt.add_argument("--token", required=True)

    hash_command = commands.add_parser("hash")
    hash_command.add_argument("file", type=Path)


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _json_value(value.model_dump(mode="json"))
    if is_dataclass(value) and not isinstance(value, type):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    return value


def _print_json(value: Any) -> None:
    print(json.dumps(_json_value(value), ensure_ascii=False, indent=2))


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read JSON from {path}: {exc}") from exc


def run(args: argparse.Namespace) -> int:
    """Execute a parsed book command and return a process exit status."""
    workflow = BookWorkflow(args.repo_root, args.work_root, args.ocr_jobs_root)
    command = args.book_command
    try:
        if command == "init":
            result = workflow.create_run(
                args.pdf, args.author, run_id=args.run_id,
                ocr_job_id=args.ocr_job,
            )
        elif command == "list":
            result = workflow.list_runs()
        elif command == "status":
            result = workflow.status(args.run_id)
        elif command == "ready":
            kinds = {NodeKind(value) for value in args.kind} if args.kind else None
            result = workflow.ready_nodes(
                args.run_id, limit=args.limit, kinds=kinds,
            )
        elif command == "claim":
            result = workflow.claim_task(
                args.run_id, args.node_id, args.worker,
                lease_seconds=args.lease,
            )
        elif command == "renew":
            result = workflow.renew_claim(
                args.run_id, args.node_id, args.token,
                lease_seconds=args.lease,
            )
        elif command == "complete":
            result_data = (
                _read_json(args.result_json)
                if args.result_json is not None else None
            )
            if result_data is not None and not isinstance(result_data, dict):
                raise WorkflowError("task result JSON must be an object")
            result = workflow.complete_task(
                args.run_id, args.node_id, args.token,
                result=result_data, artifact_path=args.artifact,
            )
        elif command == "fail":
            result = workflow.fail_task(
                args.run_id, args.node_id, args.token, args.error,
                retryable=not args.terminal,
            )
        elif command == "reset":
            result = workflow.reset_task(
                args.run_id, args.node_id, cascade=args.cascade,
            )
        elif command == "resume":
            result = workflow.resume(args.run_id)
        elif command == "refresh-author":
            result = workflow.refresh_author(args.run_id)
        elif command == "set-ocr-job":
            result = workflow.set_ocr_job(args.run_id, args.ocr_job_id)
        elif command == "write-artifact":
            data = _read_json(args.json_file)
            if not isinstance(data, dict):
                raise WorkflowError("artifact JSON must be an object")
            path = workflow.write_artifact(
                args.run_id, args.relative_path, data,
            )
            result = {"path": str(path), "sha256": sha256_file(path)}
        elif command == "add-nodes":
            data = _read_json(args.json_file)
            if isinstance(data, dict) and "nodes" in data:
                data = data["nodes"]
            if not isinstance(data, list):
                raise WorkflowError("add-nodes JSON must be an array")
            result = workflow.add_nodes(
                args.run_id, [Node.model_validate(item) for item in data],
            )
        elif command == "approve":
            result = workflow.approve_artifact(
                args.run_id, ApprovalGate(args.gate), args.artifact,
                args.sha, args.approver,
            )
        elif command == "expand":
            from .book_graph import expand_approved_plan
            result = expand_approved_plan(workflow, args.run_id)
        elif command == "advance-qa":
            from .book_graph import advance_after_qa
            result = advance_after_qa(workflow, args.run_id, args.report)
        elif command == "verify-stage":
            from .book_promotion import verify_stage
            result = verify_stage(
                workflow, args.run_id, args.manifest, require_approval=False,
            )
        elif command == "promote":
            from .book_promotion_guard import promote
            result = promote(
                workflow, args.run_id, args.manifest, args.token,
            )
        elif command == "stage":
            from .book_stage import complete_stage
            result = complete_stage(
                workflow, args.run_id, args.token, args.retained, args.message,
            )
        elif command == "preflight":
            from .book_coordinator import complete_preflight
            result = complete_preflight(workflow, args.run_id, args.token)
        elif command == "ocr":
            from .book_coordinator import complete_ocr
            result = complete_ocr(workflow, args.run_id, args.token)
        elif command == "qa":
            from .book_qa import complete_qa
            result = complete_qa(
                workflow, args.run_id, args.round, args.token,
            )
        elif command == "recover-promotion":
            from .book_promotion_guard import recover_promotion
            result = recover_promotion(workflow, args.run_id, args.manifest)
        elif command == "prompt":
            from .book_packets import build_task_packet
            result = build_task_packet(
                workflow, args.run_id, args.node_id, args.token,
            )
        elif command == "hash":
            result = {
                "path": str(args.file.resolve()),
                "sha256": sha256_file(args.file),
            }
        elif command == "abort":
            result = workflow.abort(args.run_id)
        else:  # argparse prevents this branch
            raise WorkflowError(f"unknown book command: {command}")
    except (WorkflowError, ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    _print_json(result)
    return 0


__all__ = ["configure_parser", "run"]
