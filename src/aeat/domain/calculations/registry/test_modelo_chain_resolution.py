"""End-to-end calculation tests for the canonical feeder→summary chains.

Where ``test_modelo_chain_cohesion.py`` asserts the relations are
declared and shape-correct, this module exercises the actual data
flow: build synthetic source filings for the feeder modelo across
the periods of a year, run the receiver's relations against them,
and assert every relation resolves to the expected aggregate.

Each chain test pins a deterministic set of feeder-period values so
the aggregate is known exactly. Failures point at registry drift in
the relation's aggregation, source/target periods, or selector.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from ._bindings import RegistryFilingObservation
from ._loader import load_registry_tree
from ._relations import resolve_relation_values_from_observations
from ._schema import ModeloDefinition, ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"


def _modelo(modelo_id: str) -> ModeloDefinition:
    modelos, _ = load_registry_tree(_REGISTRY_ROOT)
    return next(m for m in modelos if m.id == modelo_id)


def _revision(modelo_id: str, revision_id: str) -> ModeloRevision:
    return _modelo(modelo_id).revisions[revision_id]


def _quarterly_filings(
    modelo_id: str, filing_year: int, casilla_quarters: dict[str, dict[str, Decimal]]
) -> tuple[RegistryFilingObservation, ...]:
    """Build one ``RegistryFilingObservation`` per quarter from a per-quarter casilla map.

    ``casilla_quarters`` is keyed by casilla id; each entry maps period to
    the value the synthetic feeder filing reported for that casilla in
    that quarter. The helper inverts the mapping into one observation
    per period covering all referenced casillas.
    """

    periods = {"1T", "2T", "3T", "4T"}
    by_period: dict[str, dict[str, Decimal]] = {p: {} for p in periods}
    for casilla_id, quarter_values in casilla_quarters.items():
        for period, value in quarter_values.items():
            by_period[period][casilla_id] = value
    return tuple(
        RegistryFilingObservation(
            modelo=modelo_id,
            filing_year=filing_year,
            period=period,
            casilla_values=values,
        )
        for period, values in by_period.items()
    )


def _zero_quarters() -> dict[str, Decimal]:
    return {p: Decimal("0") for p in ("1T", "2T", "3T", "4T")}


def test_modelo_190_aggregates_modelo_111_quarterly_outputs_into_annual_summary() -> None:
    """190's relations must sum each 111 quarterly casilla into the matching annual binding."""

    revision = _revision("190", "2025-y-siguientes")
    # 190 declares 19 relations sourcing 111 casillas: perceptores
    # (01,04,07,10,13,16,19,22,25), importes (02,05,08,11,14,17,20,23,26),
    # and total retenciones (28). Build a full per-quarter map so every
    # relation has a value to aggregate. Casillas under test pin specific
    # values; the rest stay zero.
    casilla_quarters: dict[str, dict[str, Decimal]] = {}
    for casilla_id in (
        "01",
        "02",
        "04",
        "05",
        "07",
        "08",
        "10",
        "11",
        "13",
        "14",
        "16",
        "17",
        "19",
        "20",
        "22",
        "23",
        "25",
        "26",
        "28",
    ):
        casilla_quarters[casilla_id] = _zero_quarters()
    casilla_quarters["01"] = {"1T": Decimal("3"), "2T": Decimal("3"), "3T": Decimal("4"), "4T": Decimal("4")}
    casilla_quarters["02"] = {
        "1T": Decimal("12000.50"),
        "2T": Decimal("12500.00"),
        "3T": Decimal("12500.00"),
        "4T": Decimal("12999.50"),
    }
    casilla_quarters["28"] = {
        "1T": Decimal("2400.10"),
        "2T": Decimal("2500.00"),
        "3T": Decimal("2500.00"),
        "4T": Decimal("2599.90"),
    }
    observations = _quarterly_filings("111", 2026, casilla_quarters)

    values = resolve_relation_values_from_observations(revision, observations, filing_year=2026, period="0A")

    assert values["modelo-190-rel-111-trabajo-dinerario-percepciones-anual"] == Decimal("14")
    assert values["modelo-190-rel-111-trabajo-dinerario-importe-anual"] == Decimal("50000.00")
    assert values["modelo-190-rel-111-retenciones-anual"] == Decimal("10000.00")
    # Untouched casillas (04, 05, ...) stay zero through aggregation.
    assert values["modelo-190-rel-111-trabajo-especie-percepciones-anual"] == Decimal("0")
    assert values["modelo-190-rel-111-derechos-imagen-importe-anual"] == Decimal("0")


def test_modelo_193_aggregates_modelo_123_quarterly_outputs_into_annual_summary() -> None:
    """193's three relations sum 123's quarterly perceptores / base / retenciones casillas."""

    revision = _revision("193", "2024-y-siguientes")
    casilla_quarters = {
        # casilla 03: perceptores capital mobiliario dinerario
        "03": {"1T": Decimal("2"), "2T": Decimal("3"), "3T": Decimal("3"), "4T": Decimal("4")},
        # casilla 06: base de retenciones dineraria
        "06": {
            "1T": Decimal("1000.00"),
            "2T": Decimal("1500.00"),
            "3T": Decimal("2000.00"),
            "4T": Decimal("2500.50"),
        },
        # casilla 09: retenciones e ingresos a cuenta dineraria
        "09": {
            "1T": Decimal("190.00"),
            "2T": Decimal("285.00"),
            "3T": Decimal("380.00"),
            "4T": Decimal("475.10"),
        },
    }
    observations = _quarterly_filings("123", 2026, casilla_quarters)

    values = resolve_relation_values_from_observations(revision, observations, filing_year=2026, period="0A")

    assert values["modelo-193-rel-123-perceptores-anual"] == Decimal("12")
    assert values["modelo-193-rel-123-base-anual"] == Decimal("7000.50")
    assert values["modelo-193-rel-123-retenciones-anual"] == Decimal("1330.10")


def test_chain_resolution_returns_empty_under_non_aggregating_period() -> None:
    """Calling resolve under a period the receiver does not aggregate yields nothing.

    Modelo 190's relations all target ``0A``. Asking for ``1T`` exercises
    the period-filter path and produces no requirements, so the resolver
    short-circuits to an empty mapping without demanding observations.
    """

    revision = _revision("190", "2025-y-siguientes")
    values = resolve_relation_values_from_observations(revision, (), filing_year=2026, period="1T")
    assert values == {}


def test_chain_resolution_obeys_target_period_under_non_annual_call() -> None:
    """Calling the resolver with a non-annual period must not aggregate the annual relations."""

    revision = _revision("190", "2025-y-siguientes")
    # Even with full quarterly observations, asking for period "1T" must
    # return nothing — the receiver's relations all target "0A".
    casilla_quarters = {
        "01": {"1T": Decimal("1"), "2T": Decimal("1"), "3T": Decimal("1"), "4T": Decimal("1")},
    }
    observations = _quarterly_filings("111", 2026, casilla_quarters)

    values = resolve_relation_values_from_observations(revision, observations, filing_year=2026, period="1T")

    assert values == {}
