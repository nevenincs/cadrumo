"""Real-behaviour conformance for the unified SearchRecord funnel.

The five typed input projections -- concept cards, casilla projections, legal
provisions, CLI surface records, and CLI option records -- funnel through
:func:`to_search_record` into one homogeneous :class:`SearchRecord` shape (the
Pagefind injection payload). These gates prove the funnel produces a uniform
record for every input projection, carries each projection's authored
descriptions and grounding provenance, and normalises ranking weights onto one
comparable cross-kind scale (term cards first, navigation second, full text
third).

No live CLI walk: the CLI records are constructed directly (their shape is the
contract under test, not their projection from the transiently-broken tree).
The concept, casilla, and legal records come from the real projections.
"""

from __future__ import annotations

import re

import pytest

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.modelo import Modelo

from .._cli_projection import CliOptionRecord, CliSurfaceRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_FOUR_LANGUAGES = frozenset(OutputLanguage)
_PARSEABLE_CASILLA_RECORD_ID_RE = re.compile(r"^casilla:[^:]+:.+")


def _cli_command_record() -> CliSurfaceRecord:
    from .._cli_projection import CliSurfaceRecord
    from ..search_record import SearchRecordKind

    return CliSurfaceRecord(
        kind=SearchRecordKind.CLI,
        descriptions={OutputLanguage.ES: "Anade una transaccion", OutputLanguage.EN: "Add a transaction"},
        command_path="aeat app ledger add",
        registry_key="ledger.add",
        family="app",
        target="cli/app.html#aeat-app-ledger-add",
    )


def _cli_option_record() -> CliOptionRecord:
    from .._cli_projection import CliOptionRecord
    from ..search_record import SearchRecordKind

    return CliOptionRecord(
        kind=SearchRecordKind.CLI,
        descriptions={OutputLanguage.ES: "Importe de la transaccion"},
        command_path="aeat app ledger add",
        option_names=("--amount",),
        is_argument=False,
        required=True,
        target="cli/app.html#aeat-app-ledger-add",
    )


# ---------------------------------------------------------------------------
# Homogeneous funnel — every kind becomes one shape
# ---------------------------------------------------------------------------


def test_concept_card_funnels_to_a_search_record() -> None:
    """A concept card funnels into a SearchRecord carrying its grounding refs."""
    from .._concept_cards import project_concept_cards
    from ..search_record import SearchRecordKind
    from ..unified_record import SearchRecord, to_search_record

    cards, _stats = project_concept_cards()
    prorrata = next(c for c in cards if c.concept_id == "prorrata")
    record = to_search_record(prorrata)

    assert isinstance(record, SearchRecord)
    assert record.kind is SearchRecordKind.CONCEPT
    assert record.id == "concept:prorrata"
    assert record.title == "prorrata"  # the es preferred label
    assert record.target == "_generated/glossary.html#term-prorrata"
    assert set(record.descriptions) == _FOUR_LANGUAGES
    assert record.metadata.concept_id == "prorrata"
    assert "ley-37-1992:art-104" in record.metadata.legal_refs


def test_casilla_funnels_to_a_search_record_with_provenance() -> None:
    """A casilla record funnels in, carrying legal_refs/source_refs provenance."""
    from ..casilla_projection import project_modelo_casillas
    from ..search_record import SearchRecordKind
    from ..unified_record import to_search_record

    records = project_modelo_casillas(Modelo.M303)
    record = to_search_record(records[0])

    assert record.kind is SearchRecordKind.CASILLA
    assert record.id.startswith("casilla-record:")
    assert re.fullmatch(r"casilla-record:[0-9a-f]{24}", record.id)
    assert not _PARSEABLE_CASILLA_RECORD_ID_RE.fullmatch(record.id)
    assert record.metadata.modelo == "303"
    assert record.metadata.casilla_id == records[0].casilla_id  # type: ignore[attr-defined]
    assert record.metadata.legal_refs  # provenance survived the funnel
    assert record.metadata.source_refs
    assert OutputLanguage.ES in record.descriptions


def test_segmented_casilla_funnels_with_opaque_id_and_canonical_metadata() -> None:
    """A segmented M200 casilla keeps ``casilla.id`` only in typed metadata."""
    from ..casilla_projection import project_modelo_casillas
    from ..unified_record import to_search_record

    projected = project_modelo_casillas(Modelo.M200)
    segmented = next(record for record in projected if record.casilla_id == "DP200014:00562")  # type: ignore[attr-defined]
    record = to_search_record(segmented)

    assert record.id.startswith("casilla-record:")
    assert not _PARSEABLE_CASILLA_RECORD_ID_RE.fullmatch(record.id)
    assert "DP200014:00562" not in record.id
    assert record.title == "Modelo 200 · casilla DP200014:00562"
    # The target deep-links to the per-modelo casilla reference page and the
    # casilla's page-local anchor (the id-folding slug), never the retired
    # search-for-itself query string. Both come from the ONE slug authority the
    # generator renders against.
    assert record.target == "_generated/casillas/200.html#casilla-dp200014-00562"
    assert record.metadata.modelo == "200"
    assert record.metadata.casilla_id == "DP200014:00562"
    assert record.metadata.number == "00562"
    assert record.metadata.segmento == "DP200014"


