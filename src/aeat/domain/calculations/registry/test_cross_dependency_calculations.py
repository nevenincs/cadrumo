from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date
from decimal import Decimal

import pytest

from ....core.paths import PROJECT_ROOT
from . import build_snapshot, calculate_registry_snapshot, load_registry_tree
from ._bindings import RegistryFilingObservation
from ._relations import (
    RegistryRelationSourceRequirement,
    relation_source_requirements,
    resolve_relation_values_from_observations,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"


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
