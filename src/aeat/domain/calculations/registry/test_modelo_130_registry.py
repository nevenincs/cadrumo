"""Modelo 130 registry behaviour for direct-estimation instalment filings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.resources import bundled_path

from . import (
    RegistryValidationError,
    build_snapshot,
    calculate_registry_snapshot,
    load_registry_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
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
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )


def test_modelo_130_validated_snapshot_owns_workflow_surfaces(modelo_130_registry) -> None:
    modelo, catalogues = modelo_130_registry
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )

    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert set(linked_by_surface) >= _REQUIRED_SURFACES
    assert all(link.requires_snapshot for link in linked_by_surface.values())


def test_modelo_130_requires_external_previous_year_income_binding_for_minoracion(modelo_130_registry) -> None:
    with pytest.raises(RegistryValidationError, match="previous_year_economic_activity_net_income"):
        calculate_registry_snapshot(
            _snapshot_130(modelo_130_registry),
            inputs={"01": Decimal("12000.00"), "02": Decimal("4000.00")},
            date_context={"filing_period": date(2026, 4, 20)},
            binding_values={"modelo-130-resultados-negativos-anteriores": Decimal("0")},
        )
