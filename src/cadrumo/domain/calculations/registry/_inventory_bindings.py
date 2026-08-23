"""Typed registry selector contract for the 2025 Modelo 100 inventory projection.

This module declares only the binding selector and its accumulating shape
validator. Source resolution, readiness, valuation, provenance, and registry
enrollment are owned by later integration steps; a selector declaration cannot
make an inventory schedule authoritative or complete.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ....core import CasillaId, Modelo, validated_casilla_id
from ._binding_selector_utils import selector_against_model
from ._errors import RegistryValidationError
from ._schema import DataBindingDefinition

type InventoryProjectionOperation = Literal[
    "complete_acquisition_cost",
    "closing_minus_opening_positive",
    "opening_minus_closing_positive",
]

_INVENTORY_DESTINATION_BY_OPERATION: dict[InventoryProjectionOperation, CasillaId] = {
    "complete_acquisition_cost": validated_casilla_id(
        "0181",
        surface="inventory complete-acquisition-cost destination",
    ),
    "closing_minus_opening_positive": validated_casilla_id(
        "0177",
        surface="inventory positive closing-minus-opening destination",
    ),
    "opening_minus_closing_positive": validated_casilla_id(
        "0182",
        surface="inventory positive opening-minus-closing destination",
    ),
}


class _InventorySelector(BaseModel):
    """One approved inventory fact projected at taxpayer/year/activity grain.

    ``complete_acquisition_cost`` names the legally complete acquisition-cost
    fact, never the existing IVA-exclusive purchase subtotal. The two stock
    variation operations name non-negative magnitudes in opposite directions,
    so no generic signed variation can enter the selector vocabulary.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: Literal[Modelo.M100] = Modelo.M100
    filing_year: Literal[2025] = 2025
    projection_grain: Literal["taxpayer_year_activity"] = "taxpayer_year_activity"
    actividad_id: str = Field(min_length=1)
    operation: InventoryProjectionOperation
    target_casilla_id: CasillaId

    @model_validator(mode="after")
    def _require_operation_destination_identity(self) -> _InventorySelector:
        expected = _INVENTORY_DESTINATION_BY_OPERATION[self.operation]
        if self.target_casilla_id != expected:
            raise RegistryValidationError(
                f"inventory operation {self.operation!r} must target casilla {expected!r}, "
                f"not {self.target_casilla_id!r}",
            )
        return self


InventorySelector = _InventorySelector


def validate_inventory_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate an inventory selector while preserving field diagnostics."""
    return selector_against_model(binding, _InventorySelector)


__all__ = [
    "InventoryProjectionOperation",
    "InventorySelector",
    "validate_inventory_binding",
]
