"""The unified search record -- one homogeneous index payload (ADR D4/D6).

The four projected record kinds -- concept cards, casilla projections, CLI
surface records, doc pages -- are heterogeneous (each carries kind-specific
fields). The compiled search index, and the Pagefind injection that consumes
it, need ONE homogeneous shape per entry. :class:`SearchRecord` is that shape:
a strict frozen pydantic record carrying a stable ``id``, the ``kind``
discriminator, a ``title``, the four-language ``descriptions`` map, a ``target``
URL/anchor a palette card jumps to, a normalised ``ranking_weight``, and typed
``metadata``.

:func:`to_search_record` is the uniform serialisation funnel: it projects any
of the four kind records into a :class:`SearchRecord`, deriving the per-kind
``id`` / ``title`` / ``target`` and the base ranking weight. The weight
normalisation (ADR D5: "term cards first, nav second, full text third") lives
in :data:`_KIND_BASE_WEIGHT` so a casilla hit, a concept hit, a BOE-article
hit, and a code hit rank comparably in the unified index.
"""

from __future__ import annotations

from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field

from aeat.core.external_constants import OutputLanguage
from aeat.domain.calculations.registry import CasillaId, ModeloId

from ._casilla_projection import CasillaSearchRecord
from ._cli_projection import CliOptionRecord, CliSurfaceRecord
from ._concept_cards import ConceptCardRecord
from ._glossary_anchor import glossary_term_anchor
from ._search_record import SearchRecordKind

__all__ = [
    "RankingTier",
    "SearchRecord",
    "SearchRecordMetadata",
    "casilla_search_record_id",
    "kind_base_weight",
    "normalise_ranking_weight",
    "to_search_record",
]

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

#: Built path of the generated glossary page. The glossary is generated into
#: ``docs/_generated/glossary.rst`` (the cutover moved it off the hand-written
#: ``docs/glossary.md``), so a concept card's deep link must target the built
#: ``_generated/glossary.html`` - a bare ``glossary.html`` no longer resolves.
GLOSSARY_PAGE = "_generated/glossary.html"


class RankingTier(StrEnum):
    """The three palette ranking tiers (ADR D5).

    The palette surfaces term cards first, navigation (CLI / casilla
    namespaces) second, and full-text pages third. The tier is the coarse
    ordering axis; the per-record ``ranking_weight`` is the fine axis within
    and across tiers.
    """

    TERM = "term"
    NAVIGATION = "navigation"
    FULLTEXT = "fulltext"


#: Per-kind base ranking weight (ADR D5 ordering: term cards first, navigation
#: second, full text third). A concept card outranks a CLI/casilla namespace
#: entry, which outranks a full-text page, for the same textual relevance. The
#: sweep score (when present) modulates within this base via
#: :func:`normalise_ranking_weight`.
_KIND_BASE_WEIGHT: dict[SearchRecordKind, float] = {
    SearchRecordKind.CONCEPT: 1.0,
    SearchRecordKind.CLI: 0.8,
    SearchRecordKind.CASILLA: 0.7,
    SearchRecordKind.PAGE: 0.5,
}


def kind_base_weight(kind: SearchRecordKind) -> float:
    """Return the base ranking weight for a record kind (ADR D5 ordering)."""
    return _KIND_BASE_WEIGHT[kind]


def normalise_ranking_weight(kind: SearchRecordKind, sweep_score: float | None = None) -> float:
    """Normalise a record's ranking weight onto a comparable cross-kind scale.

    The base weight encodes the ADR-D5 tier ordering (concept > nav > page).
    When a build-time RAG sweep produced a relevance ``sweep_score`` for the
    record (in ``[0, 1]``), it modulates the base multiplicatively but never
    lets a lower tier overtake a higher one: the modulated weight stays within
    ``[base * 0.5, base]`` so a weakly-scored concept never drops below a
    strongly-scored page. A record with no sweep score keeps its base weight.

    Args:
        kind: The record kind (selects the base weight / tier).
        sweep_score: Optional RAG relevance score in ``[0, 1]``; clamped.

    Returns:
        A ranking weight in ``[0, 1]``, comparable across all kinds.
    """
    base = _KIND_BASE_WEIGHT[kind]
    if sweep_score is None:
        return base
    clamped = min(1.0, max(0.0, sweep_score))
    # Modulate within [base*0.5, base]: the score scales the upper half of the
    # kind's band so tier ordering is preserved while relevance still sorts
    # within a kind.
    return round(base * (0.5 + 0.5 * clamped), 6)


