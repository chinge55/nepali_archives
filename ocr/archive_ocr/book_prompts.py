"""Versioned contracts for subscription-backed OCR sub-agents.

This module does not call a model.  It builds bounded prompts for the built-in
sub-agents of whichever agent CLI is driving the run, and validates the JSON
artifacts they leave in the filesystem-backed book run.  Keeping the contract
here — rather than in any one vendor's agent config — makes a paused run
resumable by a different tool, without an API key or a model API dependency.
"""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CONTRACT_VERSION = "book-agent/v1"


class AgentRole(str, Enum):
    structure = "structure"
    folio = "folio"
    dedupe = "dedupe"
    section_reconciler = "section_reconciler"
    footnote_sweep = "footnote_sweep"
    targeted_verifier = "targeted_verifier"


# Logical profile names, bound per tool (e.g. .codex/agents/ocr-*.toml or
# .claude/agents/ocr-*.md).  A tool with no profile system can ignore these and
# run the packet's prompt directly — build_prompt() output is self-contained.
AGENT_PROFILE_BY_ROLE: dict[AgentRole, str] = {
    AgentRole.structure: "ocr_structure",
    AgentRole.folio: "ocr_support",
    AgentRole.dedupe: "ocr_support",
    AgentRole.section_reconciler: "ocr_reconciler",
    AgentRole.footnote_sweep: "ocr_support",
    AgentRole.targeted_verifier: "ocr_verifier",
}


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskPage(ContractModel):
    page: int = Field(ge=1)
    image_path: str = Field(min_length=1)
    ocr_path: str | None = None


class AgentPromptRequest(ContractModel):
    task_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    role: AgentRole
    result_path: str
    pages: list[TaskPage] = Field(min_length=1)
    review_path: str | None = None
    catalogue_index_path: str | None = None
    task_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("result_path")
    @classmethod
    def result_must_be_isolated(cls, value: str) -> str:
        path = PurePosixPath(value)
        if ".." in path.parts or "archives" in path.parts or ".git" in path.parts:
            raise ValueError("result_path may not target protected project data")
        if path.is_absolute():
            if "tasks" not in path.parts or path.name != "result.json":
                raise ValueError("absolute result_path must be a task result file")
        elif path.parts[:2] != (".ocr-work", "book-runs"):
            raise ValueError("relative result_path must be inside .ocr-work/book-runs/")
        return value

    @model_validator(mode="after")
    def pages_are_unique(self) -> "AgentPromptRequest":
        numbers = [item.page for item in self.pages]
        if len(numbers) != len(set(numbers)):
            raise ValueError("pages may not contain duplicate PDF page numbers")
        return self


class Evidence(ContractModel):
    page: int = Field(ge=1)
    image_path: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class Uncertainty(ContractModel):
    page: int = Field(ge=1)
    category: Literal[
        "illegible",
        "cropped",
        "structure",
        "numbering",
        "footnote",
        "identity",
        "other",
    ]
    detail: str = Field(min_length=1)
    blocking: bool = True


class ResultBase(ContractModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    task_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    source_pages: list[int] = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)
    uncertainties: list[Uncertainty] = Field(default_factory=list)

    @field_validator("source_pages")
    @classmethod
    def source_pages_are_unique(cls, value: list[int]) -> list[int]:
        if any(page < 1 for page in value):
            raise ValueError("source_pages are one-based")
        if len(value) != len(set(value)):
            raise ValueError("source_pages may not contain duplicates")
        return value

    @model_validator(mode="after")
    def evidence_stays_on_assigned_pages(self) -> "ResultBase":
        assigned = set(self.source_pages)
        observed = {item.page for item in self.evidence}
        observed.update(item.page for item in self.uncertainties)
        if not observed.issubset(assigned):
            raise ValueError("evidence or uncertainty lies outside source_pages")
        return self


