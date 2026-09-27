"""Grounded M100 inventory row-template registry data."""

from __future__ import annotations

import pytest

from .....core.aggregation import BindingAggregationOp, BindingSourceKind
from ..inventory_bindings import InventoryProvider
from .published_authority import PublishedGovernedFactSource, published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUPPORT = PublishedGovernedFactSource().supported_filing_years()
# The newest authored Modelo 100 edition sits one below the horizon, which carries
# its inventory templates forward; both exercises must load them exactly.
_REVIEWED_EDITION = _SUPPORT.horizon - 1


@pytest.mark.parametrize("filing_year", tuple(year for year in _SUPPORT.years if year >= _REVIEWED_EDITION))
def test_m100_loads_exact_grounded_inventory_operation_templates(filing_year: int) -> None:
    revision = published_snapshot("100", filing_year=filing_year, period="0A").revision
    bindings = tuple(binding for binding in revision.bindings if binding.source is BindingSourceKind.INVENTORY)

    assert {binding.id for binding in bindings} == {
        "renta-inventory-activity-closing-increase-0177",
        "renta-inventory-activity-acquisition-cost-0181",
        "renta-inventory-activity-closing-decrease-0182",
    }
    assert len(bindings) == 3
    assert all(isinstance(binding.provider, InventoryProvider) for binding in bindings)
    assert all(binding.aggregation is not None for binding in bindings)
    assert all(binding.aggregation.op is BindingAggregationOp.ROWS for binding in bindings if binding.aggregation)
    assert {binding.provider.row_field for binding in bindings if isinstance(binding.provider, InventoryProvider)} == {
        "closing_minus_opening_positive",
        "complete_acquisition_cost",
        "opening_minus_closing_positive",
    }
    assert {
        binding.provider.target_casilla_id for binding in bindings if isinstance(binding.provider, InventoryProvider)
    } == {"0177", "0181", "0182"}
    assert all(binding.legal_refs == ("ley-35-2006:art-30",) for binding in bindings)
    assert all(binding.source_refs == (f"aeat-renta-{_REVIEWED_EDITION}-manual-parte1",) for binding in bindings)


def test_inventory_templates_carry_no_taxpayer_activity_identity_or_legacy_shape() -> None:
    revision = published_snapshot("100", filing_year=2025, period="0A").revision
    bindings = tuple(binding for binding in revision.bindings if binding.source is BindingSourceKind.INVENTORY)

    for binding in bindings:
        assert isinstance(binding.provider, InventoryProvider)
        document = binding.provider.model_dump(mode="json")
        assert "actividad_id" not in document
        assert "operation" not in document
        assert "wildcard" not in repr(document).casefold()
        assert "0155" not in repr(document)


def test_inventory_templates_are_absent_from_other_m100_revisions() -> None:
    revision = published_snapshot("100", filing_year=2024, period="0A").revision

    assert not tuple(binding for binding in revision.bindings if binding.source is BindingSourceKind.INVENTORY)
