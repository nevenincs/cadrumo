"""Contract tests for the 2025 Modelo 100 inventory selector."""

from __future__ import annotations

from itertools import product

import pytest
from pydantic import ValidationError

from .....core import BindingSourceKind, Modelo
from .....core.aggregation import BindingAggregation, BindingAggregationOp
from ..binding_selector_utils import binding_row_set_selector
from ..inventory_bindings import InventorySelector, validate_inventory_binding
from ..schema import DataBindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_OPERATION_DESTINATIONS = {
    "complete_acquisition_cost": "0181",
    "closing_minus_opening_positive": "0177",
    "opening_minus_closing_positive": "0182",
}


def _selector(
    operation: str,
    target_casilla_id: str,
) -> dict[str, object]:
    return {
        "modelo": Modelo.M100,
        "filing_year": 2025,
        "projection_grain": "taxpayer_year_activity",
        "fact": "row_field",
        "record": "inventory_activity",
        "grouping": "per_inventory_activity",
        "row_field": operation,
        "target_casilla_id": target_casilla_id,
    }


@pytest.mark.parametrize(("operation", "destination"), tuple(_OPERATION_DESTINATIONS.items()))
def test_inventory_selector_accepts_each_exact_2025_operation_destination(
    operation: str,
    destination: str,
) -> None:
    selector = InventorySelector.model_validate(_selector(operation, destination))

    assert selector.target_casilla_id == destination
    assert selector.projection_grain == "taxpayer_year_activity"
    assert selector.fact == "row_field"
    assert selector.record == "inventory_activity"
    assert selector.grouping == "per_inventory_activity"
    assert selector.row_field == operation


@pytest.mark.parametrize(
    ("operation", "destination"),
    tuple(
        (operation, destination)
        for operation, destination in product(_OPERATION_DESTINATIONS, _OPERATION_DESTINATIONS.values())
        if _OPERATION_DESTINATIONS[operation] != destination
    ),
)
def test_inventory_selector_refuses_crossed_operation_destination_identity(
    operation: str,
    destination: str,
) -> None:
    with pytest.raises(ValidationError, match="must target casilla"):
        InventorySelector.model_validate(_selector(operation, destination))


@pytest.mark.parametrize(
    "mutation",
    [
        {"filing_year": 2024},
        {"filing_year": "2025"},
        {"modelo": "130"},
        {"projection_grain": "taxpayer_year"},
        {"actividad_id": "literal-activity-forbidden"},
        {"actividad_id": "*"},
        {"fact": "scalar"},
        {"record": "activity"},
        {"grouping": "taxpayer_year"},
        {"operation": "complete_acquisition_cost"},
        {"row_field": "signed_stock_variation"},
        {"target_casilla_id": "0155"},
        {"signed": True},
        {"source_ready": True},
    ],
)
def test_inventory_selector_refuses_unsupported_scope_stale_signed_and_readiness_claims(
    mutation: dict[str, object],
) -> None:
    raw = _selector("complete_acquisition_cost", "0181")
    raw.update(mutation)

    with pytest.raises(ValidationError):
        InventorySelector.model_validate(raw)


def test_inventory_selector_requires_complete_row_template_shape() -> None:
    raw = _selector("complete_acquisition_cost", "0181")
    del raw["grouping"]

    with pytest.raises(ValidationError, match="grouping"):
        InventorySelector.model_validate(raw)


def test_inventory_selector_roundtrips_without_taxpayer_activity_identity() -> None:
    selector = InventorySelector.model_validate(_selector("complete_acquisition_cost", "0181"))

    assert "actividad_id" not in selector.model_dump()
    assert InventorySelector.model_validate(selector.model_dump()) == selector


def test_inventory_binding_validator_preserves_the_operation_destination_failure() -> None:
    binding = DataBindingDefinition.model_construct(
        id="inventory-stock-increase",
        source=BindingSourceKind.INVENTORY,
        selector=_selector("closing_minus_opening_positive", "0182"),
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
    )

    failures = validate_inventory_binding(binding)

    assert len(failures) == 1
    assert "must target casilla '0177', not '0182'" in failures[0]


def test_inventory_binding_validator_requires_rows_aggregation() -> None:
    binding = DataBindingDefinition.model_construct(
        id="inventory-purchases",
        source=BindingSourceKind.INVENTORY,
        selector=_selector("complete_acquisition_cost", "0181"),
        aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
    )

    assert validate_inventory_binding(binding) == [
        "binding 'inventory-purchases' inventory operation template requires aggregation op 'rows'",
    ]


def test_inventory_binding_reuses_the_canonical_row_set_projection() -> None:
    binding = DataBindingDefinition(
        id="inventory-purchases",
        source=BindingSourceKind.INVENTORY,
        selector=_selector("complete_acquisition_cost", "0181"),
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        legal_refs=("rd-439-2007:art-75",),
        source_refs=("aeat-renta-2025-inventory",),
    )

    row_set = binding_row_set_selector(binding)

    assert row_set is not None
    assert row_set.fact == "row_field"
    assert row_set.record == "inventory_activity"
    assert row_set.grouping == "per_inventory_activity"
    assert row_set.row_field == "complete_acquisition_cost"


def test_inventory_selector_is_frozen_and_has_only_the_three_unsigned_destinations() -> None:
    selector = InventorySelector.model_validate(_selector("complete_acquisition_cost", "0181"))

    assert set(_OPERATION_DESTINATIONS.values()) == {"0177", "0181", "0182"}
    assert "0155" not in _OPERATION_DESTINATIONS.values()
    assert selector.model_config["frozen"] is True