class PageClassification(ContractModel):
    page: int = Field(ge=1)
    kind: Literal[
        "cover",
        "title",
        "copyright",
        "author_front_matter",
        "editorial_front_matter",
        "contents",
        "literary_content",
        "blank",
        "advertisement",
        "back_matter",
        "unknown",
    ]
    action: Literal["include", "exclude", "inspect"]
    reason: str = Field(min_length=1)


class SectionBoundary(ContractModel):
    section_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    title_printed: str = Field(min_length=1)
    kind: Literal["poem", "canto", "chapter", "essay", "preface", "other"]
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)
    starts_new_work: bool
    include: bool = True
    exclusion_reason: str | None = None

    @model_validator(mode="after")
    def range_and_exclusion_are_consistent(self) -> "SectionBoundary":
        if self.end_page < self.start_page:
            raise ValueError("section end_page precedes start_page")
        if not self.include and not self.exclusion_reason:
            raise ValueError("excluded sections require exclusion_reason")
        return self


class StructureResult(ResultBase):
    role: Literal[AgentRole.structure] = AgentRole.structure
    pages: list[PageClassification] = Field(min_length=1)
    sections: list[SectionBoundary] = Field(default_factory=list)
    printed_to_pdf_offset_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def every_source_page_is_classified_once(self) -> "StructureResult":
        classified = [item.page for item in self.pages]
        if len(classified) != len(set(classified)):
            raise ValueError("a PDF page was classified more than once")
        if set(classified) != set(self.source_pages):
            raise ValueError("pages must classify every source_pages entry exactly once")
        return self


class FolioEntry(ContractModel):
    pdf_page: int = Field(ge=1)
    printed_label: str | None = None
    state: Literal["normal", "unnumbered", "missing_printed", "duplicate", "misordered", "unclear"]
    header_text: str | None = None
    footer_text: str | None = None


class FolioResult(ResultBase):
    role: Literal[AgentRole.folio] = AgentRole.folio
    folios: list[FolioEntry] = Field(min_length=1)
    anomalies: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def every_source_page_has_one_folio(self) -> "FolioResult":
        pages = [item.pdf_page for item in self.folios]
        if len(pages) != len(set(pages)) or set(pages) != set(self.source_pages):
            raise ValueError("folios must cover every source page exactly once")
        return self


class CatalogueMatch(ContractModel):
    candidate_path: str = Field(min_length=1)
    confidence: Literal["exact", "probable", "possible"]
    matching_evidence: list[str] = Field(min_length=1)


class WorkDedupeDecision(ContractModel):
    proposed_section_id: str = Field(min_length=1)
    action: Literal["new", "skip_exact", "enrich_metadata", "human_review"]
    matches: list[CatalogueMatch] = Field(default_factory=list)
    reason: str = Field(min_length=1)


class DedupeResult(ResultBase):
    role: Literal[AgentRole.dedupe] = AgentRole.dedupe
    decisions: list[WorkDedupeDecision] = Field(min_length=1)


class NumberingRecord(ContractModel):
    printed: str = Field(min_length=1)
    page: int = Field(ge=1)
    status: Literal["present", "genuine_gap_before", "unclear"]


class FootnoteRecord(ContractModel):
    marker: str = Field(min_length=1)
    text: str = Field(min_length=1)
    page: int = Field(ge=1)
    continues_on_page: int | None = Field(default=None, ge=1)


class SectionResult(ResultBase):
    role: Literal[AgentRole.section_reconciler] = AgentRole.section_reconciler
    section_id: str = Field(min_length=1)
    title_printed: str = Field(min_length=1)
    text: str = Field(min_length=1)
    numbering_mode: Literal["none", "printed", "mixed", "unclear"]
    numbering: list[NumberingRecord] = Field(default_factory=list)
    footnotes: list[FootnoteRecord] = Field(default_factory=list)
    resolved_disagreement_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def records_stay_on_assigned_pages(self) -> "SectionResult":
        assigned = set(self.source_pages)
        pages = {item.page for item in self.numbering}
        pages.update(item.page for item in self.footnotes)
        pages.update(
            item.continues_on_page for item in self.footnotes
            if item.continues_on_page is not None
        )
        if not pages.issubset(assigned):
            raise ValueError("section records lie outside source_pages")
        return self


