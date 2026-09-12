"""Typed registry selector contract for the Modelo 100 inventory projection.

This module declares only the binding selector and its accumulating shape
validator. Source resolution, readiness, valuation, provenance, and registry
enrollment are owned by later integration steps; a selector declaration cannot
make an inventory schedule authoritative or complete.

The filing year is deliberately NOT pinned here. Which years carry an inventory
projection is a revision-owned fact, declared by the bindings the authoring tree
ships, so a later revision adding one must be an authoring change rather than an
edit to this file. Today only the Modelo 100 2025 revision declares them.

The operation-to-casilla identity below is a structural invariant of the
projection vocabulary: an operation names WHICH figure it produces, so its
destination is what the operation means, not a value the law re-sets per year.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, model_validator

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.modelo import Modelo
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_temporal import BindingTemporalSelector, SameTargetContext
from .errors import RegistryValidationError

if TYPE_CHECKING:
    from .schema import BindingDefinition

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


class InventoryProvider(BaseModel):
    """One immutable operation template expanded over runtime activity rows.

    ``complete_acquisition_cost`` names the legally complete acquisition-cost
    fact, never the existing IVA-exclusive purchase subtotal. The two stock
    variation operations name non-negative magnitudes in opposite directions,
    so no generic signed variation can enter the selector vocabulary.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.INVENTORY] = BindingSourceKind.INVENTORY

    modelo: Literal[Modelo.M100]
    # The source year is the TARGET's year, never an authored constant: the
    # declaration states timeless intent and the filing context supplies the
    # year. The casilla-renumbering hazard the former absolute ``filing_year``
    # guarded against is carried by the revision the binding is declared in
    # together with ``_INVENTORY_DESTINATION_BY_OPERATION``, which still pins
    # each operation to the exact destination casilla of its own revision.
    temporal: BindingTemporalSelector = SameTargetContext()
    projection_grain: Literal["taxpayer_year_activity"]
    fact: Literal["row_field"]
    record: Literal["inventory_activity"]
    grouping: Literal["per_inventory_activity"]
    row_field: InventoryProjectionOperation
    target_casilla_id: CasillaId

    @model_validator(mode="after")
    def _require_operation_destination_identity(self) -> InventoryProvider:
        expected = _INVENTORY_DESTINATION_BY_OPERATION[self.row_field]
        if self.target_casilla_id != expected:
            raise RegistryValidationError(
                f"inventory operation {self.row_field!r} must target casilla {expected!r}, "
                f"not {self.target_casilla_id!r}",
            )
        return self


def validate_inventory_binding(binding: BindingDefinition) -> list[str]:
    """Validate the inventory op invariant for snapshot build.

    The provider shape is the union member's own gate; the operation template's
    requirement of a row aggregation is the invariant left to lift.
    """
    failures: list[str] = []
    if binding.aggregation is None or binding.aggregation.op is not BindingAggregationOp.ROWS:
        failures.append(f"binding {binding.id!r} inventory operation template requires aggregation op 'rows'")
    return failures


__all__ = [
    "InventoryProjectionOperation",
    "InventoryProvider",
    "validate_inventory_binding",
]
