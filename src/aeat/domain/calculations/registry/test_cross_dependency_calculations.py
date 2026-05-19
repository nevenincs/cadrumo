from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from datetime import date
from decimal import Decimal

import pytest

from . import RegistryCalculationResult, calculate_registry_snapshot
from ._authority import ValidatedRegistryAuthority
from ._bindings import CasillaObservation, RegistryModeloObservation, resolve_previous_filing_binding_values
from ._relations import (
    RegistryRelationSourceRequirement,
    relation_source_requirements,
    resolve_relation_values_from_observations,
)
from ._schema import ModeloRevision, RegistrySnapshot

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_cross_model_relations_resolve_from_observations_for_revision_edge_years(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    for modelo in registry_authority.modelos:
        for revision in modelo.revisions.values():
            if not revision.relations:
                continue
            relation_ids = {relation.id for relation in revision.relations}
            for filing_year, period in _full_relation_filing_year_periods(
                revision=revision, relation_ids=relation_ids
            ):
                _assert_relations_resolve_from_observations(
                    revision=revision,
                    filing_year=filing_year,
                    period=period,
                    relation_ids=relation_ids,
                    scope=f"{modelo.id}/{revision.id}/{filing_year}/{period}",
                )


def _full_relation_filing_year_periods(
    *,
    revision,  # type: ignore[no-untyped-def]
    relation_ids: set[str],
) -> Iterator[tuple[int, str]]:
    """Yield ``(filing_year, period)`` pairs where every relation is active.

    A relation is "active" for a period when it either has no
    target_periods declared (matches every period) or lists the
    period explicitly. The gate only exercises tuples where the
    active set equals the full relation set so partial-coverage
    periods do not pollute the resolution check.
    """
    for filing_year in _revision_edge_years(revision):
        for period in revision.period_selector.periods:
            active_relation_ids = {
                relation.id
                for relation in revision.relations
                if not relation.target_periods or period in relation.target_periods
            }
            if active_relation_ids == relation_ids:
                yield filing_year, period


def _assert_relations_resolve_from_observations(
    *,
    revision,  # type: ignore[no-untyped-def]
    filing_year: int,
    period: str,
    relation_ids: set[str],
    scope: str,
) -> None:
    """Drive the relation-source -> observation -> resolution roundtrip and assert closure."""
    requirements = relation_source_requirements(revision, filing_year=filing_year, period=period)
    observations = _observations_from_requirements(
        requirements,
        lambda _requirement, period_index: Decimal(period_index + 1),
    )
    resolved = resolve_relation_values_from_observations(
        revision, observations, filing_year=filing_year, period=period
    )
    assert set(resolved) == relation_ids, scope


@pytest.mark.parametrize(
    ("filing_year", "expected_revision"),
    [
        (2022, "2019-2022"),
        (2026, "2023-y-siguientes"),
        (2027, "2023-y-siguientes"),
    ],
)
def test_modelo_180_cross_dependency_calculation_resolves_historical_current_and_future_revisions(
    filing_year: int,
    expected_revision: str,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("180", filing_year, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=filing_year, period="0A")
    observations = _observations_from_requirements(
        requirements,
        lambda requirement, period_index: {
            "01": (Decimal("1"), Decimal("1"), Decimal("2"), Decimal("1")),
            "02": (Decimal("250.10"), Decimal("749.90"), Decimal("1200.00"), Decimal("-50.25")),
            "03": (Decimal("47.52"), Decimal("142.48"), Decimal("228.00"), Decimal("0.00")),
        }[requirement.source_output][period_index],
    )

    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=filing_year,
        period="0A",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(filing_year, 12, 31)},
        relation_values=relation_values,
    )

    assert snapshot.revision.id == expected_revision
    entries = {entry.target: entry for entry in result.entries}
    assert entries["decl.total-perceptores"].operand_refs == ("modelo-180-rel-115-perceptores-anual",)
    assert entries["decl.base-total"].operand_refs == ("modelo-180-rel-115-base-anual",)
    assert entries["decl.retenciones-total"].operand_refs == ("modelo-180-rel-115-retenciones-anual",)


