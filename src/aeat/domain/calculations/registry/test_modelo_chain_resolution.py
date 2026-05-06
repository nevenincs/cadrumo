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


def test_modelo_100_aggregates_full_irpf_chain_into_annual_settlement() -> None:
    """Modelo 100 receives from five periodic feeders plus three annual rollups.

    The renta 2025 revision declares nine relations:
    - 130 / 131 quarterly pagos fraccionados (instalment_to_final_settlement)
    - 111 quarterly retenciones (factual_evidence) and 111 monthly retenciones
      (factual_evidence — same target binding; the taxpayer files quarterly OR
      monthly, never both)
    - 115 / 123 quarterly retenciones (factual_evidence)
    - 180 / 190 / 193 annual retenciones rollup (copy from period 0A)

    To resolve the full set every relation's source period must be observed.
    The test provides quarterly observations for all quarterly feeders, twelve
    monthly observations for 111 (zeroed — the taxpayer is on the quarterly
    rhythm), and one annual observation per annual rollup.
    """

    revision = _revision("100", "2025")
    observations: list[RegistryFilingObservation] = []
    # 100 revision 2025's source_revision_selector pins source observations to
    # tax year 2025; modelo 100 itself is filed in calendar year 2026 for that
    # tax year. Source filings carry filing_year=2025; the resolution call
    # passes filing_year=2026.
    source_year = 2025

    # 130 quarterly pagos fraccionados (estimacion directa): casilla 19.
    for period, value in zip(
        ("1T", "2T", "3T", "4T"),
        (Decimal("800.00"), Decimal("800.00"), Decimal("800.00"), Decimal("800.00")),
        strict=True,
    ):
        observations.append(
            RegistryFilingObservation(
                modelo="130", filing_year=source_year, period=period, casilla_values={"19": value}
            )
        )

    # 131 quarterly pagos fraccionados (estimacion objetiva): casilla 15.
    for period, value in zip(
        ("1T", "2T", "3T", "4T"),
        (Decimal("500.00"), Decimal("500.00"), Decimal("500.00"), Decimal("500.00")),
        strict=True,
    ):
        observations.append(
            RegistryFilingObservation(
                modelo="131", filing_year=source_year, period=period, casilla_values={"15": value}
            )
        )

    # 111 quarterly retenciones: casilla 28.
    for period, value in zip(
        ("1T", "2T", "3T", "4T"),
        (Decimal("3000.00"), Decimal("3000.00"), Decimal("3000.00"), Decimal("3000.00")),
        strict=True,
    ):
        observations.append(
            RegistryFilingObservation(
                modelo="111", filing_year=source_year, period=period, casilla_values={"28": value}
            )
        )

    # 111 monthly retenciones: zeroed, since the taxpayer is on the quarterly rhythm.
    for month in (f"{n:02d}" for n in range(1, 13)):
        observations.append(
            RegistryFilingObservation(
                modelo="111", filing_year=source_year, period=month, casilla_values={"28": Decimal("0")}
            )
        )

    # 115 quarterly retenciones (rental): casilla 03.
    for period, value in zip(
        ("1T", "2T", "3T", "4T"),
        (Decimal("100.00"), Decimal("100.00"), Decimal("100.00"), Decimal("100.00")),
        strict=True,
    ):
        observations.append(
            RegistryFilingObservation(
                modelo="115", filing_year=source_year, period=period, casilla_values={"03": value}
            )
        )

    # 123 quarterly retenciones (capital mobiliario): casilla 09.
    for period, value in zip(
        ("1T", "2T", "3T", "4T"),
        (Decimal("50.00"), Decimal("50.00"), Decimal("50.00"), Decimal("50.00")),
        strict=True,
    ):
        observations.append(
            RegistryFilingObservation(
                modelo="123", filing_year=source_year, period=period, casilla_values={"09": value}
            )
        )

    # 180 / 190 / 193 annual retenciones rollups: each provides one 0A observation
    # of decl.retenciones-total under the 2025 source year.
    observations.append(
        RegistryFilingObservation(
            modelo="180",
            filing_year=source_year,
            period="0A",
            casilla_values={"decl.retenciones-total": Decimal("400.00")},
        )
    )
    observations.append(
        RegistryFilingObservation(
            modelo="190",
            filing_year=source_year,
            period="0A",
            casilla_values={"decl.retenciones-total": Decimal("12000.00")},
        )
    )
    observations.append(
        RegistryFilingObservation(
            modelo="193",
            filing_year=source_year,
            period="0A",
            casilla_values={"decl.retenciones-total": Decimal("200.00")},
        )
    )

    values = resolve_relation_values_from_observations(revision, tuple(observations), filing_year=2026, period="0A")

    # Pagos fraccionados sum across four quarters.
    assert values["renta-2025-rel-130-pagos-fraccionados"] == Decimal("3200.00")
    assert values["renta-2025-rel-131-pagos-fraccionados"] == Decimal("2000.00")

    # Quarterly retenciones sums.
    assert values["renta-2025-rel-111-retenciones-trimestrales"] == Decimal("12000.00")
    assert values["renta-2025-rel-115-retenciones-trimestrales"] == Decimal("400.00")
    assert values["renta-2025-rel-123-retenciones-trimestrales"] == Decimal("200.00")

    # Monthly retenciones path is zeroed because the taxpayer files quarterly.
    assert values["renta-2025-rel-111-retenciones-mensuales"] == Decimal("0")

    # Annual rollups copy the source casilla directly.
    assert values["renta-2025-rel-180-retenciones-anuales"] == Decimal("400.00")
    assert values["renta-2025-rel-190-retenciones-anuales"] == Decimal("12000.00")
    assert values["renta-2025-rel-193-retenciones-anuales"] == Decimal("200.00")


def test_modelo_200_aggregates_modelo_202_pagos_fraccionados_into_annual_settlement() -> None:
    """200's instalment_to_final_settlement relation sums 202's three pagos fraccionados.

    IS pago fraccionado uses period codes ``1P`` / ``2P`` / ``3P``
    (April, October, December) rather than the quarterly ``1T``-``4T``
    codes used by IRPF / IVA / withholdings. The receiver's relation
    declares those three explicitly.
    """

    revision = _revision("200", "2024-y-siguientes")
    pagos_periods = ("1P", "2P", "3P")
    pagos_values = (Decimal("1500.00"), Decimal("2000.00"), Decimal("2500.50"))
    observations = tuple(
        RegistryFilingObservation(
            modelo="202",
            filing_year=2026,
            period=period,
            casilla_values={"34": value},
        )
        for period, value in zip(pagos_periods, pagos_values, strict=True)
    )

    values = resolve_relation_values_from_observations(revision, observations, filing_year=2026, period="0A")

    assert values["modelo-200-2024-rel-202-pagos-fraccionados"] == Decimal("6000.50")