class SearchRecordMetadata(BaseModel):
    """Typed kind-specific metadata carried on a unified :class:`SearchRecord`.

    Every field is optional: a record populates only the fields its kind
    provides. Concepts carry ``concept_id`` / ``domain`` / ``lifecycle``;
    casillas carry canonical ``modelo`` / ``casilla_id`` plus display/export
    metadata ``number`` / ``segmento`` and provenance ``legal_refs`` /
    ``source_refs`` / ``source_revisions``; CLI records carry ``command_path`` /
    ``registry_key`` / ``option_names``. This keeps the unified payload one
    shape while preserving the provenance the calculation-grounding contract
    requires (legal/source refs survive into the unified record).
    """

    model_config = _STRICT_FROZEN

    # Concept fields.
    concept_id: str | None = Field(default=None, min_length=1, max_length=64)
    domain: str | None = Field(default=None, min_length=1, max_length=64)
    lifecycle: str | None = Field(default=None, min_length=1, max_length=32)
    # Casilla fields.
    modelo: ModeloId | None = None
    casilla_id: CasillaId | None = None
    number: str | None = Field(default=None, min_length=1, max_length=160)
    segmento: str | None = Field(default=None, min_length=1, max_length=32)
    source_revisions: tuple[str, ...] = ()
    # CLI fields.
    command_path: str | None = Field(default=None, min_length=1, max_length=240)
    registry_key: str | None = Field(default=None, min_length=1, max_length=240)
    option_names: tuple[str, ...] = ()
    # Grounding provenance (calculation-grounding contract).
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


class SearchRecord(BaseModel):
    """One homogeneous compiled-index entry over the four record kinds (ADR D4).

    This is the shape the Pagefind ``addCustomRecord`` injection consumes:
    every projected kind funnels into it via :func:`to_search_record`, so the
    index payload is uniform. ``id`` is stable, unique within a build, and
    opaque for casilla records; casilla consumers must use typed
    ``metadata.modelo`` / ``metadata.casilla_id`` instead of parsing the record
    id. ``descriptions`` is the four-language card text (``es`` invariant);
    ``target`` is the URL/anchor a palette result jumps to; ``ranking_weight``
    is normalised across kinds; ``metadata`` carries the typed kind-specific
    provenance.
    """

    model_config = _STRICT_FROZEN

    id: str = Field(min_length=1, max_length=320)
    kind: SearchRecordKind
    tier: RankingTier
    title: str = Field(min_length=1, max_length=320)
    descriptions: dict[OutputLanguage, str] = Field(min_length=1)
    target: str = Field(min_length=1, max_length=512)
    ranking_weight: float = Field(ge=0.0, le=1.0)
    metadata: SearchRecordMetadata = Field(default_factory=SearchRecordMetadata)
    #: Extra searchable surface forms - every declared term label (preferred +
    #: admitted, all languages) and hidden search form for a concept. The
    #: Pagefind injection folds these into the record content so a query for any
    #: declared alias (the English "pro rata", the Catalan/Hungarian form, an
    #: unaccented variant) finds the card, delivering the cross-lingual matching
    #: the four declared translations were meant to provide.
    search_aliases: tuple[str, ...] = ()

    @property
    def description_es(self) -> str:
        """The Spanish-invariant card text (always present)."""
        return self.descriptions[OutputLanguage.ES]


# ---------------------------------------------------------------------------
# Uniform serialisation funnel
# ---------------------------------------------------------------------------

KindRecord = CasillaSearchRecord | CliSurfaceRecord | CliOptionRecord | ConceptCardRecord


def to_search_record(record: KindRecord, *, sweep_score: float | None = None) -> SearchRecord:
    """Project any of the four kind records into a unified :class:`SearchRecord`.

    Derives the per-kind ``id`` / ``title`` / ``target`` and the normalised
    ranking weight, copying the four-language ``descriptions`` verbatim and
    carrying the kind-specific provenance into typed ``metadata``.

    Args:
        record: A concept-card, casilla, CLI-surface, or CLI-option record.
        sweep_score: Optional RAG relevance score that modulates the weight.

    Returns:
        The unified :class:`SearchRecord`.
    """
    if isinstance(record, ConceptCardRecord):
        return _from_concept(record, sweep_score)
    if isinstance(record, CasillaSearchRecord):
        return _from_casilla(record, sweep_score)
    if isinstance(record, CliSurfaceRecord):
        return _from_cli_command(record, sweep_score)
    return _from_cli_option(record, sweep_score)


