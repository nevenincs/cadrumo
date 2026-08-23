"""Inventory resolver boundary tests for registry-owned row templates.

S176 restores the displaced encrypted success, absence, corruption, conflict,
fingerprint/tamper, determinism, and multi-activity cohort matrix once runtime
activity-row expansion exists. S172 must fail closed without reading storage.
"""

from __future__ import annotations

from typing import get_args

import pytest

from ....core import BindingSourceKind, Period
from ....core.aggregation import BindingAggregation, BindingAggregationOp
from ....core.resources import resources
from ....domain.calculations.registry import (
    DataBindingDefinition,
    InventoryProjectionOperation,
    InventorySelector,
    ModeloRevision,
)
from ....domain.contribuyente.inventory import InventoryLedgerDocument
from .._inventory import _VALUE_ATTRIBUTE_BY_OPERATION, InventorySourceResolver
from .._source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _RepositorySpy:
    def __init__(self) -> None:
        self.loads = 0

    def load(self) -> InventoryLedgerDocument:
        self.loads += 1
        raise AssertionError("S172 templates must not read inventory before S176 expansion")


def _binding(operation: InventoryProjectionOperation, target: str) -> DataBindingDefinition:
    return DataBindingDefinition(
        id=f"inventory-{target}",
        source=BindingSourceKind.INVENTORY,
        selector={
            "modelo": "100",
            "filing_year": 2025,
            "projection_grain": "taxpayer_year_activity",
            "fact": "row_field",
            "record": "inventory_activity",
            "grouping": "per_inventory_activity",
            "row_field": operation,
            "target_casilla_id": target,
        },
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        legal_refs=("ley-35-2006:art-30",),
        source_refs=("aeat-renta-2025-manual",),
    )


def _revision(*, inventory: bool) -> ModeloRevision:
    base = resources().modelos.authority.snapshot("100", filing_year=2025, period="0A").revision
    bindings = (
        (
            _binding("complete_acquisition_cost", "0181"),
            _binding("closing_minus_opening_positive", "0177"),
            _binding("opening_minus_closing_positive", "0182"),
        )
        if inventory
        else ()
    )
    return base.model_copy(update={"bindings": bindings})


def _context(revision: ModeloRevision, *, year: int = 2025) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id="operator",
        modelo="100",
        filing_year=year,
        period=Period.from_year_and_code(year, "0A"),
        revision=revision,
    )


def test_inventory_operation_adapter_tracks_the_canonical_row_field_vocabulary() -> None:
    annotation = InventorySelector.model_fields["row_field"].annotation
    operations = set(get_args(getattr(annotation, "__value__", annotation)))

    assert operations == set(_VALUE_ATTRIBUTE_BY_OPERATION)
    assert operations == {
        "complete_acquisition_cost",
        "closing_minus_opening_positive",
        "opening_minus_closing_positive",
    }


def test_no_inventory_binding_is_allocation_and_repository_read_free() -> None:
    repository = _RepositorySpy()

    result = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision(inventory=False)))

    assert repository.loads == 0
    assert result.binding_values == {}
    assert result.row_binding_values == {}
    assert result.row_source_identities == {}
    assert result.unresolved_binding_ids == ()
    assert result.diagnostics == ()
    assert result.provenance == ()


def test_inventory_row_template_fails_closed_until_runtime_expansion() -> None:
    repository = _RepositorySpy()

    result = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision(inventory=True)))

    assert repository.loads == 0
    assert result.binding_values == {}
    assert result.row_binding_values == {}
    assert result.row_source_identities == {}
    assert result.unresolved_binding_ids == ("inventory-0177", "inventory-0181", "inventory-0182")
    assert result.provenance == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.reason == "source_domain_not_ready"
    assert diagnostic.source_kind == "inventory"
    assert diagnostic.resolver_id == "inventory"
    assert diagnostic.message == (
        "inventory source row_template_not_expanded: runtime inventory activity-row expansion is not enrolled"
    )
    assert diagnostic.remedy == "complete the canonical inventory row-expansion integration before calculation"


def test_inventory_row_template_rejects_unsupported_coordinate_without_repository_read() -> None:
    repository = _RepositorySpy()

    result = InventorySourceResolver(inventory_repository=repository).resolve(
        _context(_revision(inventory=True), year=2024),
    )

    assert repository.loads == 0
    assert result.unresolved_binding_ids == ("inventory-0177", "inventory-0181", "inventory-0182")
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].reason == "unhandled_binding_source"
    assert "unsupported_coordinate" in result.diagnostics[0].message
