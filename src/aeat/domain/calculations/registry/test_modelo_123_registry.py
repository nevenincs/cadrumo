"""Modelo 123 registry behaviour for quarterly capital-income withholding filings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from . import RegistryValidator, build_snapshot, calculate_registry_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"


def _load_modelo(modelo_id: str):
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == modelo_id)
    return modelo, catalogues


@pytest.mark.parametrize(
    ("filing_year", "required_surfaces"),
    [
        (
            2023,
            {
                "calculation",
                "filing",
                "export",
                "verification",
                "review",
                "approval",
                "reconciliation",
                "extractor",
                "portal",
                "workflow",
            },
        ),
        (
            2026,
            {
                "calculation",
                "filing",
                "export",
                "verification",
                "review",
                "approval",
                "reconciliation",
                "extractor",
                "portal",
                "deadline",
                "workflow",
            },
        ),
    ],
)
def test_modelo_123_validated_snapshot_owns_workflow_surfaces(
    filing_year: int,
    required_surfaces: set[str],
) -> None:
    modelo, catalogues = _load_modelo("123")

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)
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
    assert required_surfaces <= set(linked_by_surface)
    assert all(link.requires_snapshot for link in linked_by_surface.values())


def test_modelo_123_current_revision_calculates_all_registry_totals() -> None:
    modelo, catalogues = _load_modelo("123")
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
            "01": Decimal("2"),
            "02": Decimal("3"),
            "04": Decimal("100.00"),
            "05": Decimal("25.00"),
            "07": Decimal("19.00"),
            "08": Decimal("5.00"),
            "10": Decimal("0.00"),
            "11": Decimal("2.00"),
            "13": Decimal("1.00"),
        },
        date_context={"filing_period": date(2026, 4, 20)},
    )

    assert result.values["03"] == Decimal("5")
    assert result.values["06"] == Decimal("125.00")
    assert result.values["09"] == Decimal("24.00")
    assert result.values["12"] == Decimal("26.00")
    assert result.values["14"] == Decimal("25.00")
    assert {entry.target for entry in result.entries} == {"03", "06", "09", "12", "14"}


def test_modelo_123_historical_revision_calculates_prior_layout_totals() -> None:
    modelo, catalogues = _load_modelo("123")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2023,
        period="1T",
    )

    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            "01": Decimal("2"),
            "02": Decimal("100.00"),
            "03": Decimal("19.00"),
            "04": Decimal("0.00"),
            "05": Decimal("2.00"),
            "07": Decimal("1.00"),
        },
        date_context={"filing_period": date(2023, 4, 20)},
    )

    assert result.values["06"] == Decimal("21.00")
    assert result.values["08"] == Decimal("20.00")
    assert {entry.target for entry in result.entries} == {"06", "08"}
