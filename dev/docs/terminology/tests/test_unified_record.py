"""Real-behaviour conformance for the unified SearchRecord funnel (ADR D4/D6).

The four projected record kinds -- concept cards, casilla projections, CLI
surface/option records -- funnel through :func:`to_search_record` into one
homogeneous :class:`SearchRecord` shape (the Pagefind injection payload). These
gates prove the funnel produces a uniform record for every kind, carries the
four-language descriptions and grounding provenance, and that the ranking
weights are normalised onto one comparable cross-kind scale (ADR D5: term cards
first, navigation second, full text third).

No live CLI walk: the CLI records are constructed directly (their shape is the
contract under test, not their projection from the transiently-broken tree).
The concept and casilla records come from the real projections.
"""

from __future__ import annotations

import pytest

from aeat.core import Modelo
from aeat.core.external_constants import OutputLanguage

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_FOUR_LANGUAGES = frozenset(OutputLanguage)


def _cli_command_record() -> object:
    from dev.docs.terminology._cli_projection import CliSurfaceRecord
    from dev.docs.terminology._search_record import SearchRecordKind

    return CliSurfaceRecord(
        kind=SearchRecordKind.CLI,
        descriptions={OutputLanguage.ES: "Anade una transaccion", OutputLanguage.EN: "Add a transaction"},
        command_path="aeat app ledger add",
        registry_key="ledger.add",
        family="app",
        target="cli/app.html#aeat-app-ledger-add",
    )


def _cli_option_record() -> object:
    from dev.docs.terminology._cli_projection import CliOptionRecord
    from dev.docs.terminology._search_record import SearchRecordKind

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
    from dev.docs.terminology._concept_cards import project_concept_cards
    from dev.docs.terminology._search_record import SearchRecordKind
    from dev.docs.terminology._unified_record import SearchRecord, to_search_record

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
    from dev.docs.terminology._casilla_projection import project_modelo_casillas
    from dev.docs.terminology._search_record import SearchRecordKind
    from dev.docs.terminology._unified_record import to_search_record

    records = project_modelo_casillas(Modelo.M303)
    record = to_search_record(records[0])

    assert record.kind is SearchRecordKind.CASILLA
    assert record.id.startswith("casilla:303:")
    assert record.metadata.modelo == "303"
    assert record.metadata.legal_refs  # provenance survived the funnel
    assert record.metadata.source_refs
    assert OutputLanguage.ES in record.descriptions


def test_cli_command_and_option_funnel_to_search_records() -> None:
    """CLI command and option records funnel into uniform SearchRecords."""
    from dev.docs.terminology._search_record import SearchRecordKind
    from dev.docs.terminology._unified_record import to_search_record

    command = to_search_record(_cli_command_record())  # type: ignore[arg-type]
    assert command.kind is SearchRecordKind.CLI
    assert command.id == "cli:ledger.add"
    assert command.title == "aeat app ledger add"
    assert command.metadata.registry_key == "ledger.add"

    option = to_search_record(_cli_option_record())  # type: ignore[arg-type]
    assert option.kind is SearchRecordKind.CLI
    assert option.id == "cli-option:aeat app ledger add:--amount"
    assert option.metadata.option_names == ("--amount",)


def test_all_kinds_serialise_to_the_same_shape() -> None:
    """Every kind serialises to the identical SearchRecord field set (homogeneous)."""
    from dev.docs.terminology._casilla_projection import project_modelo_casillas
    from dev.docs.terminology._concept_cards import project_concept_cards
    from dev.docs.terminology._unified_record import SearchRecord, to_search_record

    cards, _ = project_concept_cards()
    casillas = project_modelo_casillas(Modelo.M303)
    kinds = [
        to_search_record(cards[0]),
        to_search_record(casillas[0]),
        to_search_record(_cli_command_record()),  # type: ignore[arg-type]
        to_search_record(_cli_option_record()),  # type: ignore[arg-type]
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
    from dev.docs.terminology._concept_cards import project_concept_cards
    from dev.docs.terminology._unified_record import to_search_record

    cards, _ = project_concept_cards()
    record = to_search_record(cards[0])
    payload = record.model_dump_json()
    assert '"kind":' in payload
    assert '"target":' in payload


# ---------------------------------------------------------------------------
# Ranking weight normalisation across kinds (ADR D5)
# ---------------------------------------------------------------------------


def test_base_weights_follow_the_d5_tier_ordering() -> None:
    """Concept > CLI > casilla > page base weights (term, nav, nav, fulltext)."""
    from dev.docs.terminology._search_record import SearchRecordKind
    from dev.docs.terminology._unified_record import kind_base_weight

    concept = kind_base_weight(SearchRecordKind.CONCEPT)
    cli = kind_base_weight(SearchRecordKind.CLI)
    casilla = kind_base_weight(SearchRecordKind.CASILLA)
    page = kind_base_weight(SearchRecordKind.PAGE)
    assert concept > cli > casilla > page


def test_normalisation_preserves_tier_ordering_under_score() -> None:
    """A weakly-scored concept never drops below a strongly-scored page.

    The normalisation modulates within ``[base*0.5, base]`` so the tier
    ordering survives any sweep score: the worst-scored concept still ranks at
    or above the best-scored page.
    """
    from dev.docs.terminology._search_record import SearchRecordKind
    from dev.docs.terminology._unified_record import normalise_ranking_weight

    worst_concept = normalise_ranking_weight(SearchRecordKind.CONCEPT, 0.0)
    best_page = normalise_ranking_weight(SearchRecordKind.PAGE, 1.0)
    assert worst_concept >= best_page


def test_normalisation_clamps_and_sorts_within_a_kind() -> None:
    """Within a kind, a higher sweep score yields a higher (clamped) weight."""
    from dev.docs.terminology._search_record import SearchRecordKind
    from dev.docs.terminology._unified_record import normalise_ranking_weight

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

    from dev.docs.terminology._concept_cards import project_concept_cards
    from dev.docs.terminology._unified_record import to_search_record

    cards, _ = project_concept_cards()
    record = to_search_record(cards[0])
    with pytest.raises(ValidationError):
        record.title = "mutated"  # type: ignore[misc]
