"""Typed registry selector contract for the Modelo 100 inventory projection.

This module declares only the binding selector and its accumulating shape
validator. Source resolution, readiness, valuation, provenance, and registry
enrollment are owned by later integration steps; a selector declaration cannot
make an inventory schedule authoritative or complete.

The filing year is deliberately NOT pinned here. Which years carry an inventory
projection is a revision-owned fact, declared by the bindings the authoring tree
ships, so a later revision adding one must be an authoring change rather than an
edit to this file. Today only the Modelo 100 2025 revision declares them.

The operation-to-casilla identity below is retained as a structural invariant of
the projection vocabulary rather than migrated: an operation names WHICH figure
it produces, so its destination is what the operation means, not a value the law
re-sets per year. Retiring it would leave nothing at all checking that a binding
declaring ``complete_acquisition_cost`` targets the acquisition-cost box, and a
guard with no replacement is worse than a duplicated declaration. The embed
classification ledger records it as revision-owned data; that half needs
re-adjudication before it moves.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from ....core import CasillaId, Modelo, validated_casilla_id
from ....core.aggregation import BindingAggregationOp
from .binding_selector_utils import selector_against_model
from .errors import RegistryValidationError
from .schema import DataBindingDefinition

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
    """One immutable operation template expanded over runtime activity rows.

    ``complete_acquisition_cost`` names the legally complete acquisition-cost
    fact, never the existing IVA-exclusive purchase subtotal. The two stock
    variation operations name non-negative magnitudes in opposite directions,
    so no generic signed variation can enter the selector vocabulary.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: Literal[Modelo.M100]
    filing_year: int
    projection_grain: Literal["taxpayer_year_activity"]
    fact: Literal["row_field"]
    record: Literal["inventory_activity"]
    grouping: Literal["per_inventory_activity"]
    row_field: InventoryProjectionOperation
    target_casilla_id: CasillaId

    @model_validator(mode="after")
    def _require_operation_destination_identity(self) -> _InventorySelector:
        expected = _INVENTORY_DESTINATION_BY_OPERATION[self.row_field]
        if self.target_casilla_id != expected:
            raise RegistryValidationError(
                f"inventory operation {self.row_field!r} must target casilla {expected!r}, "
                f"not {self.target_casilla_id!r}",
            )
        return self


InventorySelector = _InventorySelector


def validate_inventory_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate an inventory selector while preserving field diagnostics."""
    failures = selector_against_model(binding, _InventorySelector)
    if binding.aggregation is None or binding.aggregation.op is not BindingAggregationOp.ROWS:
        failures.append(f"binding {binding.id!r} inventory operation template requires aggregation op 'rows'")
    return failures


__all__ = [
    "InventoryProjectionOperation",
    "InventorySelector",
    "validate_inventory_binding",
]
