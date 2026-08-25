"""Grounded 2025 M100 inventory row-template registry data."""

from __future__ import annotations

import pytest

from .....core import BindingSourceKind
from .....core.aggregation import BindingAggregationOp
from .....core.resources import resources
from .. import InventorySelector

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_m100_2025_loads_exact_grounded_inventory_operation_templates() -> None:
    revision = resources().modelos.authority.snapshot("100", filing_year=2025, period="0A").revision
    bindings = tuple(binding for binding in revision.bindings if binding.source is BindingSourceKind.INVENTORY)

    assert {binding.id for binding in bindings} == {
        "renta-2025-inventory-activity-closing-increase-0177",
        "renta-2025-inventory-activity-acquisition-cost-0181",
        "renta-2025-inventory-activity-closing-decrease-0182",
    }
    assert len(bindings) == 3
    assert all(isinstance(binding.selector, InventorySelector) for binding in bindings)
    assert all(binding.aggregation is not None for binding in bindings)
    assert all(binding.aggregation.op is BindingAggregationOp.ROWS for binding in bindings if binding.aggregation)
    assert {binding.selector.row_field for binding in bindings if isinstance(binding.selector, InventorySelector)} == {
        "closing_minus_opening_positive",
        "complete_acquisition_cost",
        "opening_minus_closing_positive",
    }
    assert {
        binding.selector.target_casilla_id for binding in bindings if isinstance(binding.selector, InventorySelector)
    } == {"0177", "0181", "0182"}
    assert all(binding.legal_refs == ("ley-35-2006:art-30",) for binding in bindings)
    assert all(binding.source_refs == ("aeat-renta-2025-manual-parte1",) for binding in bindings)


def test_inventory_templates_carry_no_taxpayer_activity_identity_or_legacy_shape() -> None:
    revision = resources().modelos.authority.snapshot("100", filing_year=2025, period="0A").revision
    bindings = tuple(binding for binding in revision.bindings if binding.source is BindingSourceKind.INVENTORY)

    for binding in bindings:
        assert isinstance(binding.selector, InventorySelector)
        document = binding.selector.model_dump(mode="json")
        assert "actividad_id" not in document
        assert "operation" not in document
        assert "wildcard" not in repr(document).casefold()
        assert "0155" not in repr(document)


def test_inventory_templates_are_absent_from_other_m100_revisions() -> None:
    revision = resources().modelos.authority.snapshot("100", filing_year=2024, period="0A").revision

    assert not tuple(binding for binding in revision.bindings if binding.source is BindingSourceKind.INVENTORY)