def test_legal_provision_funnels_to_a_search_record_with_provenance() -> None:
    """A real registry-backed legal projection funnels into the LEGAL kind."""
    from .._legal_projection import project_legal_search_records
    from ..search_record import SearchRecordKind
    from ..unified_record import SearchRecord, to_search_record

    legal = project_legal_search_records()[0]
    record = to_search_record(legal)

    assert isinstance(record, SearchRecord)
    assert record.kind is SearchRecordKind.LEGAL
    assert record.id == legal.record_id
    assert record.target == legal.target
    assert record.metadata.legal_id == legal.legal_id
    assert record.metadata.legal_permalink == legal.permalink
    assert record.metadata.legal_refs == (legal.legal_id,)
    assert OutputLanguage.ES in record.descriptions


def test_casilla_search_record_ids_are_opaque_and_unique() -> None:
    """Every projected casilla has a unique non-parseable search record id."""
    from ..casilla_projection import project_casilla_search_records
    from ..unified_record import to_search_record

    records, stats = project_casilla_search_records()
    unified = tuple(to_search_record(record) for record in records)
    ids = [record.id for record in unified]

    assert stats.deduplicated_records > 1000
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"casilla-record:[0-9a-f]{24}", record.id) for record in unified)
    assert all(not record.id.startswith("casilla:") for record in unified)


def test_cli_command_and_option_funnel_to_search_records() -> None:
    """CLI command and option records funnel into uniform SearchRecords."""
    from ..search_record import SearchRecordKind
    from ..unified_record import to_search_record

    command = to_search_record(_cli_command_record())
    assert command.kind is SearchRecordKind.CLI
    assert command.id == "cli:ledger.add"
    assert command.title == "aeat app ledger add"
    assert command.metadata.registry_key == "ledger.add"

    option = to_search_record(_cli_option_record())
    assert option.kind is SearchRecordKind.CLI
    assert option.id == "cli-option:aeat app ledger add:--amount"
    assert option.metadata.option_names == ("--amount",)


def test_all_kinds_serialise_to_the_same_shape() -> None:
    """Every kind serialises to the identical SearchRecord field set (homogeneous)."""
    from .._concept_cards import project_concept_cards
    from .._legal_projection import project_legal_search_records
    from ..casilla_projection import project_modelo_casillas
    from ..unified_record import SearchRecord, to_search_record

    cards, _ = project_concept_cards()
    casillas = project_modelo_casillas(Modelo.M303)
    legal = project_legal_search_records()[0]
    kinds = [
        to_search_record(cards[0]),
        to_search_record(casillas[0]),
        to_search_record(legal),
        to_search_record(_cli_command_record()),
        to_search_record(_cli_option_record()),
    ]
    expected_fields = set(SearchRecord.model_fields)
    for record in kinds:
        dumped = record.model_dump()
        assert set(dumped) == expected_fields
        assert dumped["id"]
        assert dumped["title"]
        assert dumped["target"]
        assert dumped["descriptions"]


def test_funnelled_records_are_json_serialisable() -> None:
    """The unified record serialises to JSON (the index-injection payload form)."""
    from .._concept_cards import project_concept_cards
    from ..unified_record import to_search_record

    cards, _ = project_concept_cards()
    record = to_search_record(cards[0])
    payload = record.model_dump_json()
    assert '"kind":' in payload
    assert '"target":' in payload


# ---------------------------------------------------------------------------
# Ranking weight normalisation across kinds
# ---------------------------------------------------------------------------


def test_base_weights_follow_the_declared_tier_ordering() -> None:
    """Concept > casilla > legal > CLI > page base weights (the per-class ladder).

    The per-kind view projects the one declared per-display-class table declared
    once for the shipped ranking: CONCEPT uses the general-fact ``DOC`` band, and
    it reverses the navigation-tier order to casilla > cli (previously cli >
    casilla), while a full-text PAGE hit collapses to the ``TECHNICAL`` floor.

    LEGAL is asserted explicitly because it is the one kind whose band was a
    hand-written alias onto ``DOC`` rather than a projection. That put every BOE
    article above the modelo and casilla cards it merely grounds, so the ordering
    below casilla is the contract, not an incidental value.
    """
    from ..search_record import SearchRecordKind
    from ..unified_record import kind_base_weight

    concept = kind_base_weight(SearchRecordKind.CONCEPT)
    cli = kind_base_weight(SearchRecordKind.CLI)
    casilla = kind_base_weight(SearchRecordKind.CASILLA)
    legal = kind_base_weight(SearchRecordKind.LEGAL)
    page = kind_base_weight(SearchRecordKind.PAGE)
    assert concept > casilla > legal > cli > page


