"""Strict pydantic v2 schema for the AEAT *Manual práctico* corpus.

Every boundary-crossing record the :mod:`aeat.domain.manuals`
subpackage reads from disk, writes to disk, or exposes over its
public API is defined here. The schema is frozen and strict wherever
the loader idiom permits it, per the project-wide pydantic v2
mandate.

Closed catalogues are :class:`enum.StrEnum`. Multilingual fields use
:class:`aeat.core.i18n.str`. Modelo field cross-references
are stored as validated strings (``MODELO_130:01`` shape) so the
manuals corpus stays loadable even when a citation references a
field that has not yet been promoted into a validated registry
snapshot.

Spanish is the authoritative language for AEAT-domain terminology.
Spanish-authoritative translatable fields on persisted records are
validated at load time to guarantee the ``es`` key is present;
missing ``en`` and ``hu`` translations are surfaced as warnings by
the verification pipeline, not hard errors.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ..modelos import ModeloCode

# Modelo field cross-reference syntax used inside extracted rules.
# The MODELO_NNN prefix is anchored to the closed `aeat.domain.modelos.ModeloCode`
# enum (each member's value is the three-character AEAT code string), so a
# new modelo cannot be cited from the manuals corpus without first being
# registered in `aeat.domain.modelos`. The optional field suffix is a
# validated string only - the field itself need not exist in a registry
# snapshot at manual-corpus load time.
_MODELO_CODE_ALTERNATION = "|".join(member.value for member in ModeloCode)
_MODELO_CASILLA_PATTERN = rf"^MODELO_(?:{_MODELO_CODE_ALTERNATION})(?::[0-9A-Z_]+)?$"


class ManualId(StrEnum):
    """Identifier for a *Manual práctico* volume.

    The enum is intentionally small (only the handbooks relevant to an
    autónomo) and extensible by follow-on work.

    Attributes:
        RENTA: *Manual práctico de Renta* (IRPF).
        IVA: *Manual práctico de IVA*.
    """

    RENTA = "renta"
    IVA = "iva"


class ManualPart(StrEnum):
    """Volume split for a handbook within a single tax year.

    Attributes:
        SINGLE: One-volume handbook (covers IVA).
        PARTE_1: Main volume of the Renta handbook (2024 onward).
        PARTE_2_DEDUCCIONES_AUTONOMICAS: Companion volume of the Renta
            handbook covering autonomous-community deductions.
    """

    SINGLE = "single"
    PARTE_1 = "parte1"
    PARTE_2_DEDUCCIONES_AUTONOMICAS = "parte2-deducciones-autonomicas"


class RuleKind(StrEnum):
    """Closed catalogue of rule categories extracted from the handbook.

    Attributes:
        OBLIGATION: A statutory or regulatory obligation.
        COMPUTATION: A computation step (formula or aggregation).
        EXEMPTION: An exemption from an otherwise-applicable rule.
        DEDUCTION: A deduction from the tax base or quota.
        DEADLINE: A submission or payment deadline.
        DEFINITION: A definitional clarification of terminology.
        EXAMPLE: A worked example drawn from the handbook.
    """

    OBLIGATION = "obligation"
    COMPUTATION = "computation"
    EXEMPTION = "exemption"
    DEDUCTION = "deduction"
    DEADLINE = "deadline"
    DEFINITION = "definition"
    EXAMPLE = "example"


# Stable ID shape: lowercase kebab-case slug, no whitespace, no slashes.
_StableId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9-]*$"),
]

# Reviewer tag: any non-empty trimmed string (e.g. GitHub handle, email, or name).
_Reviewer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]

# Modelo field cross-reference, e.g. ``MODELO_130:01``. Validated as a
# constrained string so manuals can cite fields that may not yet exist in a
# registry snapshot at manual-corpus load time.
_CasillaRef = Annotated[str, StringConstraints(strip_whitespace=True, pattern=_MODELO_CASILLA_PATTERN)]

# Legal-act reference: free-form but trimmed + non-empty, e.g. "Ley 35/2006, art. 32".
_LegalActRef = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]

# Review year bounds: AEAT publishes a new manual every year; guard against
# absurd values while staying lenient for historical backfills.
_YearField = Annotated[int, Field(ge=2000, le=2100)]


def _require_spanish(translatable: str, field_name: str) -> None:
    """Assert a :class:`~aeat.core.i18n.str` carries the authoritative ``es`` key."""
    if not translatable:
        raise ValueError(f"{field_name}: missing authoritative Spanish ('es') translation")


class _ManualStrictFrozen(BaseModel):
    """Shared config: strict validation, immutable instances, no extras."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        str_strip_whitespace=False,
    )


class _StrictLoose(BaseModel):
    """Strict validation but mutable; used for aggregate catalogues."""

    model_config = ConfigDict(
        strict=True,
        frozen=False,
        extra="forbid",
    )


