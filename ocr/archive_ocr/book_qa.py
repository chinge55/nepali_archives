"""Deterministic QA checks for reconciled semantic sections."""
from __future__ import annotations

import re
from pathlib import Path

from .book_graph import QAIssue, QAReport
from .book_prompts import (
    FootnoteSweepResult,
    SectionResult,
    VerifierResult,
)
from .book_workflow import BookWorkflow, InvalidTransition, NodeStatus


_MIXED_NUMERAL = re.compile(r"(?=.*[0-9])(?=.*[०-९])[0-9०-९]+")
_PAGE_FURNITURE = re.compile(r"(?m)^\s*(?:[०-९0-9]{1,4}\s*[:।-]\s*.+|[०-९0-9]{1,4})\s*$")


def _artifact(workflow: BookWorkflow, run_id: str, node_id: str) -> Path:
    node = workflow.load_run(run_id).nodes[node_id]
    if node.status != NodeStatus.completed or not node.artifact_path:
        raise InvalidTransition(f"{node_id} is not completed with an artifact")
    path = workflow.run_dir(run_id) / node.artifact_path
    if not path.is_file():
        raise InvalidTransition(f"{node_id} artifact is missing")
    return path


def build_qa_report(
    workflow: BookWorkflow,
    run_id: str,
    round_number: int,
) -> QAReport:
    """Inspect typed worker outputs and return a reproducible risk report."""
    run = workflow.load_run(run_id)
    qa_id = f"qa_{round_number}"
    if qa_id not in run.nodes:
        raise InvalidTransition(f"unknown QA round: {round_number}")
    issues: list[QAIssue] = []

    if round_number == 0:
        reconcile_nodes = [
            node for node in run.nodes.values()
            if node.id.startswith("reconcile_")
        ]
        if not reconcile_nodes:
            raise InvalidTransition("no reconciled sections exist")
        for node in reconcile_nodes:
            section = SectionResult.model_validate_json(
                _artifact(workflow, run_id, node.id).read_bytes()
            )
            footnote_id = f"footnotes_{section.section_id}"
            sweep = FootnoteSweepResult.model_validate_json(
                _artifact(workflow, run_id, footnote_id).read_bytes()
            )
            pages = section.source_pages
            for uncertainty in section.uncertainties:
                if uncertainty.blocking:
                    issues.append(
                        QAIssue(
                            id=f"uncertain_{section.section_id}_{uncertainty.page}",
                            category=(
                                uncertainty.category
                                if uncertainty.category in {
                                    "numbering", "footnote", "structure", "illegible"
                                }
                                else "other"
                            ),
                            severity="blocking",
                            pages=[uncertainty.page],
                            detail=uncertainty.detail,
                        )
                    )
            if len(section.text.strip()) < max(12, len(pages) * 8):
                issues.append(
                    QAIssue(
                        id=f"text_loss_{section.section_id}",
                        category="other",
                        severity="high",
                        pages=pages,
                        detail="Reconciled text is suspiciously short for its page range.",
                    )
                )
            malformed = [
                record for record in section.numbering
                if _MIXED_NUMERAL.search(record.printed) or record.printed == "रर"
            ]
            if malformed:
                issues.append(
                    QAIssue(
                        id=f"numbering_{section.section_id}",
                        category="numbering",
                        severity="high",
                        pages=sorted({record.page for record in malformed}),
                        detail="Malformed OCR-like printed numeral requires image verification.",
                    )
                )
            if section.numbering_mode == "none" and section.numbering:
                issues.append(
                    QAIssue(
                        id=f"invented_numbers_{section.section_id}",
                        category="numbering",
                        severity="blocking",
                        pages=sorted({record.page for record in section.numbering}),
                        detail="Unnumbered section contains numbering records.",
                    )
                )
            if _PAGE_FURNITURE.search(section.text):
                issues.append(
                    QAIssue(
                        id=f"furniture_{section.section_id}",
                        category="other",
                        severity="medium",
                        pages=pages,
                        detail="Text contains standalone page-number/footer-like lines.",
                    )
                )
            reconciled_notes = {
                (note.page, note.marker, note.text.strip())
                for note in section.footnotes
            }
            swept_notes = {
                (note.page, note.marker, note.text.strip())
                for page in sweep.pages for note in page.findings
            }
            if reconciled_notes != swept_notes:
                issues.append(
                    QAIssue(
                        id=f"footnotes_{section.section_id}",
                        category="footnote",
                        severity="high",
                        pages=sorted(
                            {item[0] for item in reconciled_notes ^ swept_notes}
                        ),
                        detail="Reconciler and independent footnote sweep disagree.",
                    )
                )
    else:
        verifier = VerifierResult.model_validate_json(
            _artifact(workflow, run_id, f"verify_{round_number}").read_bytes()
        )
        for item in verifier.issues:
            if item.verdict == "blocked":
                issues.append(
                    QAIssue(
                        id=f"blocked_{item.issue_id}",
                        category="illegible",
                        severity="blocking",
                        pages=[item.page],
                        detail=item.explanation,
                    )
                )

    high_risk = any(
        issue.severity in {"high", "blocking"} for issue in issues
    )
    return QAReport(
        run_id=run_id,
        round=round_number,
        issues=issues,
        deterministic_checks_passed=not high_risk,
        ready_to_stage=not high_risk,
    )


def complete_qa(
    workflow: BookWorkflow,
    run_id: str,
    round_number: int,
    claim_token: str,
) -> QAReport:
    report = build_qa_report(workflow, run_id, round_number)
    path = workflow.write_artifact(
        run_id,
        f"artifacts/qa-{round_number}-report.json",
        report,
    )
    workflow.complete_task(
        run_id,
        f"qa_{round_number}",
        claim_token,
        artifact_path=path,
    )
    return report


__all__ = ["build_qa_report", "complete_qa"]
