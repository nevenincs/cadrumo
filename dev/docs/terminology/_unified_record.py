"""The unified search record -- one homogeneous index payload.

The five projected record kinds -- concept cards, casilla projections, CLI
surface records, doc pages, and legal provisions -- are heterogeneous (each
carries kind-specific fields). The compiled search index, and the Pagefind
injection that consumes
it, need ONE homogeneous shape per entry. :class:`SearchRecord` is that shape:
a strict frozen pydantic record carrying a stable ``id``, the ``kind``
discriminator, a ``title``, the four-language ``descriptions`` map, a ``target``
URL/anchor a palette card jumps to, a normalised ``ranking_weight``, and typed
``metadata``.

:func:`to_search_record` is the uniform serialisation funnel: it projects any
of the five kind records into a :class:`SearchRecord`, deriving the per-kind
``id`` / ``title`` / ``target`` and the base ranking weight. The ranking
authority is the user-first per-display-class ladder
:data:`_DISPLAY_CLASS_BASE_WEIGHT` (user documentation first, then modelo,
casilla, CLI, and dev-machinery pages last), so an injected record
ranks by the display class :func:`derive_display_class` assigns it.
:data:`_KIND_BASE_WEIGHT` is a derived legacy per-kind projection of that one
table, retained only for the sweep-relevance reweight path that keys on record
kind rather than the fully-derived display class.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.ids import (
    BindingId,
    FormulaId,
    ModeloId,
)
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind

from ..terminology_handbook import ConceptDomain
from ._casilla_anchor import casilla_reference_target
from ._casilla_projection import CasillaSearchRecord
from ._cli_projection import CliOptionRecord, CliSurfaceRecord
from ._concept_cards import ConceptCardRecord
from ._glossary_anchor import glossary_term_anchor
from ._search_record import LegalSearchRecord, ResultDisplayClass, SearchRecordKind

__all__ = [
    "RankingTier",
    "ResultDisplayClass",
    "SearchRecord",
    "SearchRecordMetadata",
    "casilla_search_record_id",
    "contain_boost_in_band",
    "derive_display_class",
    "display_class_band_ceiling",
    "display_class_base_weight",
    "kind_base_weight",
    "normalise_display_class_weight",
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
    """The three palette ranking tiers.

    The palette surfaces term cards first, navigation (CLI / casilla
    namespaces) second, and full-text pages third. The tier is the coarse
    ordering axis; the per-record ``ranking_weight`` is the fine axis within
    and across tiers.
    """

    TERM = "term"
    NAVIGATION = "navigation"
    FULLTEXT = "fulltext"


#: The single declared user-first base-weight ladder, keyed by display class
#: Highest sorts first:
#: general-fact concept cards (``DOC``) lead, then modelo document cards, then
#: casilla rows, then CLI records, and full-text ``TECHNICAL`` (api / dev
#: machinery) pages rank last. This amends the prior per-kind ladder in two
#: ways only -- casilla now outranks cli, and the full-text tier splits
#: so dev-machinery pages sink below user documentation (a user-doc page is
#: ``DOC`` and shares the top band, but the retained :class:`RankingTier`
#: coarse axis keeps full-text pages below the term/navigation cards, so term
#: cards still lead). The sweep score, when present, modulates within a class's
#: band via :func:`normalise_display_class_weight`.
_DISPLAY_CLASS_BASE_WEIGHT: dict[ResultDisplayClass, float] = {
    ResultDisplayClass.DOC: 1.0,
    ResultDisplayClass.MODELO: 0.9,
    ResultDisplayClass.CASILLA: 0.8,
    # A BOE article or Orden GROUNDS a modelo/casilla surface rather than
    # answering the operator's question, so it ranks below both. Aliasing it
    # to DOC (1.0) put every legal provision above the very cards it grounds.
    ResultDisplayClass.LEGAL: 0.75,
    ResultDisplayClass.CLI: 0.7,
    ResultDisplayClass.TECHNICAL: 0.5,
}

#: Legacy per-kind projection of the one class table, for the sweep-relevance
#: reweight path (``_resolution._reweight``) that keys on record kind rather
#: than the fully-derived display class. CONCEPT collapses to the general-fact
#: ``DOC`` band (a per-hit reweight has no Handbook domain to split on), legal
#: provisions carry their own ``LEGAL`` band beneath casilla, and a
#: full-text PAGE hit collapses to the ``TECHNICAL`` floor. Derived so the
#: per-kind values can never drift from the one declared table.
_KIND_TO_DISPLAY_CLASS: dict[SearchRecordKind, ResultDisplayClass] = {
    SearchRecordKind.CONCEPT: ResultDisplayClass.DOC,
    SearchRecordKind.CASILLA: ResultDisplayClass.CASILLA,
    SearchRecordKind.CLI: ResultDisplayClass.CLI,
    SearchRecordKind.PAGE: ResultDisplayClass.TECHNICAL,
    SearchRecordKind.LEGAL: ResultDisplayClass.LEGAL,
}

_KIND_BASE_WEIGHT: dict[SearchRecordKind, float] = {
    kind: _DISPLAY_CLASS_BASE_WEIGHT[display_class] for kind, display_class in _KIND_TO_DISPLAY_CLASS.items()
}

#: Exclusive upper bound of the highest band. The declared weights are already
#: normalised to this scale, so the top class floors at the ceiling and has no
#: headroom to promote within -- see :func:`contain_boost_in_band`.
_TOP_BAND_CEILING: float = 1.0

#: Fraction of a band's headroom a boost may claim. Strictly below 1 so a
#: fully-boosted record approaches its band's ceiling without reaching it, and
#: therefore never ties with, let alone overtakes, the floor of the class above.
_BAND_HEADROOM_RESERVE: float = 0.9


def display_class_base_weight(display_class: ResultDisplayClass) -> float:
    """Return the declared base ranking weight for a display class."""
    return _DISPLAY_CLASS_BASE_WEIGHT[display_class]


def display_class_band_ceiling(display_class: ResultDisplayClass) -> float:
    """Return the exclusive upper bound of a display class's ranking band.

    A class's band runs from its declared weight up to the next-higher class's
    declared weight; the top class is bounded by 1.0. Derived from the one
    declared table by sorting it, so a reordered or extended table cannot leave
    a hand-listed ceiling behind.
    """
    floor = _DISPLAY_CLASS_BASE_WEIGHT[display_class]
    higher = [weight for weight in _DISPLAY_CLASS_BASE_WEIGHT.values() if weight > floor]
    return min(higher) if higher else _TOP_BAND_CEILING


def contain_boost_in_band(display_class: ResultDisplayClass, boost: float) -> float:
    """Map a committed relevance boost into the class's own band.

    A per-query boost orders records WITHIN a display class; the declared
    ladder orders classes against each other. Taking the stronger of a boost
    and the base weight conflated the two, so any record that topped a single
    query was promoted for every query and outranked whole classes above it.

    The boost is therefore mapped into the interval between the class's floor
    and the next class's floor, reserving a margin so the result stays strictly
    below that ceiling. A zero boost yields the floor exactly, preserving the
    ladder; a full boost approaches but never reaches the class above.

    The top class has no headroom (its floor is the ceiling), so its records
    sit at the ceiling and order by the engine's own lexical score. That class
    is already first, so it needs no promotion.
    """
    floor = _DISPLAY_CLASS_BASE_WEIGHT[display_class]
    headroom = display_class_band_ceiling(display_class) - floor
    clamped = min(1.0, max(0.0, boost))
    return round(floor + clamped * headroom * _BAND_HEADROOM_RESERVE, 6)


def kind_base_weight(kind: SearchRecordKind) -> float:
    """Return the base ranking weight for a record kind (legacy per-kind view).

    A thin projection of the one declared per-display-class table via
    :data:`_KIND_TO_DISPLAY_CLASS`; retained for the sweep-relevance reweight
    path that keys on record kind. Injected records rank through the fully
    derived display class instead (:func:`derive_display_class`).
    """
    return _KIND_BASE_WEIGHT[kind]


def _modulate(base: float, sweep_score: float | None) -> float:
    """Modulate a base weight by an optional sweep score within ``[base*0.5, base]``.

    The score scales the upper half of the class band so the declared ladder
    ordering is preserved (a weakly-scored higher band never drops below a
    strongly-scored lower band) while relevance still sorts within a band. A
    ``None`` score keeps the base weight; an out-of-range score clamps.
    """
    if sweep_score is None:
        return base
    clamped = min(1.0, max(0.0, sweep_score))
    return round(base * (0.5 + 0.5 * clamped), 6)


def normalise_display_class_weight(
    display_class: ResultDisplayClass,
    sweep_score: float | None = None,
) -> float:
    """Normalise a record's ranking weight onto the one user-first ladder.

    The base weight is the declared per-display-class ladder value; the sweep
    score (when present) modulates it within the class band. This is the base
    weight every injected search record carries.

    Args:
        display_class: The record's display class (selects the base weight).
        sweep_score: Optional RAG relevance score in ``[0, 1]``; clamped.

    Returns:
        A ranking weight in ``[0, 1]``, comparable across all display classes.
    """
    return _modulate(_DISPLAY_CLASS_BASE_WEIGHT[display_class], sweep_score)


def normalise_ranking_weight(kind: SearchRecordKind, sweep_score: float | None = None) -> float:
    """Normalise a record's ranking weight from its record kind (legacy view).

    Projects the record kind onto the one declared per-display-class ladder
    (:func:`kind_base_weight`) and modulates by the sweep score. Retained for
    the sweep-relevance reweight path; injected records normalise through the
    fully derived display class (:func:`normalise_display_class_weight`).

    Args:
        kind: The record kind (projects to a display-class band).
        sweep_score: Optional RAG relevance score in ``[0, 1]``; clamped.

    Returns:
        A ranking weight in ``[0, 1]``, comparable across all kinds.
    """
    return _modulate(_KIND_BASE_WEIGHT[kind], sweep_score)


def _display_class_for(
    kind: SearchRecordKind,
    domain: str | None,
    target: str,
) -> ResultDisplayClass:
    """Derive the display class from a record's kind, concept domain, and target.

    The single derivation authority: CASILLA records are ``CASILLA``;
    CLI records are ``CLI``; a CONCEPT card splits by Handbook domain -- a
    modelo-domain card is a ``MODELO`` document, every other domain (a
    general-fact concept: régimen, período, legal, concepto, ...) is a ``DOC``;
    a full-text PAGE hit splits by path -- under ``cli/`` it is ``CLI``, under
    ``api/`` (or any dev-machinery surface) it is ``TECHNICAL``, everything else
    user-facing is ``DOC``.
    """
    if kind is SearchRecordKind.CASILLA:
        return ResultDisplayClass.CASILLA
    if kind is SearchRecordKind.CLI:
        return ResultDisplayClass.CLI
    if kind is SearchRecordKind.CONCEPT:
        if domain == ConceptDomain.MODELO.value:
            return ResultDisplayClass.MODELO
        return ResultDisplayClass.DOC
    if kind is SearchRecordKind.LEGAL:
        return ResultDisplayClass.LEGAL
    path = target.split("#", 1)[0].lstrip("/")
    if path.startswith("cli/"):
        return ResultDisplayClass.CLI
    if path.startswith("api/"):
        return ResultDisplayClass.TECHNICAL
    return ResultDisplayClass.DOC


def derive_display_class(record: SearchRecord) -> ResultDisplayClass:
    """Derive the closed display class for a finished unified search record.

    The public seam over :func:`_display_class_for`: reads the record's kind,
    its concept ``metadata.domain`` (``None`` for non-concept kinds), and its
    ``target`` path. Total over every kind -- no record falls through to a null
    class -- so the injection seam can ship exactly one class per record and the
    coverage gate can prove it.
    """
    return _display_class_for(record.kind, record.metadata.domain, record.target)


class SearchRecordMetadata(BaseModel):
    """Typed kind-specific metadata carried on a unified :class:`SearchRecord`.

    Every field is optional: a record populates only the fields its kind
    provides. Concepts carry ``concept_id`` / ``domain`` / ``lifecycle``;
    casillas carry canonical ``modelo`` / ``casilla_id`` plus display/export
    metadata ``number`` / ``segmento``, the registry definition contract, and
    provenance ``legal_refs`` / ``source_refs`` / ``source_revisions``; CLI
    records carry ``command_path`` / ``registry_key`` / ``option_names``; legal
    records carry their authored catalogue metadata and BOE grounding. This
    keeps the unified payload one shape while preserving the definition and
    provenance the calculation-grounding contract requires (legal/source refs
    survive into the unified record).
    """

    model_config = _STRICT_FROZEN

    # Concept fields.
    concept_id: str | None = Field(default=None, min_length=1, max_length=64)
    domain: str | None = Field(default=None, min_length=1, max_length=64)
    lifecycle: str | None = Field(default=None, min_length=1, max_length=32)
    # Casilla fields.
    modelo: ModeloId | None = None
    casilla_id: CasillaId | None = None
    localized_help: dict[str, str] = Field(default_factory=dict)
    data_type: str | None = None
    input_kind: InputKind | None = None
    required: bool | None = None
    binding: BindingId | None = None
    formula_id: FormulaId | None = None
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
    # Legal catalogue fields.
    legal_id: str | None = Field(default=None, min_length=1, max_length=320)
    legal_kind: str | None = Field(default=None, min_length=1, max_length=128)
    legal_document_id: str | None = Field(default=None, min_length=1, max_length=320)
    legal_corpus_ref: str | None = Field(default=None, min_length=1, max_length=512)
    legal_permalink: str | None = Field(default=None, min_length=1, max_length=512)
    legal_authority: str | None = Field(default=None, min_length=1, max_length=128)
    legal_evidence_tier: str | None = Field(default=None, min_length=1, max_length=128)
    legal_article: str | None = Field(default=None, min_length=1, max_length=320)
    legal_section: str | None = Field(default=None, min_length=1, max_length=320)
    legal_published_at: date | None = None
    legal_effective_from: date | None = None
    legal_effective_to: date | None = None
    legal_consolidated_as_of: date | None = None
    legal_review_status: str | None = Field(default=None, min_length=1, max_length=64)
    legal_reviewed_at: date | None = None
    legal_reviewed_by: str | None = Field(default=None, min_length=1, max_length=160)
    legal_notes: str | None = None
    legal_required_text: tuple[str, ...] = ()


class SearchRecord(BaseModel):
    """One homogeneous compiled-index entry over the five record kinds.

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

