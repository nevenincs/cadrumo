"""Strict search-record schema for the compiled docs search index.

Per ADR D4 the compiled index unifies four record kinds (concept cards,
casilla projections, CLI surface records, doc pages). This module owns
the shared base every kind extends -- a strict, frozen pydantic model
carrying the ``kind`` discriminator, the four-language localised
descriptions, and the legal grounding -- plus the casilla projection
record built by the casilla-projection compiler.

The shared :class:`SearchRecordBase` is the seam the sibling CLI-surface
and concept-card emitters extend: they declare their own ``kind`` member
and add kind-specific fields, reusing the localised description map and
the strict-frozen config defined here so all four record kinds serialise
to one homogeneous index payload.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from aeat.core import Modelo
from aeat.core.external_constants import OutputLanguage

__all__ = [
    "CasillaSearchRecord",
    "SearchRecordBase",
    "SearchRecordKind",
]

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class SearchRecordKind(StrEnum):
    """The four record kinds the compiled search index unifies (ADR D4)."""

    CONCEPT = "concept"
    CASILLA = "casilla"
    CLI = "cli"
    PAGE = "page"


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
    """A machine-projected search record for one AEAT casilla (ADR D4).

    Built from registry snapshots, never hand-curated. Identity is the
    ``(modelo, number, segmento)`` triple, deduplicated across revisions.
    The localised descriptions are the registry casilla ``label`` (es
    invariant) plus per-revision ``localized_labels`` (en / ca / hu) where
    authored -- conforming to the official casilla descriptions. The
    ``legal_refs`` / ``source_refs`` provenance is carried verbatim from
    the casilla definition (the calculation-grounding contract).
    """

    kind: SearchRecordKind = SearchRecordKind.CASILLA
    modelo: Modelo
    number: str = Field(min_length=1, max_length=160)
    segmento: str | None = Field(default=None, min_length=1, max_length=32)
    section: tuple[str, ...] = ()
    semantic_role: str | None = Field(default=None, min_length=1, max_length=128)
    legal_refs: tuple[str, ...] = Field(min_length=1)
    source_refs: tuple[str, ...] = Field(min_length=1)
    #: The revision ids this record was projected/deduplicated from, latest first.
    source_revisions: tuple[str, ...] = Field(min_length=1)

    @property
    def dedup_key(self) -> tuple[str, str, str]:
        """The cross-revision dedup identity ``(modelo, number, segmento)``."""
        return (self.modelo.value, self.number, self.segmento or "")
