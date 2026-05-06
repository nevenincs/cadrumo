"""Modelo 115 registry behaviour for quarterly rental withholding filings."""

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


def test_modelo_115_validated_snapshot_owns_workflow_surfaces() -> None:
    modelo, catalogues = _load_modelo("115")

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_modelo(modelo)
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
    assert {
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
    } <= set(linked_by_surface)
    assert all(link.requires_snapshot for link in linked_by_surface.values())


def test_modelo_115_calculates_retention_and_amount_to_pay_from_registry_formula() -> None:
    modelo, catalogues = _load_modelo("115")
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=PROJECT_ROOT,
        filing_year=2026,
        period="1T",
    )

    result = calculate_registry_snapshot(
        snapshot,
        inputs={"01": Decimal("2"), "02": Decimal("1000.00"), "04": Decimal("25.00")},
        date_context={"filing_period": date(2026, 4, 20)},
    )

    assert result.values["03"] == Decimal("190.00")
    assert result.values["05"] == Decimal("165.00")
    entries_by_target = {entry.target: entry for entry in result.entries}
    assert entries_by_target["03"].legal_refs == ("rd-439-2007:art-100",)
    assert entries_by_target["05"].legal_refs == (
        "ley-35-2006:art-99",
        "rd-439-2007:art-100",
        "rd-439-2007:art-109",
    )