KindRecord = LegalSearchRecord | CasillaSearchRecord | CliSurfaceRecord | CliOptionRecord | ConceptCardRecord


def to_search_record(record: KindRecord, *, sweep_score: float | None = None) -> SearchRecord:
    """Project any of the five kind records into a unified :class:`SearchRecord`.

    Derives the per-kind ``id`` / ``title`` / ``target`` and the normalised
    ranking weight, copying the four-language ``descriptions`` verbatim and
    carrying the kind-specific provenance into typed ``metadata``.

    Args:
        record: A concept-card, casilla, legal, CLI-surface, or CLI-option record.
        sweep_score: Optional RAG relevance score that modulates the weight.

    Returns:
        The unified :class:`SearchRecord`.
    """
    if isinstance(record, ConceptCardRecord):
        return _from_concept(record, sweep_score)
    if isinstance(record, CasillaSearchRecord):
        return _from_casilla(record, sweep_score)
    if isinstance(record, LegalSearchRecord):
        return _from_legal(record, sweep_score)
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
    target = f"{GLOSSARY_PAGE}#{glossary_term_anchor(title)}"
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
        target=target,
        # A modelo-domain card ranks in the ``MODELO`` document band; every
        # general-fact card (régimen, período, legal, concepto, ...) ranks in
        # the top general-fact ``DOC`` band.
        ranking_weight=normalise_display_class_weight(
            _display_class_for(SearchRecordKind.CONCEPT, record.domain.value, target),
            sweep_score,
        ),
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
        # Deep-link to the per-modelo casilla reference page and the casilla's
        # anchor, both derived from the ONE slug authority the generator renders
        # against (casilla_reference_target -> casilla_page_anchor), so card and
        # landing page can never disagree. The former search.html?q= hand-off (a
        # search-for-itself, forbidden as a record target by the destination
        # contract) is gone entirely - no dual-target bridge.
        target=casilla_reference_target(record.modelo, record.casilla_id),
        ranking_weight=normalise_display_class_weight(ResultDisplayClass.CASILLA, sweep_score),
        metadata=SearchRecordMetadata(
            modelo=record.modelo.value,
            casilla_id=record.casilla_id,
            localized_help=dict(record.localized_help),
            data_type=record.data_type,
            input_kind=record.input_kind,
            required=record.required,
            binding=record.binding,
            # The projection has the canonical formula id but not the
            # revision's formula table, so the unified record deliberately
            # carries no invented expression or synthetic formula target.
            formula_id=record.formula_id,
            number=record.number,
            segmento=record.segmento,
            source_revisions=record.source_revisions,
            legal_refs=record.legal_refs,
            source_refs=record.source_refs,
        ),
    )


