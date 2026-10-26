"""Canonical source evidence and reviewed policy decisions for render profiles."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .render_profile_model_base import RenderProfileAnchor, RenderProfileDesignIdentity, _StrictModel
from .render_profile_validation import _duplicates


class OfficialSourceEvidence(_StrictModel):
    """A profile conclusion grounded in text read from an exact official cell."""

    authority_kind: Literal["official_source"]
    source_sheet: str = Field(min_length=1)
    source_cell: str = Field(pattern=r"^[A-Z]+[1-9][0-9]*$")
    expected_normalized_statement: str = Field(min_length=1)
    justification: str = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_whitespace_only_review_text(self) -> OfficialSourceEvidence:
        if not self.expected_normalized_statement.strip() or not self.justification.strip():
            raise ValueError("official evidence and justification must contain non-whitespace text")
        return self


class ReviewedPolicyDecision(_StrictModel):
    """A reviewed policy decision that makes no claim about official source text."""

    authority_kind: Literal["reviewed_policy"]
    decision_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    #: The single anchor a SINGLETON decision governs, and omitted entirely on a
    #: width-17 membership decision, whose governed set is the rule's own
    #: ``anchors`` enumeration. Restating that enumeration here would duplicate
    #: the one authority the coverage gate already checks and could drift from
    #: it. Which shape is required is decided by the owning rule, both ways, so
    #: neither a singleton without its anchor nor a membership with a stray one
    #: can be authored.
    governed_anchor: RenderProfileAnchor | None = None
    decision_statement: str = Field(min_length=1)
    justification: str = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_whitespace_only_review_text(self) -> ReviewedPolicyDecision:
        if not self.decision_statement.strip() or not self.justification.strip():
            raise ValueError("reviewed policy and justification must contain non-whitespace text")
        return self


ReviewedEvidence = Annotated[
    OfficialSourceEvidence | ReviewedPolicyDecision,
    Field(discriminator="authority_kind"),
]


class SourceStatedCompositeEvidence(_StrictModel):
    """A reviewed composite whose complete wire grammar is stated at one PDF anchor."""

    authority_kind: Literal["official_parser_anchor"]
    governed_anchor: RenderProfileAnchor
    decision_statement: str = Field(min_length=1)
    justification: str = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_whitespace_only_review_text(self) -> SourceStatedCompositeEvidence:
        if not self.decision_statement.strip() or not self.justification.strip():
            raise ValueError("source-stated composite evidence must contain non-whitespace text")
        return self


class RenderProfileSourceEvidenceEntry(_StrictModel):
    """Actual normalized text read from one exact cell in the verified source."""

    sheet: str = Field(min_length=1)
    cell: str = Field(pattern=r"^[A-Z]+[1-9][0-9]*$")
    normalized_statement: str = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_whitespace_only_statement(self) -> RenderProfileSourceEvidenceEntry:
        if not self.normalized_statement.strip():
            raise ValueError("source evidence statement must contain non-whitespace text")
        return self


class RenderProfileSourceEvidence(_StrictModel):
    """Independent exact-cell evidence extracted from one verified official design."""

    design_identity: RenderProfileDesignIdentity
    entries: tuple[RenderProfileSourceEvidenceEntry, ...]

    @model_validator(mode="after")
    def _require_unique_locators(self) -> RenderProfileSourceEvidence:
        locators = tuple((entry.sheet, entry.cell) for entry in self.entries)
        duplicates = _duplicates(locators)
        if duplicates:
            raise ValueError(f"source evidence contains duplicate exact locators: {duplicates!r}")
        return self