def casilla_search_record_id(modelo: ModeloId, casilla_id: CasillaId) -> str:
    """Return the opaque search-record id for one ``(modelo, casilla.id)`` pair.

    The metadata fields are the only canonical casilla reference surface. The
    record id exists for search-result dedupe and committed relevance stability,
    so it must not create a second parseable ``modelo:casilla`` notation.
    """

    digest = sha256(f"{modelo}\0{casilla_id}".encode()).hexdigest()[:24]
    return f"casilla-record:{digest}"


def _from_concept(record: ConceptCardRecord, sweep_score: float | None) -> SearchRecord:
    title = _preferred_label(record) or record.concept_id
    aliases: list[str] = []
    seen: set[str] = set()
    for alias in record.aliases:
        for form in (alias.label, *alias.hidden_search_forms):
            if form and form != title and form not in seen:
                seen.add(form)
                aliases.append(form)
    return SearchRecord(
        id=f"concept:{record.concept_id}",
        kind=SearchRecordKind.CONCEPT,
        tier=RankingTier.TERM,
        title=title,
        descriptions=dict(record.descriptions),
        # Deep-link to the headword-derived glossary anchor Sphinx actually
        # generates (e.g. "VIES" -> term-VIES), NOT the concept id (term-vies),
        # which only coincides when the id equals the headword slug. The
        # glossary-anchor-parity gate keeps the two in lock-step.
        target=f"{GLOSSARY_PAGE}#{glossary_term_anchor(title)}",
        ranking_weight=normalise_ranking_weight(SearchRecordKind.CONCEPT, sweep_score),
        search_aliases=tuple(aliases),
        metadata=SearchRecordMetadata(
            concept_id=record.concept_id,
            domain=record.domain.value,
            lifecycle=record.lifecycle.value,
            legal_refs=tuple(link.legal_ref for link in record.legal_links),
        ),
    )


def _from_casilla(record: CasillaSearchRecord, sweep_score: float | None) -> SearchRecord:
    title = f"Modelo {record.modelo.value} · casilla {record.casilla_id}"
    return SearchRecord(
        id=casilla_search_record_id(record.modelo.value, record.casilla_id),
        kind=SearchRecordKind.CASILLA,
        tier=RankingTier.NAVIGATION,
        title=title,
        descriptions=dict(record.descriptions),
        target=f"search.html?q={record.modelo.value}+{record.casilla_id}",
        ranking_weight=normalise_ranking_weight(SearchRecordKind.CASILLA, sweep_score),
        metadata=SearchRecordMetadata(
            modelo=record.modelo.value,
            casilla_id=record.casilla_id,
            number=record.number,
            segmento=record.segmento,
            source_revisions=record.source_revisions,
            legal_refs=record.legal_refs,
            source_refs=record.source_refs,
        ),
    )


def _from_cli_command(record: CliSurfaceRecord, sweep_score: float | None) -> SearchRecord:
    return SearchRecord(
        id=f"cli:{record.registry_key}",
        kind=SearchRecordKind.CLI,
        tier=RankingTier.NAVIGATION,
        title=record.command_path,
        descriptions=dict(record.descriptions),
        target=record.target,
        ranking_weight=normalise_ranking_weight(SearchRecordKind.CLI, sweep_score),
        metadata=SearchRecordMetadata(
            command_path=record.command_path,
            registry_key=record.registry_key,
        ),
    )


def _from_cli_option(record: CliOptionRecord, sweep_score: float | None) -> SearchRecord:
    option_token = record.option_names[0] if record.option_names else "option"
    return SearchRecord(
        id=f"cli-option:{record.command_path}:{option_token}",
        kind=SearchRecordKind.CLI,
        tier=RankingTier.NAVIGATION,
        title=f"{record.command_path} {option_token}",
        descriptions=dict(record.descriptions),
        target=record.target,
        ranking_weight=normalise_ranking_weight(SearchRecordKind.CLI, sweep_score),
        metadata=SearchRecordMetadata(
            command_path=record.command_path,
            option_names=record.option_names,
        ),
    )


def _preferred_label(record: ConceptCardRecord) -> str | None:
    """Return the concept's Spanish preferred term, if one is declared."""
    from ._concept_cards import TermAlias

    es_preferred: TermAlias | None = next(
        (
            alias
            for alias in record.aliases
            if alias.language is OutputLanguage.ES and alias.term_status.value == "preferred"
        ),
        None,
    )
    return es_preferred.label if es_preferred is not None else None