def _from_legal(record: LegalSearchRecord, sweep_score: float | None) -> SearchRecord:
    return SearchRecord(
        id=record.record_id,
        kind=SearchRecordKind.LEGAL,
        tier=RankingTier.FULLTEXT,
        title=record.title,
        descriptions=dict(record.descriptions),
        # The target comes from legal_reference.render_legal_reference(). Its
        # page/anchor authority is the same one that emits the destination;
        # the BOE permalink remains destination provenance in typed metadata.
        target=record.target,
        ranking_weight=normalise_display_class_weight(ResultDisplayClass.LEGAL, sweep_score),
        search_aliases=record.search_aliases,
        metadata=SearchRecordMetadata(
            legal_id=record.legal_id,
            legal_kind=record.legal_kind,
            legal_document_id=record.document_id,
            legal_corpus_ref=record.corpus_ref,
            legal_permalink=record.permalink,
            legal_authority=record.authority,
            legal_evidence_tier=record.evidence_tier,
            legal_article=record.article,
            legal_section=record.section,
            legal_published_at=record.published_at,
            legal_effective_from=record.effective_from,
            legal_effective_to=record.effective_to,
            legal_consolidated_as_of=record.consolidated_as_of,
            legal_review_status=record.review_status,
            legal_reviewed_at=record.reviewed_at,
            legal_reviewed_by=record.reviewed_by,
            legal_notes=record.notes,
            legal_required_text=record.required_text,
            legal_refs=(record.legal_id,),
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
        ranking_weight=normalise_display_class_weight(ResultDisplayClass.CLI, sweep_score),
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
        ranking_weight=normalise_display_class_weight(ResultDisplayClass.CLI, sweep_score),
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
