"""Modelo 130 registry behaviour for direct-estimation instalment filings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import (
    RegistryValidationError,
    build_snapshot,
    calculate_registry_snapshot,
    load_registry_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"
_REQUIRED_SURFACES = {
    "approval",
    "calculation",
    "deadline",
    "export",
    "extractor",
    "filing",
    "portal",
    "reconciliation",
    "review",
    "verification",
    "workflow",
}


def _load_modelo(modelo_id: str):
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == modelo_id)
    return modelo, catalogues


@pytest.fixture(scope="module")
def modelo_130_registry():
    return _load_modelo("130")


def _snapshot_130(modelo_130_registry):
    modelo, catalogues = modelo_130_registry
    return build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2026,
        period="1T",
    )


def test_modelo_130_validated_snapshot_owns_workflow_surfaces(modelo_130_registry) -> None:
    modelo, catalogues = modelo_130_registry
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2026,
        period="1T",
    )

    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert set(linked_by_surface) >= _REQUIRED_SURFACES
    assert all(link.requires_snapshot for link in linked_by_surface.values())


def test_modelo_130_current_revision_calculates_direct_estimation_result(modelo_130_registry) -> None:
    result = calculate_registry_snapshot(
        _snapshot_130(modelo_130_registry),
        inputs={
            "01": Decimal("10000.00"),
            "02": Decimal("4000.00"),
            "05": Decimal("100.00"),
            "06": Decimal("50.00"),
            "08": Decimal("5000.00"),
            "10": Decimal("20.00"),
            "15": Decimal("20.00"),
            "16": Decimal("5.00"),
            "18": Decimal("100.00"),
        },
        binding_values={"irpf.previous_year_economic_activity_net_income": Decimal("9500.00")},
        date_context={"filing_period": date(2026, 4, 20)},
    )

    assert result.values["03"] == Decimal("6000.00")
    assert result.values["04"] == Decimal("1200.00")
    assert result.values["07"] == Decimal("1050.00")
    assert result.values["09"] == Decimal("100.00")
    assert result.values["11"] == Decimal("80.00")
    assert result.values["12"] == Decimal("1130.00")
    assert result.values["13"] == Decimal("75.00")
    assert result.values["14"] == Decimal("1055.00")
    assert result.values["17"] == Decimal("1030.00")
    assert result.values["19"] == Decimal("930.00")
    assert {entry.target for entry in result.entries} == {"03", "04", "07", "09", "11", "12", "13", "14", "17", "19"}


def test_modelo_130_requires_external_previous_year_income_binding_for_minoracion(modelo_130_registry) -> None:
    with pytest.raises(RegistryValidationError, match="previous_year_economic_activity_net_income"):
        calculate_registry_snapshot(
            _snapshot_130(modelo_130_registry),
            inputs={"01": Decimal("12000.00"), "02": Decimal("4000.00")},
            date_context={"filing_period": date(2026, 4, 20)},
        )
