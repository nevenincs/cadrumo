from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date
from decimal import Decimal

import pytest

from ....core.paths import PROJECT_ROOT
from . import build_snapshot, calculate_registry_snapshot, load_registry_tree
from ._bindings import RegistryFilingObservation, resolve_previous_filing_binding_values
from ._relations import (
    RegistryRelationSourceRequirement,
    relation_source_requirements,
    resolve_relation_values_from_observations,
)
from ._schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"


def test_cross_model_relations_resolve_from_observations_for_revision_edge_years() -> None:
    modelos, _catalogues = load_registry_tree(_REGISTRY_ROOT)

    for modelo in modelos:
        for revision in modelo.revisions.values():
            if not revision.relations:
                continue
            relation_ids = {relation.id for relation in revision.relations}
            for filing_year in _revision_edge_years(revision):
                for period in revision.period_selector.periods:
                    active_relation_ids = {
                        relation.id
                        for relation in revision.relations
                        if not relation.target_periods or period in relation.target_periods
                    }
                    if active_relation_ids != relation_ids:
                        continue
                    requirements = relation_source_requirements(
                        revision,
                        filing_year=filing_year,
                        period=period,
                    )
                    observations = _observations_from_requirements(
                        requirements,
                        lambda _requirement, period_index: Decimal(period_index + 1),
                    )

                    resolved = resolve_relation_values_from_observations(
                        revision,
                        observations,
                        filing_year=filing_year,
                        period=period,
                    )

                    assert set(resolved) == relation_ids, f"{modelo.id}/{revision.id}/{filing_year}/{period}"


@pytest.mark.parametrize(
    ("filing_year", "expected_revision"),
    [
        (2022, "2014-2022"),
        (2026, "2023-y-siguientes"),
        (2027, "2023-y-siguientes"),
    ],
)
def test_modelo_180_cross_dependency_calculation_resolves_historical_current_and_future_revisions(
    filing_year: int,
    expected_revision: str,
) -> None:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == "180")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=filing_year,
        period="0A",
    )
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
    assert result.values["decl.total-perceptores"] == Decimal("5")
    assert result.values["decl.base-total"] == Decimal("2149.75")
    assert result.values["decl.retenciones-total"] == Decimal("418.00")
    entries = {entry.target: entry for entry in result.entries}
    assert entries["decl.total-perceptores"].operand_refs == ("modelo-180-rel-115-perceptores-anual",)
    assert entries["decl.base-total"].operand_refs == ("modelo-180-rel-115-base-anual",)
    assert entries["decl.retenciones-total"].operand_refs == ("modelo-180-rel-115-retenciones-anual",)


def test_modelo_100_payment_calculation_resolves_cross_model_periodic_and_annual_observations() -> None:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == "100")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2025,
        period="0A",
    )
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
        binding_values={"renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1")},
    )

    assert relation_values["renta-2025-rel-111-retenciones-trimestrales"] == Decimal("10")
    assert relation_values["renta-2025-rel-111-retenciones-mensuales"] == Decimal("78")
    assert relation_values["renta-2025-rel-115-retenciones-trimestrales"] == Decimal("40")
    assert relation_values["renta-2025-rel-123-retenciones-trimestrales"] == Decimal("80")
    assert relation_values["renta-2025-rel-130-pagos-fraccionados"] == Decimal("1000")
    assert relation_values["renta-2025-rel-131-pagos-fraccionados"] == Decimal("20")
    assert relation_values["renta-2025-rel-180-retenciones-anuales"] == Decimal("30")
    assert result.values["0604"] == Decimal("1020.00")
    assert result.values["0609"] == Decimal("1020.00")
    entries = {entry.target: entry for entry in result.entries}
    assert entries["0604"].operand_refs == (
        "renta-2025-rel-130-pagos-fraccionados",
        "renta-2025-rel-131-pagos-fraccionados",
    )


@pytest.mark.parametrize(
    ("filing_year", "source_year", "source_values", "expected_binding", "expected_minoracion", "expected_result"),
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
            Decimal("100.00"),
            Decimal("780.00"),
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
            Decimal("75.00"),
            Decimal("805.00"),
        ),
    ],
)
def test_modelo_130_calculation_resolves_previous_year_modelo_100_filed_casillas(
    filing_year: int,
    source_year: int,
    source_values: dict[str, Decimal],
    expected_binding: Decimal,
    expected_minoracion: Decimal,
    expected_result: Decimal,
) -> None:
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == "130")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=filing_year,
        period="1T",
    )

    binding_values = resolve_previous_filing_binding_values(
        snapshot.revision,
        (
            RegistryFilingObservation(
                modelo="100",
                filing_year=source_year,
                period="0A",
                casilla_values=source_values,
            ),
        ),
        filing_year=filing_year,
        period="1T",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs=_modelo_130_inputs(),
        date_context={"filing_period": date(filing_year, 3, 31)},
        binding_values=binding_values,
    )

    assert binding_values["irpf.previous_year_economic_activity_net_income"] == expected_binding
    assert result.values["13"] == expected_minoracion
    assert result.values["14"] == expected_result
    assert result.values["19"] == expected_result


def _observations_from_requirements(
    requirements: Iterable[RegistryRelationSourceRequirement],
    value_for: Callable[[RegistryRelationSourceRequirement, int], Decimal],
) -> tuple[RegistryFilingObservation, ...]:
    observed: dict[tuple[str, int, str], dict[str, Decimal]] = {}
    for requirement in requirements:
        for period_index, period in enumerate(requirement.periods):
            key = (requirement.source_modelo, requirement.filing_year, period)
            casilla_values = observed.setdefault(key, {})
            casilla_values[requirement.source_output] = value_for(requirement, period_index)
    return tuple(
        RegistryFilingObservation(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            casilla_values=casilla_values,
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
    raise AssertionError(f"unhandled relation requirement {relation_id}")


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
