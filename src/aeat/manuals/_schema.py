"""Strict pydantic v2 schema for the AEAT *Manual práctico* corpus.

Every boundary-crossing record the ``aeat.manuals`` subpackage reads
from disk, writes to disk, or exposes over its public API is defined
here. The schema is frozen and strict wherever the loader idiom
permits it, per the project-wide pydantic v2 mandate reinforced by
issue ``#25``.

Closed catalogues are ``enum.StrEnum``. Trilingual fields use
``aeat.i18n.Translatable``. Modelo casilla cross-references are stored
as validated strings (``MODELO_130:01`` shape) so the manuals corpus
stays loadable even when a citation references a casilla outside the
:class:`aeat.casillas.CasillaRecord` catalogue at load time.

Spanish is the authoritative language for AEAT-domain terminology per
the trilingual i18n ADR. Spanish-authoritative translatable fields on
persisted records are validated at load time to guarantee the ``es``
key is present; missing ``en`` / ``hu`` are surfaced as warnings by
the verification pipeline, not hard errors.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ..i18n import Translatable
from ._stubs import MODELO_CASILLA_PATTERN


class ManualId(StrEnum):
    """Identifier for a *Manual práctico* volume.

    The enum is intentionally small in v1 (only the handbooks relevant
    to an autónomo) and extensible by follow-ups.
    """

    RENTA = "renta"
    IVA = "iva"


class ManualPart(StrEnum):
    """Volume split for a handbook within a single tax year.

    ``SINGLE`` covers IVA which is published as one volume. Renta from
    2024 onward is split into a main ``PARTE_1`` and the autonómica
    deductions ``PARTE_2_DEDUCCIONES_AUTONOMICAS``.
    """

    SINGLE = "single"
    PARTE_1 = "parte1"
    PARTE_2_DEDUCCIONES_AUTONOMICAS = "parte2-deducciones-autonomicas"


class RuleKind(StrEnum):
    """Closed catalogue of rule categories extracted from the handbook."""

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

# Modelo + casilla cross-reference, e.g. ``MODELO_130:01``. Validated as a
# constrained string so manuals can cite casillas that may not yet exist in
# the casilla catalogue at load time.
_CasillaRef = Annotated[str, StringConstraints(strip_whitespace=True, pattern=MODELO_CASILLA_PATTERN)]

# Legal-act reference: free-form but trimmed + non-empty, e.g. "Ley 35/2006, art. 32".
_LegalActRef = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]

# Review year bounds: AEAT publishes a new manual every year; guard against
# absurd values while staying lenient for historical backfills.
_YearField = Annotated[int, Field(ge=2000, le=2100)]


def _require_spanish(translatable: Translatable, field_name: str) -> None:
    """Assert a translatable carries the authoritative ``es`` key."""
    if not translatable.get("es"):
        raise ValueError(f"{field_name}: missing authoritative Spanish ('es') translation")


class _StrictFrozen(BaseModel):
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


class LLMProvenance(_StrictFrozen):
    """Record of which LLM call produced a draft extraction.

    Attached to every LLM-drafted ``Rule`` so reviewers can trace the
    origin and so follow-ups can invalidate drafts keyed on a
    deprecated prompt template.
    """

    provider: str = Field(min_length=1, max_length=64, description="Provider key, e.g. 'anthropic'.")
    model: str = Field(min_length=1, max_length=128, description="Concrete model name used for the draft.")
    prompt_id: str = Field(min_length=1, max_length=128, description="Named prompt from the #21 prompt registry.")
    cache_hit: bool = Field(description="Whether the draft was served from the LLM cache.")
    extracted_at: datetime = Field(description="UTC timestamp the draft was produced.")


class SectionSource(_StrictFrozen):
    """Provenance pointer for a ``Section`` back to the source handbook."""

    manual_url: AnyHttpUrl = Field(description="Canonical AEAT URL the section was extracted from.")
    page: int = Field(ge=1, description="1-indexed page number in the PDF.")


class RuleSource(_StrictFrozen):
    """Provenance pointer for a ``Rule`` back to the source handbook."""

    manual_url: AnyHttpUrl = Field(description="Canonical AEAT URL the rule was extracted from.")
    page: int = Field(ge=1, description="1-indexed page number in the PDF.")
    paragraph: int | None = Field(default=None, ge=1, description="Optional paragraph index within the page.")


class Paragraph(_StrictFrozen):
    """A single Spanish source paragraph within a section."""

    paragraph_id: _StableId = Field(description="Stable identifier, unique within its section.")
    text: str = Field(min_length=1, description="Spanish source prose (authoritative).")
    page: int = Field(ge=1, description="1-indexed page number in the PDF.")


class Rule(_StrictFrozen):
    """A single extracted rule from the *Manual práctico*.

    Every persisted rule carries reviewer metadata populated by a real
    human; the verify CLI rejects rules missing those fields when
    ``AEAT_MANUALS_REVIEW_REQUIRED`` is true.
    """

    rule_id: _StableId
    manual_id: ManualId
    year: _YearField
    part: ManualPart
    chapter_id: _StableId
    section_id: _StableId
    kind: RuleKind
    statement: Translatable = Field(description="Rule statement in all supplied languages.")
    applies_when: str | None = Field(
        default=None,
        description="Optional natural-language predicate describing the rule's applicability.",
    )
    references_casillas: tuple[_CasillaRef, ...] = Field(
        default_factory=tuple,
        description="Cross-references to modelo casillas (e.g. 'MODELO_130:01').",
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


class SectionRef(_StrictFrozen):
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


class Section(_StrictFrozen):
    """A structured section of a handbook chapter."""

    section_id: _StableId
    chapter_id: _StableId
    title: Translatable
    summary: Translatable
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


class Chapter(_StrictFrozen):
    """A handbook chapter: metadata plus ordered section references."""

    chapter_id: _StableId
    title: Translatable
    summary: Translatable
    sections: tuple[SectionRef, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _check_spanish_translations(self) -> Chapter:
        _require_spanish(self.title, "Chapter.title")
        _require_spanish(self.summary, "Chapter.summary")
        return self


class Manual(_StrictFrozen):
    """Root record for a single ``(manual_id, year, part)`` volume."""

    manual_id: ManualId
    year: _YearField
    part: ManualPart
    title: Translatable
    summary: Translatable
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


class FetchedManualPart(_StrictFrozen):
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
    """Aggregate view over every ``Manual`` loaded from ``corpus/manuals/``.

    The catalogue is keyed by ``(manual_id, year, part)`` and exposes a
    flat rule iterator the rest of the project consumes. It is mutable
    because loading is incremental; individual ``Manual`` instances are
    frozen, so callers cannot corrupt loaded records in place.
    """

    manuals: tuple[Manual, ...] = Field(default_factory=tuple)

    def __iter__(self):  # type: ignore[override]
        """Iterate over every loaded ``Manual``."""
        return iter(self.manuals)

    def __len__(self) -> int:
        """Return the number of loaded ``Manual`` records."""
        return len(self.manuals)