def test_emitted_weight_matches_the_class_the_record_is_displayed_under() -> None:
    """A record's stamped weight must be the weight of its own display class.

    Each ``_from_*`` projector hard-codes the class literal it stamps a weight
    from, so nothing structurally ties that literal to the class
    ``derive_display_class`` later assigns the same record. A legal provision
    shipped as ``display_class=legal`` while carrying the ``DOC`` band's 1.0
    weight, so it was labelled correctly in the UI and still sorted above every
    modelo and casilla card -- the label and the sort order disagreed.

    Asserting the two agree on a real projected record catches that divergence
    for any kind, which a fixture built from an explicit display class cannot.
    """
    from .._legal_projection import project_legal_search_records
    from ..unified_record import (
        derive_display_class,
        display_class_base_weight,
        to_search_record,
    )

    record = to_search_record(project_legal_search_records()[0])
    displayed = derive_display_class(record)
    assert record.ranking_weight == display_class_base_weight(displayed), (
        f"the record is displayed as {displayed.value} but carries the "
        f"{record.ranking_weight} weight of a different band; the projector's "
        "hard-coded class literal has drifted from the derivation authority"
    )


def test_per_kind_projection_agrees_with_the_derivation_authority() -> None:
    """The two weight authorities must not disagree for any kind.

    ``_display_class_for`` decides the class of a record that reaches the reader;
    ``_KIND_TO_DISPLAY_CLASS`` decides the weight stamped during sweep-relevance
    reweighting. Both feed ``ranking_weight``, so a kind classed one way by the
    derivation and another by the projection ranks differently depending on which
    path built it -- which is exactly how LEGAL came to sit in the ``DOC`` band on
    one path while the ladder placed it below casilla on the other.

    CONCEPT and PAGE are excluded because their class genuinely depends on
    context the projection cannot see -- Handbook domain and target path. Both
    exclusions are declared behaviour, not drift: the projection deliberately
    floors a full-text hit. Every context-free kind must agree.
    """
    from ..search_record import SearchRecordKind
    from ..unified_record import (
        _KIND_TO_DISPLAY_CLASS,
        _display_class_for,
    )

    context_dependent = {SearchRecordKind.CONCEPT, SearchRecordKind.PAGE}
    checked = 0
    for kind, projected in _KIND_TO_DISPLAY_CLASS.items():
        if kind in context_dependent:
            continue
        checked += 1
        derived = _display_class_for(kind, None, "guides/overview.html")
        assert derived is projected, (
            f"{kind.value} is derived as {derived.value} but the per-kind "
            f"projection stamps {projected.value}; the two ranking authorities have drifted"
        )
    assert checked >= 3, "the agreement check covered almost nothing; a kind was dropped"


def test_normalisation_preserves_tier_ordering_under_score() -> None:
    """A weakly-scored concept never drops below a strongly-scored page.

    The normalisation modulates within ``[base*0.5, base]`` so the tier
    ordering survives any sweep score: the worst-scored concept still ranks at
    or above the best-scored page.
    """
    from ..search_record import SearchRecordKind
    from ..unified_record import normalise_ranking_weight

    worst_concept = normalise_ranking_weight(SearchRecordKind.CONCEPT, 0.0)
    best_page = normalise_ranking_weight(SearchRecordKind.PAGE, 1.0)
    assert worst_concept >= best_page


def test_normalisation_clamps_and_sorts_within_a_kind() -> None:
    """Within a kind, a higher sweep score yields a higher (clamped) weight."""
    from ..search_record import SearchRecordKind
    from ..unified_record import normalise_ranking_weight

    low = normalise_ranking_weight(SearchRecordKind.CASILLA, 0.1)
    high = normalise_ranking_weight(SearchRecordKind.CASILLA, 0.9)
    assert high > low
    # Out-of-range scores clamp into [0, 1] rather than escaping the band.
    over = normalise_ranking_weight(SearchRecordKind.CONCEPT, 5.0)
    assert over <= 1.0
    none_weight = normalise_ranking_weight(SearchRecordKind.CONCEPT, None)
    assert none_weight == 1.0


def test_search_record_is_frozen() -> None:
    """The strict-frozen contract on the unified record."""
    from pydantic import ValidationError

    from .._concept_cards import project_concept_cards
    from ..unified_record import to_search_record

    cards, _ = project_concept_cards()
    record = to_search_record(cards[0])
    with pytest.raises(ValidationError):
        record.title = "mutated"  # type: ignore[misc]
