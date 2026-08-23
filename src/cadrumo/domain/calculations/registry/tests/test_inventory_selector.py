"""Contract tests for the 2025 Modelo 100 inventory selector."""

from __future__ import annotations

from itertools import product

import pytest
from pydantic import ValidationError

from .....core import BindingSourceKind, Modelo
from .._inventory_bindings import InventorySelector, validate_inventory_binding
from .._schema import DataBindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_OPERATION_DESTINATIONS = {
    "complete_acquisition_cost": "0181",
    "closing_minus_opening_positive": "0177",
    "opening_minus_closing_positive": "0182",
}


def _selector(
    operation: str,
    target_casilla_id: str,
    *,
    actividad_id: object = "actividad-profesional-1",
) -> dict[str, object]:
    return {
        "modelo": Modelo.M100,
        "filing_year": 2025,
        "projection_grain": "taxpayer_year_activity",
        "actividad_id": actividad_id,
        "operation": operation,
        "target_casilla_id": target_casilla_id,
    }


@pytest.mark.parametrize(("operation", "destination"), tuple(_OPERATION_DESTINATIONS.items()))
def test_inventory_selector_accepts_each_exact_2025_operation_destination(
    operation: str,
    destination: str,
) -> None:
    selector = InventorySelector.model_validate(_selector(operation, destination))

    assert selector.operation == operation
    assert selector.target_casilla_id == destination
    assert selector.projection_grain == "taxpayer_year_activity"
    assert selector.actividad_id == "actividad-profesional-1"


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
        {"actividad_id": ""},
        {"actividad_id": 7},
        {"actividad_id": None},
        {"operation": "signed_stock_variation"},
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


def test_inventory_selector_requires_exact_actividad_identity() -> None:
    raw = _selector("complete_acquisition_cost", "0181")
    del raw["actividad_id"]

    with pytest.raises(ValidationError, match="actividad_id"):
        InventorySelector.model_validate(raw)


def test_inventory_selector_distinguishes_activity_and_roundtrips_exactly() -> None:
    first = InventorySelector.model_validate(
        _selector("complete_acquisition_cost", "0181", actividad_id="actividad-a"),
    )
    second = InventorySelector.model_validate(
        _selector("complete_acquisition_cost", "0181", actividad_id="actividad-b"),
    )

    assert first != second
    assert first.actividad_id != second.actividad_id
    assert InventorySelector.model_validate(first.model_dump()) == first


def test_inventory_binding_validator_preserves_the_operation_destination_failure() -> None:
    binding = DataBindingDefinition.model_construct(
        id="inventory-stock-increase",
        source=BindingSourceKind.INVENTORY,
        selector=_selector("closing_minus_opening_positive", "0182"),
        aggregation=None,
    )

    failures = validate_inventory_binding(binding)

    assert len(failures) == 1
    assert "must target casilla '0177', not '0182'" in failures[0]


def test_inventory_selector_is_frozen_and_has_only_the_three_unsigned_destinations() -> None:
    selector = InventorySelector.model_validate(_selector("complete_acquisition_cost", "0181"))

    assert set(_OPERATION_DESTINATIONS.values()) == {"0177", "0181", "0182"}
    assert "0155" not in _OPERATION_DESTINATIONS.values()
    assert selector.model_config["frozen"] is True