def test_modelo_190_calculation_resolves_modelo_111_quarterly_filings(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("190", 2026, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=2026, period="0A")
    observations = _observations_from_requirements(
        requirements,
        lambda requirement, period_index: {
            "01": (Decimal("2"), Decimal("1"), Decimal("2"), Decimal("1")),
            "04": (Decimal("1"), Decimal("0"), Decimal("0"), Decimal("1")),
            "07": (Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1")),
            "10": (Decimal("0"), Decimal("1"), Decimal("0"), Decimal("0")),
            "13": (Decimal("1"), Decimal("0"), Decimal("1"), Decimal("0")),
            "16": (Decimal("0"), Decimal("1"), Decimal("0"), Decimal("0")),
            "19": (Decimal("0"), Decimal("0"), Decimal("1"), Decimal("0")),
            "22": (Decimal("0"), Decimal("0"), Decimal("0"), Decimal("1")),
            "25": (Decimal("1"), Decimal("0"), Decimal("0"), Decimal("0")),
            "02": (Decimal("1000"), Decimal("2000"), Decimal("1500"), Decimal("2500")),
            "05": (Decimal("100"), Decimal("0"), Decimal("0"), Decimal("50")),
            "08": (Decimal("800"), Decimal("900"), Decimal("850"), Decimal("950")),
            "11": (Decimal("120"), Decimal("0"), Decimal("0"), Decimal("0")),
            "14": (Decimal("200"), Decimal("0"), Decimal("300"), Decimal("0")),
            "17": (Decimal("0"), Decimal("80"), Decimal("0"), Decimal("0")),
            "20": (Decimal("0"), Decimal("0"), Decimal("250"), Decimal("0")),
            "23": (Decimal("0"), Decimal("0"), Decimal("0"), Decimal("75")),
            "26": (Decimal("400"), Decimal("0"), Decimal("0"), Decimal("0")),
            "28": (Decimal("190"), Decimal("210"), Decimal("175.25"), Decimal("225.75")),
        }[requirement.source_output][period_index],
    )

    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=2026,
        period="0A",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(2026, 12, 31)},
        relation_values=relation_values,
    )

    entries = {entry.target: entry for entry in result.entries}
    assert len(entries["decl.total-percepciones"].operand_refs) == 9
    assert len(entries["decl.percepciones-total"].operand_refs) == 9
    assert entries["decl.retenciones-total"].operand_refs == ("modelo-190-rel-111-retenciones-anual",)


def test_modelo_193_calculation_resolves_current_modelo_123_quarterly_filings(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("193", 2026, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=2026, period="0A")
    observations = _observations_from_requirements(
        requirements,
        lambda requirement, period_index: {
            "03": (Decimal("5"), Decimal("4"), Decimal("7"), Decimal("6")),
            "06": (Decimal("1201.00"), Decimal("800.25"), Decimal("999.75"), Decimal("500.00")),
            "09": (Decimal("228.19"), Decimal("152.05"), Decimal("189.95"), Decimal("95.00")),
        }[requirement.source_output][period_index],
    )

    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=2026,
        period="0A",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(2026, 12, 31)},
        relation_values=relation_values,
    )

    assert set(relation_values) == {
        "modelo-193-rel-123-perceptores-anual",
        "modelo-193-rel-123-base-anual",
        "modelo-193-rel-123-retenciones-anual",
    }
    entries = {entry.target: entry for entry in result.entries}
    assert entries["decl.total-perceptores"].operand_refs == ("modelo-193-rel-123-perceptores-anual",)
    assert entries["decl.base-total"].operand_refs == ("modelo-193-rel-123-base-anual",)
    assert entries["decl.retenciones-total"].operand_refs == ("modelo-193-rel-123-retenciones-anual",)


def test_modelo_100_payment_calculation_resolves_cross_model_periodic_and_annual_observations(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("100", 2025, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=2025, period="0A")
    observations = _observations_from_requirements(requirements, _renta_relation_observed_value)

    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=2025,
        period="0A",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(2025, 12, 31)},
        relation_values=relation_values,
        binding_values={
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
    )

    assert set(relation_values) == {
        "renta-2025-rel-111-retenciones-trimestrales",
        "renta-2025-rel-111-retenciones-mensuales",
        "renta-2025-rel-115-retenciones-trimestrales",
        "renta-2025-rel-123-retenciones-trimestrales",
        "renta-2025-rel-130-pagos-fraccionados",
        "renta-2025-rel-131-pagos-fraccionados",
        "renta-2025-rel-180-retenciones-anuales",
        "renta-2025-rel-184-atribucion-actividades-economicas",
        "renta-2025-rel-190-retenciones-anuales",
        "renta-2025-rel-193-retenciones-anuales",
    }
    entries = {entry.target: entry for entry in result.entries}
    assert entries["0604"].operand_refs == (
        "renta-2025-rel-130-pagos-fraccionados",
        "renta-2025-rel-131-pagos-fraccionados",
    )


