"""Modelo 131 registry behaviour for objective-estimation instalment filings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import build_snapshot, calculate_registry_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"
_COMMON_SURFACES = {
    "approval",
    "calculation",
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
def modelo_131_registry():
    return _load_modelo("131")


@pytest.mark.parametrize(
    ("filing_year", "required_surfaces"),
    [
        (2023, _COMMON_SURFACES),
        (2024, _COMMON_SURFACES),
        (2025, _COMMON_SURFACES),
        (2026, _COMMON_SURFACES | {"deadline"}),
    ],
)
def test_modelo_131_validated_snapshot_owns_workflow_surfaces(
    modelo_131_registry,
    filing_year: int,
    required_surfaces: set[str],
) -> None:
    modelo, catalogues = modelo_131_registry
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=filing_year,
        period="1T",
    )

    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert set(linked_by_surface) >= required_surfaces
    assert all(link.requires_snapshot for link in linked_by_surface.values())


@pytest.mark.parametrize("filing_year", [2023, 2024, 2025, 2026])
def test_modelo_131_calculates_objective_estimation_result_for_supported_revisions(
    modelo_131_registry,
    filing_year: int,
) -> None:
    modelo, catalogues = modelo_131_registry
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=filing_year,
        period="1T",
    )

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "02": Decimal("50.00"),
            "03": Decimal("3000.00"),
            "05": Decimal("7000.00"),
            "08": Decimal("20.00"),
            "09": Decimal("5.00"),
            "11": Decimal("10.00"),
            "12": Decimal("15.00"),
            "14": Decimal("40.00"),
        },
        date_context={"filing_period": date(filing_year, 4, 20)},
    )

    assert result.values["04"] == Decimal("60.00")
    assert result.values["06"] == Decimal("140.00")
    assert result.values["07"] == Decimal("250.00")
    assert result.values["10"] == Decimal("225.00")
    assert result.values["13"] == Decimal("200.00")
    assert result.values["15"] == Decimal("160.00")
    assert {entry.target for entry in result.entries} == {"04", "06", "07", "10", "13", "15"}
