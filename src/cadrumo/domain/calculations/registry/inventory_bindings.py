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

from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import AfterValidator, BaseModel

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.casilla_id import CasillaId
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_selector_utils import selector_against_model, selector_as_dict
from .binding_temporal import BindingTemporalSelector, SameTargetContext
from .form_codes import form_role_validator, resolve_form_codes

if TYPE_CHECKING:
    from .schema import BindingDefinition

type InventoryProjectionOperation = Literal[
    "complete_acquisition_cost",
    "closing_minus_opening_positive",
    "opening_minus_closing_positive",
]


class InventoryProvider(BaseModel):
    """One immutable operation template expanded over runtime activity rows.

    ``complete_acquisition_cost`` names the legally complete acquisition-cost
    fact, never the existing IVA-exclusive purchase subtotal. The two stock
    variation operations name non-negative magnitudes in opposite directions,
    so no generic signed variation can enter the selector vocabulary.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.INVENTORY] = BindingSourceKind.INVENTORY

    modelo: Annotated[str, AfterValidator(form_role_validator("renta.annual"))]
    # The source year is the TARGET's year, never an authored constant: the
    # declaration states timeless intent and the filing context supplies the
    # year. The casilla-renumbering hazard the former absolute ``filing_year``
    # guarded against is carried by the revision the binding is declared in
    # together with the registry's ``m100.inventory`` row codes, which still pin
    # each operation to the exact destination casilla of its own revision.
    temporal: BindingTemporalSelector = SameTargetContext()
    projection_grain: Literal["taxpayer_year_activity"]
    fact: Literal["row_field"]
    record: Literal["inventory_activity"]
    grouping: Literal["per_inventory_activity"]
    row_field: InventoryProjectionOperation
    target_casilla_id: CasillaId


def validate_inventory_binding(binding: BindingDefinition) -> list[str]:
    """Validate the inventory operation invariants for snapshot build.

    The operation-to-destination identity is re-run here through the shared
    selector gate rather than trusted to have happened earlier: a snapshot is
    built from provider objects that may reach this boundary without having
    passed model validation, and an operation silently landing on another
    operation's casilla is a filing-grade misdeclaration, not a shape detail.
    The destination itself is the registry's: its ``m100.inventory`` row codes.
    """
    failures = selector_against_model(binding, InventoryProvider)
    if not failures:
        selector = InventoryProvider.model_validate(selector_as_dict(binding))
        expected = resolve_form_codes("form-row-codes").code(f"m100.inventory.{selector.row_field}")
        if selector.target_casilla_id != expected:
            failures.append(
                f"inventory operation {selector.row_field!r} must target casilla {expected!r}, "
                f"not {selector.target_casilla_id!r}",
            )
    if binding.aggregation is None or binding.aggregation.op is not BindingAggregationOp.ROWS:
        failures.append(f"binding {binding.id!r} inventory operation template requires aggregation op 'rows'")
    return failures


__all__ = [
    "InventoryProjectionOperation",
    "InventoryProvider",
    "validate_inventory_binding",
]