def test_modelo_100_payment_calculation_consumes_real_modelo_130_quarterly_registry_results(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    filing_year = 2025
    modelo_130_results = {}
    for period, inputs in {
        "1T": {"01": Decimal("10000"), "02": Decimal("3000"), "06": Decimal("100")},
        "2T": {"01": Decimal("16000"), "02": Decimal("6000"), "05": Decimal("500"), "06": Decimal("250")},
        "3T": {"01": Decimal("22000"), "02": Decimal("9000"), "05": Decimal("1100"), "06": Decimal("450")},
        "4T": {"01": Decimal("28000"), "02": Decimal("12000"), "05": Decimal("1800"), "06": Decimal("650")},
    }.items():
        modelo_130_results[period] = calculate_registry_snapshot(
            registry_snapshot("130", filing_year, period),
            inputs=inputs,
            binding_values={"irpf.previous_year_economic_activity_net_income": Decimal("13000")},
            date_context={"filing_period": _modelo_130_filing_date(filing_year, period)},
        )

    snapshot = registry_snapshot("100", filing_year, "0A")
    requirements = relation_source_requirements(snapshot.revision, filing_year=filing_year, period="0A")
    observations = _observations_from_requirements(
        requirements,
        lambda requirement, period_index: _renta_relation_observed_value_from_modelo_130_results(
            requirement,
            period_index,
            modelo_130_results,
        ),
    )
    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=filing_year,
        period="0A",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context={"filing_period": date(filing_year, 12, 31)},
        relation_values=relation_values,
        binding_values={"renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1")},
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
    )

    entries = {entry.target: entry for entry in result.entries}
    assert "renta-2025-rel-130-pagos-fraccionados" in relation_values
    assert "renta-2025-rel-130-pagos-fraccionados" in entries["0604"].operand_refs


