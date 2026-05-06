"""Modelo 111 registry behaviour for withholding filings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import build_snapshot, calculate_registry_snapshot, load_registry_tree

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
def modelo_111_registry():
    return _load_modelo("111")


@pytest.mark.parametrize("period", ["1T", "01"])
def test_modelo_111_validated_snapshot_owns_workflow_surfaces(modelo_111_registry, period: str) -> None:
    modelo, catalogues = modelo_111_registry
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2026,
        period=period,
    )

    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert set(linked_by_surface) >= _REQUIRED_SURFACES
    assert all(link.requires_snapshot for link in linked_by_surface.values())


def test_modelo_111_current_revision_calculates_withholding_totals(modelo_111_registry) -> None:
    modelo, catalogues = modelo_111_registry
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2026,
        period="1T",
    )

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "03": Decimal("10.00"),
            "06": Decimal("20.00"),
            "09": Decimal("30.00"),
            "12": Decimal("40.00"),
            "15": Decimal("50.00"),
            "18": Decimal("60.00"),
            "21": Decimal("70.00"),
            "24": Decimal("80.00"),
            "27": Decimal("90.00"),
            "29": Decimal("55.55"),
        },
        date_context={"filing_period": date(2026, 4, 20)},
    )

    assert result.values["28"] == Decimal("450.00")
    assert result.values["30"] == Decimal("394.45")
    assert {entry.target for entry in result.entries} == {"28", "30"}
