"""Strict search-record schema for the compiled docs search index.

The compiled index unifies five record kinds (concept cards, casilla
projections, CLI surface records, doc pages, and legal provisions). This module owns
the shared base every kind extends -- a strict, frozen pydantic model
carrying the ``kind`` discriminator, the four-language localised
descriptions, and the legal grounding -- plus the casilla projection
record built by the casilla-projection compiler.

The shared :class:`SearchRecordBase` is the seam the sibling CLI-surface
and concept-card emitters extend: they declare their own ``kind`` member
and add kind-specific fields, reusing the localised description map and
the strict-frozen config defined here so all five record kinds serialise
to one homogeneous index payload.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core import Modelo
from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.ids import (
    BindingId,
    FormulaId,
)
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind

__all__ = [
    "CasillaSearchRecord",
    "LegalSearchRecord",
    "ResultDisplayClass",
    "SearchRecordBase",
    "SearchRecordKind",
]

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class SearchRecordKind(StrEnum):
    """The five record kinds the compiled search index unifies."""

    CONCEPT = "concept"
    CASILLA = "casilla"
    CLI = "cli"
    PAGE = "page"
    LEGAL = "legal"


class ResultDisplayClass(StrEnum):
    """The closed visual/ranking display class a search result carries.

    Orthogonal to :class:`SearchRecordKind`: the record kind is the producing
    surface, whereas the display class is the operator-facing categorisation
    that drives both the result icon and the user-first ranking ladder. A
    CONCEPT record splits across two classes by its Handbook domain -- a
    modelo-domain card is a ``MODELO`` document, a general-fact card is a
    ``DOC`` -- and full-text page
    hits split by path (``cli/`` -> ``CLI``, ``api/`` and dev machinery ->
    ``TECHNICAL``, everything else user-facing -> ``DOC``). Derived once at the
    injection seam and shipped in the Pagefind meta; the JS renderer reads it
    verbatim and never re-derives it.
    """

    CASILLA = "casilla"
    MODELO = "modelo"
    LEGAL = "legal"
    CLI = "cli"
    TECHNICAL = "technical"
    DOC = "doc"


class SearchRecordBase(BaseModel):
    """Shared base for every compiled docs search record.

    Carries the ``kind`` discriminator and the four-language localised
    description map (``es`` always present; ``en`` / ``ca`` / ``hu`` where
    a source provides them). The CLI-surface and concept-card emitters
    extend this with their kind-specific fields.
    """

    model_config = _STRICT_FROZEN

    kind: SearchRecordKind
    #: Localised short descriptions keyed by output language. ``es`` is the
    #: invariant and is always present; other languages appear only where a
    #: source authored them.
    descriptions: dict[OutputLanguage, str] = Field(min_length=1)

    @property
    def description_es(self) -> str:
        """The Spanish-invariant description (always present)."""
        return self.descriptions[OutputLanguage.ES]


class CasillaSearchRecord(SearchRecordBase):
    """A machine-projected search record for one AEAT casilla.

    Built from registry snapshots, never hand-curated. Identity is
    ``(modelo, casilla_id)``, deduplicated across revisions. ``number`` and
    ``segmento`` are retained only as reviewed AEAT display/export metadata.
    The localised descriptions are resolved from the canonical shared
    catalogue for every supported output language. The registry definition
    contract is carried alongside them: localized help,
    value shape, input kind, requiredness, and the canonical binding/formula
    identities. The ``legal_refs`` / ``source_refs`` provenance is carried
    verbatim from the casilla definition (the calculation-grounding contract).
    """

    kind: SearchRecordKind = SearchRecordKind.CASILLA
    modelo: Modelo
    casilla_id: CasillaId
    localized_help: dict[str, str] = Field(default_factory=dict)
    data_type: str
    input_kind: InputKind
    required: bool
    binding: BindingId | None = None
    formula_id: FormulaId | None = None
    number: str = Field(min_length=1, max_length=160)
    segmento: str | None = Field(default=None, min_length=1, max_length=32)
    section: tuple[str, ...] = ()
    semantic_role: str | None = Field(default=None, min_length=1, max_length=128)
    legal_refs: tuple[str, ...] = Field(min_length=1)
    source_refs: tuple[str, ...] = Field(min_length=1)
    #: The revision ids this record was projected/deduplicated from, latest first.
    source_revisions: tuple[str, ...] = Field(min_length=1)

    @property
    def dedup_key(self) -> tuple[str, CasillaId]:
        """The cross-revision dedup identity ``(modelo, casilla_id)``."""
        return (self.modelo.value, self.casilla_id)


class LegalSearchRecord(SearchRecordBase):
    """One registry-backed legal catalogue provision for the docs index.

    The projection carries authored catalogue metadata unchanged and receives
    its site-relative target from the generated legal-reference renderer. The
    BOE permalink remains typed provenance on the record; it is rendered at
    the generated destination and is never used as the search target.
    """

    kind: SearchRecordKind = SearchRecordKind.LEGAL
    record_id: str = Field(min_length=1, max_length=320)
    title: str = Field(min_length=1, max_length=320)
    target: str = Field(min_length=1, max_length=512)
    legal_id: str = Field(min_length=1, max_length=320)
    legal_kind: str = Field(min_length=1, max_length=128)
    document_id: str = Field(min_length=1, max_length=320)
    corpus_ref: str = Field(min_length=1, max_length=512)
    permalink: str = Field(min_length=1, max_length=512)
    authority: str | None = Field(default=None, min_length=1, max_length=128)
    evidence_tier: str | None = Field(default=None, min_length=1, max_length=128)
    article: str | None = Field(default=None, min_length=1, max_length=320)
    section: str | None = Field(default=None, min_length=1, max_length=320)
    published_at: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    consolidated_as_of: date | None = None
    review_status: str | None = Field(default=None, min_length=1, max_length=64)
    reviewed_at: date | None = None
    reviewed_by: str | None = Field(default=None, min_length=1, max_length=160)
    notes: str | None = None
    required_text: tuple[str, ...] = ()
    search_aliases: tuple[str, ...] = ()