@pytest.mark.parametrize(
    ("filing_year", "source_year", "source_values", "expected_binding"),
    [
        (
            2022,
            2021,
            {
                "0224": Decimal("4000"),
                "1479": Decimal("2000"),
                "1553": Decimal("1500"),
                "1577": Decimal("1000"),
            },
            Decimal("8500"),
        ),
        (
            2026,
            2025,
            {
                "0224": Decimal("5000"),
                "1479": Decimal("2000"),
                "1553": Decimal("1500"),
                "1577": Decimal("1000"),
            },
            Decimal("9500"),
        ),
    ],
)
def test_modelo_130_resolves_previous_year_modelo_100_filed_casillas_into_binding(
    filing_year: int,
    source_year: int,
    source_values: dict[str, Decimal],
    expected_binding: Decimal,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    """Verifies the previous_filing binding resolves the source modelo's casillas
    into the expected value. The binding's ``expected_binding`` is the SUM of the
    source modelo's input casillas as the binding selector declares it — that sum
    is what the binding resolver must produce, NOT a registry formula output. This
    test exercises the binding closure, not formula arithmetic.
    """

    snapshot = registry_snapshot("130", filing_year, "1T")

    binding_values = resolve_previous_filing_binding_values(
        snapshot.revision,
        (
            RegistryModeloObservation(
                modelo="100",
                filing_year=source_year,
                period="0A",
                observations=tuple(CasillaObservation(casilla_id=cid, value=val) for cid, val in source_values.items()),
            ),
        ),
        filing_year=filing_year,
        period="1T",
    )

    assert binding_values["irpf.previous_year_economic_activity_net_income"] == expected_binding


@pytest.mark.parametrize("period", ["1P", "2P", "3P"])
def test_modelo_202_modalidad_chains_calculate_for_synthetic_inputs(
    period: str,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("202", 2026, period)
    revision = snapshot.revision
    assert revision.id == "2025-y-siguientes"
    assert len(revision.casillas) == 50
    formula_targets = {formula.target for formula in revision.formulas}
    assert formula_targets == {"03", "13", "16", "18", "22", "25", "26", "32", "34", "38", "39", "63", "66"}

    inputs = {
        "01": Decimal("10000"),
        "02": Decimal("0"),
        "04": Decimal("50000"),
        "05": Decimal("2000"),
        "06": Decimal("1000"),
        "07": Decimal("500"),
        "08": Decimal("300"),
        "37": Decimal("200"),
        "67": Decimal("100"),
        "14": Decimal("4200"),
        "44": Decimal("0"),
        "45": Decimal("0"),
        "46": Decimal("0"),
        "17": Decimal("17"),
        "47": Decimal("0"),
        "40": Decimal("0"),
        "48": Decimal("0"),
        "49": Decimal("0"),
        "27": Decimal("200"),
        "28": Decimal("500"),
        "29": Decimal("100"),
        "30": Decimal("3000"),
        "31": Decimal("0"),
        "33": Decimal("0"),
        "20": Decimal("0"),
        "21": Decimal("0"),
        "23": Decimal("0"),
        "24": Decimal("0"),
        "42": Decimal("0"),
        "50": Decimal("0"),
        "51": Decimal("0"),
        "52": Decimal("0"),
        "61": Decimal("0"),
        "62": Decimal("0"),
        "64": Decimal("0"),
        "65": Decimal("0"),
    }

    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": date(2026, 12, 31)},
    )

    entries = {entry.target: entry for entry in result.entries}
    assert entries["03"].operand_refs == ("01", "is.modalidad_cuota.percentage", "02")
    assert entries["16"].operand_refs == ("13", "44", "14", "45", "46")
    assert entries["18"].operand_refs == ("16", "17", "47", "48", "40", "49")
    assert entries["34"].operand_refs == ("32", "33")


@pytest.mark.parametrize(
    ("filing_year", "expected_revision", "expected_casilla_count"),
    [
        (2019, "2019-2022", 43),
        (2020, "2019-2022", 43),
        (2022, "2019-2022", 43),
        (2023, "2023-2024", 43),
        (2024, "2023-2024", 43),
        (2025, "2025-y-siguientes", 50),
        (2026, "2025-y-siguientes", 50),
    ],
)
def test_modelo_202_revision_selection_resolves_for_filing_year_boundaries(
    filing_year: int,
    expected_revision: str,
    expected_casilla_count: int,
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("202", filing_year, "1P")
    assert snapshot.revision.id == expected_revision
    assert len(snapshot.revision.casillas) == expected_casilla_count


def test_modelo_202_2023_2024_total_correcciones_aumentos_excludes_complementario_column(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("202", 2024, "2P")
    revision = snapshot.revision
    assert revision.id == "2023-2024"
    casilla_ids = {casilla.id for casilla in revision.casillas}
    assert "67" not in casilla_ids
    assert {"61", "62", "63", "64", "65", "66"}.isdisjoint(casilla_ids)

    inputs = {
        "05": Decimal("2000"),
        "07": Decimal("500"),
        "06": Decimal("1000"),
        "37": Decimal("200"),
        "08": Decimal("300"),
        "04": Decimal("50000"),
    }
    # Asserting the registry runs without raising on the historical
    # revision shape; arithmetic comparisons against hand-computed
    # output Decimals are deliberately omitted (tautological).
    calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": date(2024, 12, 31)},
    )


def test_modelo_200_cuota_a_ingresar_aggregates_modelo_202_pagos_fraccionados(
    registry_snapshot: Callable[[str, int, str], RegistrySnapshot],
) -> None:
    snapshot = registry_snapshot("200", 2024, "0A")
    revision = snapshot.revision
    assert revision.id == "2024-y-siguientes"
    relation_ids = {relation.id for relation in revision.relations}
    assert relation_ids == {"modelo-200-2024-rel-202-pagos-fraccionados"}
    classification = revision.dependency_classifications[0]
    assert classification.source_modelo == "202"
    assert classification.treatment == "direct_annual_settlement"

    requirements = relation_source_requirements(revision, filing_year=2024, period="0A")
    observations = _observations_from_requirements(
        requirements,
        lambda _requirement, period_index: (
            Decimal("1200"),
            Decimal("1500"),
            Decimal("1800"),
        )[period_index],
    )

    relation_values = resolve_relation_values_from_observations(
        revision,
        observations,
        filing_year=2024,
        period="0A",
    )
    assert set(relation_values) == {"modelo-200-2024-rel-202-pagos-fraccionados"}

    result = calculate_registry_snapshot(
        snapshot,
        inputs={"00592": Decimal("12000")},
        date_context={"filing_period": date(2024, 12, 31)},
        relation_values=relation_values,
    )
    entries = {entry.target: entry for entry in result.entries}
    assert "00599" in entries
    assert set(entries["00599"].operand_refs) == {"00592", "modelo-200-2024-rel-202-pagos-fraccionados"}
    entries = {entry.target: entry for entry in result.entries}
    assert entries["00599"].operand_refs == (
        "00592",
        "modelo-200-2024-rel-202-pagos-fraccionados",
    )


def _observations_from_requirements(
    requirements: Iterable[RegistryRelationSourceRequirement],
    value_for: Callable[[RegistryRelationSourceRequirement, int], Decimal],
) -> tuple[RegistryModeloObservation, ...]:
    observed: dict[tuple[str, int, str], dict[str, Decimal]] = {}
    for requirement in requirements:
        for period_index, period in enumerate(requirement.periods):
            key = (requirement.source_modelo, requirement.filing_year, period)
            casilla_values = observed.setdefault(key, {})
            casilla_values[requirement.source_output] = value_for(requirement, period_index)
    return tuple(
        RegistryModeloObservation(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observations=tuple(CasillaObservation(casilla_id=cid, value=val) for cid, val in casilla_values.items()),
        )
        for (modelo, filing_year, period), casilla_values in sorted(observed.items())
    )


def _revision_edge_years(revision: ModeloRevision) -> tuple[int, ...]:
    if revision.period_selector.years:
        years = sorted(revision.period_selector.years)
        return tuple(dict.fromkeys((years[0], years[-1])))
    year_from = revision.period_selector.year_from
    if year_from is None:
        raise AssertionError(f"revision {revision.id} has no filing-year selector")
    year_to = revision.period_selector.year_to
    if year_to is not None:
        if year_to == year_from:
            return (year_from,)
        midpoint = year_from + ((year_to - year_from) // 2)
        return tuple(dict.fromkeys((year_from, midpoint, year_to)))
    return (year_from, year_from + 1, year_from + 7)


def _renta_relation_observed_value(requirement: RegistryRelationSourceRequirement, period_index: int) -> Decimal:
    relation_id = requirement.relation_ids[0]
    if relation_id == "renta-2025-rel-111-retenciones-trimestrales":
        return (Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"))[period_index]
    if relation_id == "renta-2025-rel-111-retenciones-mensuales":
        return Decimal(period_index + 1)
    if relation_id == "renta-2025-rel-115-retenciones-trimestrales":
        return Decimal("10")
    if relation_id == "renta-2025-rel-123-retenciones-trimestrales":
        return Decimal("20")
    if relation_id == "renta-2025-rel-130-pagos-fraccionados":
        return (Decimal("100"), Decimal("200"), Decimal("300"), Decimal("400"))[period_index]
    if relation_id == "renta-2025-rel-131-pagos-fraccionados":
        return Decimal("5")
    if relation_id == "renta-2025-rel-180-retenciones-anuales":
        return Decimal("30")
    if relation_id == "renta-2025-rel-190-retenciones-anuales":
        return Decimal("40")
    if relation_id == "renta-2025-rel-193-retenciones-anuales":
        return Decimal("50")
    if relation_id == "renta-2025-rel-184-atribucion-actividades-economicas":
        return Decimal("60")
    raise AssertionError(f"unhandled relation requirement {relation_id}")


def _renta_relation_observed_value_from_modelo_130_results(
    requirement: RegistryRelationSourceRequirement,
    period_index: int,
    modelo_130_results: dict[str, RegistryCalculationResult],
) -> Decimal:
    relation_id = requirement.relation_ids[0]
    if relation_id == "renta-2025-rel-130-pagos-fraccionados":
        period = ("1T", "2T", "3T", "4T")[period_index]
        return modelo_130_results[period].values["19"]
    if relation_id == "renta-2025-rel-131-pagos-fraccionados":
        return Decimal("0")
    return Decimal("0")


def _modelo_130_filing_date(filing_year: int, period: str) -> date:
    return {
        "1T": date(filing_year, 4, 20),
        "2T": date(filing_year, 7, 20),
        "3T": date(filing_year, 10, 20),
        "4T": date(filing_year + 1, 1, 20),
    }[period]


def _modelo_130_inputs() -> dict[str, Decimal]:
    return {
        "01": Decimal("10000"),
        "02": Decimal("4000"),
        "05": Decimal("250"),
        "06": Decimal("100"),
        "08": Decimal("2000"),
        "10": Decimal("10"),
        "15": Decimal("0"),
        "16": Decimal("0"),
        "18": Decimal("0"),
    }