class PageFootnotes(ContractModel):
    page: int = Field(ge=1)
    findings: list[FootnoteRecord] = Field(default_factory=list)
    continuation_or_marginalia: str | None = None


class FootnoteSweepResult(ResultBase):
    role: Literal[AgentRole.footnote_sweep] = AgentRole.footnote_sweep
    pages: list[PageFootnotes] = Field(min_length=1)

    @model_validator(mode="after")
    def every_source_page_is_swept_once(self) -> "FootnoteSweepResult":
        swept = [item.page for item in self.pages]
        if len(swept) != len(set(swept)):
            raise ValueError("a PDF page was swept more than once")
        if set(swept) != set(self.source_pages):
            raise ValueError("pages must cover every source_pages entry exactly once")
        return self


class VerifiedIssue(ContractModel):
    issue_id: str = Field(min_length=1)
    verdict: Literal["source_correct", "repaired", "blocked"]
    explanation: str = Field(min_length=1)
    replacement_text: str | None = None
    page: int = Field(ge=1)

    @model_validator(mode="after")
    def repair_has_replacement(self) -> "VerifiedIssue":
        if self.verdict == "repaired" and not self.replacement_text:
            raise ValueError("repaired issues require replacement_text")
        if self.verdict != "repaired" and self.replacement_text is not None:
            raise ValueError("replacement_text is only valid for repaired issues")
        return self


class VerifierResult(ResultBase):
    role: Literal[AgentRole.targeted_verifier] = AgentRole.targeted_verifier
    issues: list[VerifiedIssue] = Field(min_length=1)

    @model_validator(mode="after")
    def issues_stay_on_assigned_pages(self) -> "VerifierResult":
        if not {item.page for item in self.issues}.issubset(set(self.source_pages)):
            raise ValueError("verified issue lies outside source_pages")
        return self


ResultModel = (
    StructureResult
    | FolioResult
    | DedupeResult
    | SectionResult
    | FootnoteSweepResult
    | VerifierResult
)

RESULT_MODELS: dict[AgentRole, type[ResultBase]] = {
    AgentRole.structure: StructureResult,
    AgentRole.folio: FolioResult,
    AgentRole.dedupe: DedupeResult,
    AgentRole.section_reconciler: SectionResult,
    AgentRole.footnote_sweep: FootnoteSweepResult,
    AgentRole.targeted_verifier: VerifierResult,
}


_ROLE_GUIDANCE: dict[AgentRole, str] = {
    AgentRole.structure: """
Classify every assigned PDF page exactly once. Identify author-written front
matter separately from later editorial material: keep the author's own
prefaces/notes, but exclude other people's modern prefaces, forewords, and
introductions. Find complete semantic sections (one poem, canto, chapter, or
essay), title them exactly as printed, and mark work boundaries. Do not
transcribe body text or guess unclear boundaries.
""",
    AgentRole.folio: """
Audit physical PDF order against visible printed folios, headers, and footers.
Record labels exactly as printed, including their numeral script. Detect
missing, duplicated, or misordered leaves. A printed numbering gap is evidence
to report, never permission to invent a missing number or page.
""",
    AgentRole.dedupe: """
Search the supplied catalogue/index read-only. Compare title, author, opening
and closing lines, and collection context. Recommend only new, skip_exact,
enrich_metadata, or human_review. Never recommend overwriting canonical text;
an uncertain identity must be human_review.
""",
    AgentRole.section_reconciler: """
Reconcile the complete assigned semantic section, including text that crosses
page boundaries. Use OCR only as a hint and inspect every page image. Preserve
spelling, punctuation, wording, headings, blank-line structure, and printed
numeral script. Put stanza/sloka numbers on their own lines only when printed;
do not repair genuine printed lacunae or hallucinate numbers. Remove repeating
page furniture, not literary text. Preserve footnote markers and bodies and
resolve every supplied ensemble disagreement or report it as uncertainty.
""",
    AgentRole.footnote_sweep: """
Inspect every assigned page bottom, margin, column boundary, and continuation.
Record each marker and body exactly as printed, including continuations. Empty
findings are valid but each page must still have a page result. Do not infer a
footnote from OCR alone.
""",
    AgentRole.targeted_verifier: """
Inspect only the supplied QA issue IDs against the named page images. Confirm
the source, provide the smallest faithful replacement when repair is needed,
or block when illegible. Printed numbering gaps are not errors. Do not polish
nearby text or make unrequested edits.
""",
}


