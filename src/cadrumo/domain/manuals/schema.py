"""Strict pydantic v2 records for the *Manual práctico* corpus.

The corpus consists of three primary records:

* :class:`Manual`: The root volume (id, year, part).
* :class:`Chapter`: Metadata and ordered section references.
* :class:`Section`: Prose paragraphs and extracted :class:`Rule` objects.

Every record is strict, frozen, and prohibits unknown keys. Spanish is
the authoritative language for the corpus text (prose, titles, summaries);
the internationalization engine is used for the application's user
interface and error messages.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ...core import Hex64Str
from ...core.casilla_id import CasillaId
from ...core.time import UtcInstant
from ..calculations.registry.ids import ModeloId
from ._ids import ManualId, ManualPart
from .errors import ManualValidationError

_StableId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    ),
]
"""Kebab-case identifier used for chapters, sections, and rules."""

_Reviewer = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
"""Reviewer handle or ID (e.g. 'operator')."""

_LegalActRef = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=256,
        pattern=r"^[A-Z0-9-][^|]*\|[^|]+$",
    ),
]
"""External legal act reference string (ActId|Ref)."""

# RuleKind catalogue: captures the primary categories of help text found
# in the manuals.
RuleKind = Literal[
    "computation",
    "applicability",
    "valuation",
    "deductibility",
    "formal_obligation",
    "procedural",
    "other",
]

# Review year bounds: AEAT publishes a new manual every year; guard against
# absurd values while staying lenient for historical backfills.
_YearField = Annotated[int, Field(ge=2000, le=2100)]


def _require_spanish(text: str, field_name: str) -> None:
    """Assert a string carries non-empty authoritative Spanish text."""
    if not text or not text.strip():
        raise ManualValidationError(f"{field_name}: missing authoritative Spanish text")


class _ManualStrictFrozen(BaseModel):
    """Shared config: strict validation, immutable instances, no extras.

    Deliberately NOT the canonical :data:`~cadrumo.core.STRICT_FROZEN_CONFIG`. This
    base adds an explicit ``str_strip_whitespace=False`` to guarantee that
    authoritative Spanish manual text (rule bodies, paragraphs, section titles)
    is preserved byte-for-byte, including leading and trailing whitespace that
    can be legally significant in the source corpus. ``str_strip_whitespace``
    defaults to ``False`` today, so the explicit declaration is behaviour-identical
    to the canonical config now, but it pins the intent so a future change to the
    canonical config (were it ever to enable stripping) cannot silently mutate
    verbatim legal text. It is therefore kept as a divergent, non-substitutable
    base rather than consuming the shared constant.
    """

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        str_strip_whitespace=False,
    )


class ManualCasillaReference(_ManualStrictFrozen):
    """Structured manual cross-reference to a canonical registry casilla."""

    modelo_id: ModeloId = Field(description="Registry modelo id that owns the casilla.")
    casilla_id: CasillaId = Field(description="Canonical registry casilla.id value.")


class SectionRef(_ManualStrictFrozen):
    """Link to a Section from a Chapter."""

    section_id: _StableId
    relative_path: str = Field(min_length=1)


class LLMProvenance(_ManualStrictFrozen):
    """Metadata about the LLM extraction of a rule draft.

    Attributes:
        provider: Provider key, e.g. ``'anthropic'``.
        model: Concrete model name used for the draft.
        prompt_id: Named prompt from the prompt registry.
        cache_hit: Whether the draft was served from the LLM cache.
        extracted_at: UTC timestamp the draft was produced.
    """

    provider: str = Field(min_length=1, max_length=64, description="Provider key, e.g. 'anthropic'.")
    model: str = Field(min_length=1, max_length=128, description="Concrete model name used for the draft.")
    prompt_id: str = Field(min_length=1, max_length=128, description="Named prompt from the prompt registry.")
    cache_hit: bool = Field(description="Whether the draft was served from the LLM cache.")
    extracted_at: UtcInstant = Field(description="UTC timestamp the draft was produced.")


class SectionSource(_ManualStrictFrozen):
    """Provenance pointer for a ``Section`` back to the source handbook."""

    manual_url: AnyHttpUrl = Field(description="Canonical AEAT URL the section was extracted from.")
    page: int = Field(ge=1, description="1-indexed page number in the PDF.")


class RuleSource(_ManualStrictFrozen):
    """Provenance pointer for a ``Rule`` back to the source handbook."""

    manual_url: AnyHttpUrl = Field(description="Canonical AEAT URL the rule was extracted from.")
    page: int = Field(ge=1, description="1-indexed page number in the PDF.")
    paragraph: int | None = Field(default=None, ge=1, description="Optional paragraph index within the page.")


class Paragraph(_ManualStrictFrozen):
    """A single source paragraph within a section."""

    paragraph_id: _StableId = Field(description="Stable identifier, unique within its section.")
    text: str = Field(min_length=1, description="Source prose (authoritative Spanish).")
    page: int = Field(ge=1, description="1-indexed page number in the PDF.")

    @model_validator(mode="after")
    def _check_authoritative_text(self) -> Paragraph:
        _require_spanish(self.text, "Paragraph.text")
        return self


class Rule(_ManualStrictFrozen):
    """A single extracted rule from the *Manual práctico*.

    Every persisted rule carries reviewer metadata populated by a real
    human; the verify CLI rejects rules missing those fields when
    ``CADRUMO_MANUALS_REVIEW_REQUIRED`` is true.

    Attributes:
        rule_id: Stable kebab-case identifier produced by
            :func:`~cadrumo.domain.manuals.generate_rule_id`.
        manual_id: Owning handbook identifier.
        year: Tax year the rule applies to.
        part: Volume split within the year.
        chapter_id: Stable identifier of the owning chapter.
        section_id: Stable identifier of the owning section.
        kind: Closed-catalogue rule category.
        statement: Authoritative Spanish rule statement.
        applies_when: Optional natural-language predicate describing
            the rule's applicability (Spanish).
        references_casillas: Cross-references to canonical registry casilla ids.
        references_sections: Cross-references to sibling sections by
            stable id.
        references_legal_acts: Cross-references to external legal acts
            (BOE orders, laws).
        source: Provenance pointer back to the source PDF.
        extracted_by: LLM provenance for the draft extraction.
        definition_reviewed_by: Reviewer handle who signed off on the
            curated definition.
        definition_reviewed_at: Date of the reviewer sign-off.
    """

    rule_id: _StableId
    manual_id: ManualId
    year: _YearField
    part: ManualPart
    chapter_id: _StableId
    section_id: _StableId
    kind: RuleKind
    statement: str = Field(description="Authoritative Spanish rule statement.")
    applies_when: str | None = Field(
        default=None,
        description="Optional natural-language predicate describing the rule's applicability (Spanish).",
    )
    references_casillas: tuple[ManualCasillaReference, ...] = Field(
        default_factory=tuple,
        description="Cross-references to canonical registry casilla ids scoped by modelo_id.",
    )
    references_sections: tuple[_StableId, ...] = Field(
        default_factory=tuple,
        description="Cross-references to sibling sections by stable id.",
    )
    references_legal_acts: tuple[_LegalActRef, ...] = Field(
        default_factory=tuple,
        description="Cross-references to external legal acts (BOE orders, laws).",
    )
    source: RuleSource
    extracted_by: LLMProvenance
    definition_reviewed_by: _Reviewer
    definition_reviewed_at: date

    @model_validator(mode="after")
    def _check_authoritative_statement(self) -> Rule:
        _require_spanish(self.statement, "Rule.statement")
        if self.applies_when is not None:
            _require_spanish(self.applies_when, "Rule.applies_when")
        return self


class Section(_ManualStrictFrozen):
    """A structured section of a handbook chapter."""

    section_id: _StableId
    chapter_id: _StableId
    title: str
    summary: str
    prose: tuple[Paragraph, ...] = Field(default_factory=tuple)
    rules: tuple[Rule, ...] = Field(default_factory=tuple)
    references_sections: tuple[_StableId, ...] = Field(default_factory=tuple)
    references_legal_acts: tuple[_LegalActRef, ...] = Field(default_factory=tuple)
    source: SectionSource
    definition_reviewed_by: _Reviewer
    definition_reviewed_at: date

    @model_validator(mode="after")
    def _check_authoritative_content(self) -> Section:
        _require_spanish(self.title, "Section.title")
        _require_spanish(self.summary, "Section.summary")
        return self


class Chapter(_ManualStrictFrozen):
    """A handbook chapter: metadata plus ordered section references."""

    chapter_id: _StableId
    title: str
    summary: str
    sections: tuple[SectionRef, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _check_authoritative_content(self) -> Chapter:
        _require_spanish(self.title, "Chapter.title")
        _require_spanish(self.summary, "Chapter.summary")
        return self


class Manual(_ManualStrictFrozen):
    """Root record for a single ``(manual_id, year, part)`` volume."""

    manual_id: ManualId
    year: _YearField
    part: ManualPart
    title: str
    summary: str
    source_pdf_url: AnyHttpUrl
    source_html_url: AnyHttpUrl | None = None
    fetched_at: UtcInstant
    definition_reviewed_by: _Reviewer
    definition_reviewed_at: date
    chapters: tuple[Chapter, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _check_authoritative_content(self) -> Manual:
        _require_spanish(self.title, "Manual.title")
        _require_spanish(self.summary, "Manual.summary")
        return self


class ManualCatalogue(_ManualStrictFrozen):
    """Aggregate view of all chapters and sections in a manual."""

    manuals: tuple[Manual, ...] = Field(default_factory=tuple)

    def __len__(self) -> int:
        """How many manuals the aggregate holds."""
        return len(self.manuals)


class FetchedManualPart(_ManualStrictFrozen):
    """Result of a successful manual fetch and validation."""

    manual_id: ManualId
    year: int
    part: ManualPart
    source_pdf_url: AnyHttpUrl
    relative_pdf_path: str
    sha256: Hex64Str
    content_length: int
    fetched_at: UtcInstant
    synthetic: bool = False


__all__ = [
    "Chapter",
    "FetchedManualPart",
    "LLMProvenance",
    "Manual",
    "ManualCatalogue",
    "Paragraph",
    "Rule",
    "Section",
    "SectionRef",
]
