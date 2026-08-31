"""Caller-override ownership for canonical inventory bindings."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.schema import DataBindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_input_kind import InputKind
from .._action_errors import ModeloAggregationBindingError
from .._calculation_actions import _reject_caller_overrides_of_source_bindings
from .._calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES
from .._registry_helpers import validate_casilla_input_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DESTINATIONS = {
    "complete_acquisition_cost": "0181",
    "closing_minus_opening_positive": "0177",
    "opening_minus_closing_positive": "0182",
}


def _binding(operation: str, target: str) -> DataBindingDefinition:
    return DataBindingDefinition(
        id=f"inventory-{target}",
        source=BindingSourceKind.INVENTORY,
        selector={
            # Mirrors the shipped `renta-2025-inventory-activity-*` selectors
            # verbatim. The `actividad_id` / `operation` pair this replaced is a
            # shape `_InventorySelector` no longer accepts: it now requires
            # `fact`, `record`, `grouping` and `row_field`, and forbids
            # `actividad_id`. The fixture's operation tokens already matched the
            # registry's `row_field` values, so only the envelope moved.
            "modelo": "100",
            "filing_year": 2025,
            "projection_grain": "taxpayer_year_activity",
            "fact": "row_field",
            "record": "inventory_activity",
            "grouping": "per_inventory_activity",
            "row_field": operation,
            "target_casilla_id": target,
        },
        legal_refs=("ley-35-2006:art-30",),
        source_refs=("aeat-renta-2025-manual",),
    )


def _revision(*, declared: bool = True, alias: bool = False) -> ModeloRevision:
    base = bundled_authority().snapshot("100", filing_year=2025, period="0A").revision
    if not declared:
        # "Undeclared" has to be BUILT now. Modelo 100/2025 ships three real
        # inventory bindings, so returning the base revision unchanged asserted
        # the opposite of this branch's name: casilla 0181 arrived source-owned
        # and the caller-override lock refused it, correctly. Strip the
        # inventory source and hand its casillas back to manual input, which is
        # the state the undeclared cases are about.
        undeclared_bindings = tuple(
            binding for binding in base.bindings if binding.source is not BindingSourceKind.INVENTORY
        )
        freed = set(_DESTINATIONS.values())
        undeclared_casillas = tuple(
            casilla.model_copy(update={"input_kind": InputKind.MANUAL, "binding": None})
            if str(casilla.id) in freed
            else casilla
            for casilla in base.casillas
        )
        return base.model_copy(
            update={"bindings": undeclared_bindings, "casillas": undeclared_casillas},
        )
    bindings = tuple(_binding(operation, target) for operation, target in _DESTINATIONS.items())
    by_target = {target: f"inventory-{target}" for target in _DESTINATIONS.values()}
    casillas = tuple(
        casilla.model_copy(
            update={
                "input_kind": InputKind.BOUND,
                "binding": by_target[str(casilla.id)],
                "aliases": ("181",) if alias and str(casilla.id) == "0181" else (),
            },
        )
        if str(casilla.id) in by_target
        else casilla
        for casilla in base.casillas
    )
    return base.model_copy(update={"bindings": bindings, "casillas": casillas})


@pytest.mark.parametrize("value", [Decimal("100.00"), Decimal("999.99")])
def test_declared_inventory_binding_refuses_equal_and_different_caller_values(value: Decimal) -> None:
    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        _reject_caller_overrides_of_source_bindings(
            revision=_revision(),
            owned_sources=BUCKET_AGGREGATION_LOCK_SOURCES,
            caller_binding_values={"inventory-0181": value},
            caller_casilla_inputs={},
        )

    assert exc_info.value.context == {"rejected_binding_ids": ["inventory-0181"]}


@pytest.mark.parametrize("targets", [("0181",), ("0177", "0182"), ("0177", "0181", "0182")])
def test_declared_inventory_refuses_partial_and_complete_casilla_overrides(targets: tuple[str, ...]) -> None:
    values = {validated_casilla_id(target): Decimal("0.00") for target in targets}
    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        _reject_caller_overrides_of_source_bindings(
            revision=_revision(),
            owned_sources=BUCKET_AGGREGATION_LOCK_SOURCES,
            caller_binding_values={},
            caller_casilla_inputs=values,
        )

    assert exc_info.value.context == {"casillas": sorted(values)}


def test_inventory_semantic_alias_is_refused_before_ownership_matching() -> None:
    with pytest.raises(RegistryValidationError) as exc_info:
        validate_casilla_input_ids(
            _revision(alias=True),
            {"181": Decimal("100.00")},
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["casilla_ids"] == "181"


def test_undeclared_inventory_leaves_manual_casilla_available_and_policy_is_replay_stable() -> None:
    revision = _revision(declared=False)
    manual = {validated_casilla_id("0181"): Decimal("100.00")}
    first = validate_casilla_input_ids(revision, manual)
    second = validate_casilla_input_ids(revision, manual)

    _reject_caller_overrides_of_source_bindings(
        revision=revision,
        owned_sources=BUCKET_AGGREGATION_LOCK_SOURCES,
        caller_binding_values={},
        caller_casilla_inputs=first,
    )
    assert first == second == manual


def test_inventory_lock_is_single_homed_in_canonical_policy_projection() -> None:
    assert BindingSourceKind.INVENTORY in BUCKET_AGGREGATION_LOCK_SOURCES
