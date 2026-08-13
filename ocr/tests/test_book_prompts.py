#!/usr/bin/env python3
"""Plain-assert regression spec for bounded agent contracts."""
import sys
from contextlib import contextmanager
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from archive_ocr.book_prompts import (
    AgentPromptRequest,
    AgentRole,
    FolioResult,
    StructureResult,
    VerifierResult,
    build_prompt,
    validate_result,
)


@contextmanager
def expect(exception):
    try:
        yield
    except exception:
        return
    raise AssertionError(f"expected {exception.__name__}")


def request(role: AgentRole = AgentRole.folio) -> AgentPromptRequest:
    return AgentPromptRequest(
        task_id="task-1",
        role=role,
        result_path=".ocr-work/book-runs/run-1/tasks/task-1/result.json",
        pages=[{"page": 1, "image_path": "jobs/ocr-1/pages/pg-001.png"}],
    )


def base(role: str) -> dict:
    return {
        "contract_version": "book-agent/v1",
        "task_id": "task-1",
        "role": role,
        "source_pages": [1],
        "evidence": [],
        "uncertainties": [],
    }


def test_prompt_names_image_truth_output_and_no_api_boundary():
    prompt = build_prompt(request(AgentRole.section_reconciler))
    assert "page images are the sole source of truth" in prompt
    assert "Never modernize" in prompt
    assert "Never edit archives/" in prompt
    assert "API key" in prompt
    assert ".ocr-work/book-runs/run-1/tasks/task-1/result.json" in prompt


def test_result_path_must_be_isolated(path):
    with expect(ValidationError):
        AgentPromptRequest(
            task_id="task-1",
            role="folio",
            result_path=path,
            pages=[{"page": 1, "image_path": "pg-001.png"}],
        )


def test_structure_must_classify_all_pages_once():
    payload = base("structure")
    payload.update(
        {
            "source_pages": [1, 2],
            "pages": [{"page": 1, "kind": "title", "action": "include", "reason": "title"}],
            "sections": [],
            "printed_to_pdf_offset_notes": [],
        }
    )
    with expect(ValidationError):
        StructureResult.model_validate(payload)


def test_role_specific_validation_rejects_wrong_role():
    payload = base("folio")
    payload.update(
        {
            "folios": [
                {
                    "pdf_page": 1,
                    "printed_label": None,
                    "state": "unnumbered",
                    "header_text": None,
                    "footer_text": None,
                }
            ],
            "anomalies": [],
        }
    )
    assert isinstance(validate_result("folio", payload), FolioResult)
    with expect(ValidationError):
        validate_result("structure", payload)


def test_repaired_verifier_issue_requires_replacement_text():
    payload = base("targeted_verifier")
    payload["issues"] = [
        {
            "issue_id": "number-1",
            "verdict": "repaired",
            "explanation": "Image clearly prints १२.",
            "page": 1,
        }
    ]
    with expect(ValidationError):
        VerifierResult.model_validate(payload)


if __name__ == "__main__":
    test_prompt_names_image_truth_output_and_no_api_boundary()
    for unsafe_path in (
        "/tmp/result.json",
        "../result.json",
        "archives/authors/author/work/text.txt",
        ".ocr-work/other/result.json",
    ):
        test_result_path_must_be_isolated(unsafe_path)
    test_structure_must_classify_all_pages_once()
    test_role_specific_validation_rejects_wrong_role()
    test_repaired_verifier_issue_requires_replacement_text()
    print("OK: book_prompts.py contract spec passes")