class LLMProvenance(_ManualStrictFrozen):
    """Record of which LLM call produced a draft extraction.

    Attached to every LLM-drafted :class:`Rule` so reviewers can trace
    the origin and so follow-on work can invalidate drafts keyed on a
    deprecated prompt template.

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
    extracted_at: datetime = Field(description="UTC timestamp the draft was produced.")


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
    """A single Spanish source paragraph within a section."""

    paragraph_id: _StableId = Field(description="Stable identifier, unique within its section.")
    text: str = Field(min_length=1, description="Spanish source prose (authoritative).")
    page: int = Field(ge=1, description="1-indexed page number in the PDF.")


class Rule(_ManualStrictFrozen):
    """A single extracted rule from the *Manual práctico*.

    Every persisted rule carries reviewer metadata populated by a real
    human; the verify CLI rejects rules missing those fields when
    ``AEAT_MANUALS_REVIEW_REQUIRED`` is true.

    Attributes:
        rule_id: Stable kebab-case identifier produced by
            :func:`~aeat.domain.manuals.generate_rule_id`.
        manual_id: Owning handbook identifier.
        year: Tax year the rule applies to.
        part: Volume split within the year.
        chapter_id: Stable identifier of the owning chapter.
        section_id: Stable identifier of the owning section.
        kind: Closed-catalogue rule category.
        statement: Rule statement in all supplied languages.
        applies_when: Optional natural-language predicate describing
            the rule's applicability.
        references_casillas: Cross-references to modelo fields.
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
    statement: str = Field(description="Rule statement in all supplied languages.")
    applies_when: str | None = Field(
        default=None,
        description="Optional natural-language predicate describing the rule's applicability.",
    )
    references_casillas: tuple[_CasillaRef, ...] = Field(
        default_factory=tuple,
        description="Cross-references to modelo fields (e.g. 'MODELO_130:01').",
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
    def _check_spanish_statement(self) -> Rule:
        _require_spanish(self.statement, "Rule.statement")
        return self


class SectionRef(_ManualStrictFrozen):
    """Compact pointer from a ``Chapter`` to a ``Section`` on disk.

    Keeping the chapter tree small and file-based keeps the
    ``chapters.json`` document readable and diff-friendly even for a
    handbook with hundreds of sections.
    """

    section_id: _StableId
    relative_path: str = Field(
        min_length=1,
        description=(
            "POSIX-style relative path from the part root to the section JSON file, "
            "e.g. 'structure/sections/cap5/sec2.json'."
        ),
    )

    @field_validator("relative_path")
    @classmethod
    def _validate_relative_path(cls, value: str) -> str:
        pure = PurePosixPath(value)
        if "\\" in value or pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise ValueError("SectionRef.relative_path must be a contained POSIX relative path")
        return pure.as_posix()


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
    def _check_spanish_translations(self) -> Section:
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
    def _check_spanish_translations(self) -> Chapter:
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
    fetched_at: datetime
    definition_reviewed_by: _Reviewer
    definition_reviewed_at: date
    chapters: tuple[Chapter, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _check_spanish_translations(self) -> Manual:
        _require_spanish(self.title, "Manual.title")
        _require_spanish(self.summary, "Manual.summary")
        return self


class FetchedManualPart(_ManualStrictFrozen):
    """Manifest record for a fetched raw manual part.

    Committed to disk as ``manifest.json`` next to the raw ``source.pdf``
    blob. The raw PDF itself is git-ignored; this record is the
    authoritative contract that ``aeat manual fetch`` uses to verify
    subsequent re-downloads via sha256.
    """

    manual_id: ManualId
    year: _YearField
    part: ManualPart
    source_pdf_url: AnyHttpUrl
    relative_pdf_path: str = Field(
        min_length=1,
        description="POSIX-style path from the part root to the raw PDF (typically 'source.pdf').",
    )
    sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
        description="Lower-case hex sha256 of the fetched bytes.",
    )
    content_length: int = Field(ge=1, description="Size of the fetched PDF in bytes.")
    fetched_at: datetime = Field(description="UTC timestamp the PDF was fetched.")
    synthetic: bool = Field(
        default=False,
        description="Always False for fetched records; kept for diff-friendliness with synthetic fixtures.",
    )

    @field_validator("relative_pdf_path")
    @classmethod
    def _validate_relative_pdf_path(cls, value: str) -> str:
        pure = PurePosixPath(value)
        if "\\" in value or pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise ValueError("FetchedManualPart.relative_pdf_path must be a contained POSIX relative path")
        return pure.as_posix()


class ManualCatalogue(_StrictLoose):
    """Aggregate view over every :class:`Manual` loaded from ``corpus/manuals/``.

    The catalogue is keyed by ``(manual_id, year, part)`` and exposes
    a flat rule iterator the rest of the project consumes. It is
    mutable because loading is incremental; individual :class:`Manual`
    instances are frozen, so callers cannot corrupt loaded records in
    place.

    Attributes:
        manuals: The loaded :class:`Manual` records, in load order.
    """

    manuals: tuple[Manual, ...] = Field(default_factory=tuple)

    def __iter__(self):  # type: ignore[override]
        """Iterate over every loaded :class:`Manual`."""
        return iter(self.manuals)

    def __len__(self) -> int:
        """Return the number of loaded :class:`Manual` records."""
        return len(self.manuals)