_COMMON_RULES = """
CARDINAL RULE — PRESERVE, DO NOT REWRITE:
The page images are the sole source of truth. OCR, catalogue data, and prior
agent output are hints. Never modernize spelling, punctuation, wording, or
numbering, and never silently complete damaged or absent print.

Work only on the assigned pages and task. Read canonical archive files only
when this role calls for comparison. Never edit archives/, metadata.json,
text.txt, source PDFs, Git state, or any other canonical/project file. Write
exactly one JSON result to the assigned isolated result path. While executing
this task you must not call any model API, use an API key, install
dependencies, access the network, or spawn another agent. Record uncertainty
instead of guessing.
"""


def build_prompt(request: AgentPromptRequest) -> str:
    """Return a self-contained, versioned prompt for one built-in sub-agent."""
    model = RESULT_MODELS[request.role]
    pages = [page.model_dump(mode="json") for page in request.pages]
    inputs = {
        "pages": pages,
        "review_path": request.review_path,
        "catalogue_index_path": request.catalogue_index_path,
        "task_payload": request.task_payload,
    }
    schema = model.model_json_schema()
    return (
        f"You are the {request.role.value} worker for Nepali Archives.\n"
        f"Contract: {CONTRACT_VERSION}\n"
        f"Task ID: {request.task_id}\n"
        f"Result path: {request.result_path}\n"
        f"{_COMMON_RULES}\n"
        f"ROLE-SPECIFIC DUTY:\n{_ROLE_GUIDANCE[request.role].strip()}\n\n"
        "INPUTS (repository paths; PDF pages are one-based):\n"
        f"{json.dumps(inputs, ensure_ascii=False, indent=2)}\n\n"
        "REQUIRED RESULT JSON SCHEMA:\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "Write valid UTF-8 JSON (not Markdown) to the exact result path. Set "
        f"contract_version={CONTRACT_VERSION!r}, task_id={request.task_id!r}, "
        f"role={request.role.value!r}, and source_pages to exactly the pages "
        "you inspected. After writing it, return only a concise completion "
        "summary naming the result path and any blocking uncertainty."
    )


def build_role_prompt(role: AgentRole | str, **kwargs: Any) -> str:
    """Convenience builder used by graph coordinators."""
    request = AgentPromptRequest(role=AgentRole(role), **kwargs)
    return build_prompt(request)


def validate_result(role: AgentRole | str, payload: dict[str, Any]) -> ResultModel:
    """Validate a decoded result and return its role-specific typed model."""
    selected = AgentRole(role)
    return RESULT_MODELS[selected].model_validate(payload)  # type: ignore[return-value]


def validate_result_json(role: AgentRole | str, raw: str | bytes) -> ResultModel:
    """Validate a serialized result without accepting Markdown wrappers."""
    selected = AgentRole(role)
    return RESULT_MODELS[selected].model_validate_json(raw)  # type: ignore[return-value]


def load_result(role: AgentRole | str, path: str | Path) -> ResultModel:
    """Read and validate an agent result artifact."""
    return validate_result_json(role, Path(path).read_bytes())
