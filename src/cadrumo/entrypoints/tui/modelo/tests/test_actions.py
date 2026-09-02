"""Proofs that the C4 action table is inert, closed, and honest about its scope.

The three properties this module defends are the ones a reader cannot verify by
looking at the table: that no row carries behaviour, that every row names an
operation the platform actually registers, and that the actions it CANNOT
dispatch are declared rather than omitted.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.actions`
"""

from __future__ import annotations

import dataclasses
import types

import pytest

from .....application.modelo import operation_definitions
from ..actions import (
    MODELO_ACTION_DISPATCH,
    MODELO_ACTIONS_WITHOUT_REGISTERED_OPERATIONS,
    ModeloActionPort,
    ModeloActionView,
    action_for_operation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _registered_definition_ids() -> frozenset[str]:
    """Every modelo operation id the application layer publicly declares."""
    return frozenset(
        value
        for name, value in vars(operation_definitions).items()
        if name.endswith("_OPERATION_DEFINITION_ID") and isinstance(value, str)
    )


def test_no_row_carries_behaviour() -> None:
    """A row must be data. A callable field is a hidden edge into a writer.

    Checked over every field of every row rather than over the declared type,
    because a field annotated ``str`` can still hold a bound method at runtime
    and the annotation would not object.
    """
    for action_id, row in MODELO_ACTION_DISPATCH.items():
        for field in dataclasses.fields(row):
            value = getattr(row, field.name)
            assert not callable(value), f"{action_id}.{field.name} holds a callable"
            assert not isinstance(value, types.ModuleType | types.MethodType | types.FunctionType), (
                f"{action_id}.{field.name} holds {type(value).__name__}"
            )


def test_a_row_cannot_acquire_a_handle_after_construction() -> None:
    """Inertness is enforced by the type, not promised by the docstring.

    Asserts the PROPERTY -- the assignment is refused and the value does not
    change -- rather than a specific exception class. Run directly, a frozen
    slotted dataclass raises ``FrozenInstanceError``; run under pytest, where
    this module is reachable under two identities, the generated
    ``__setattr__`` resolves ``super()`` against a different class object and
    raises ``TypeError`` instead. Both refuse the write, which is the contract
    that matters; pinning the class would make this test assert a fact about
    the import context rather than about the row.
    """
    row = next(iter(MODELO_ACTION_DISPATCH.values()))
    original = row.result_destination

    with pytest.raises((dataclasses.FrozenInstanceError, TypeError)):
        row.result_destination = "modelo.workspace.overview"  # type: ignore[misc]  # ty: ignore[invalid-assignment]  # reason: writing to the frozen row IS the refusal under test
    assert row.result_destination == original, "the write was raised on but still landed"

    with pytest.raises((AttributeError, TypeError)):
        row.injected_service = object()  # type: ignore[attr-defined]  # ty: ignore[invalid-assignment]  # reason: attaching an unknown attribute IS the refusal under test
    assert not hasattr(row, "injected_service"), "a service handle was attached to an inert row"


def test_every_dispatchable_action_names_a_registered_operation() -> None:
    """The table cannot name an operation the platform does not register.

    This is what makes the definition id the right key: a row pointing at an
    unregistered id would submit into nothing, and the failure would surface
    at the operator rather than here.
    """
    registered = _registered_definition_ids()
    assert registered, "no operation ids were discovered; this proof would be vacuous"

    unregistered = sorted(set(MODELO_ACTION_DISPATCH) - registered)
    assert not unregistered, f"dispatch rows naming unregistered operations: {unregistered}"


def test_the_table_is_keyed_by_the_id_each_row_carries() -> None:
    """A key that disagreed with its row would dispatch one action as another."""
    mismatched = [key for key, row in MODELO_ACTION_DISPATCH.items() if key != row.action_id]
    assert not mismatched, f"keys disagreeing with their row's action_id: {mismatched}"


def test_the_pending_actions_are_disjoint_from_the_dispatchable_ones() -> None:
    """An action cannot be both dispatchable and declared undispatchable.

    Overlap would mean the module contradicts itself about the one thing the
    pending list exists to say.
    """
    overlap = sorted(set(MODELO_ACTIONS_WITHOUT_REGISTERED_OPERATIONS) & set(MODELO_ACTION_DISPATCH))
    assert not overlap, f"actions declared both dispatchable and pending: {overlap}"


def test_no_pending_action_has_a_registered_operation() -> None:
    """The pending list must state a real gap, not a stale one.

    If one of these acquires a registered definition, it belongs in the
    dispatch table and this fails -- which is the point. A pending list that
    goes stale silently would understate the surface indefinitely.
    """
    registered = _registered_definition_ids()
    now_registered = sorted(set(MODELO_ACTIONS_WITHOUT_REGISTERED_OPERATIONS) & registered)
    assert not now_registered, (
        f"these are declared pending but now have registered operations, so they are dispatchable: {now_registered}"
    )


def test_a_destructive_action_does_not_return_to_the_screen_it_destroyed() -> None:
    """A discarded subject has no workspace to land on.

    Routing a destructive action back to its own overview would send the
    operator to a destination resolving against a work unit that no longer
    exists.
    """
    destructive = [row for row in MODELO_ACTION_DISPATCH.values() if row.destroys_subject]
    assert destructive, "no destructive action is declared; this proof would be vacuous"
    for row in destructive:
        assert not row.result_destination.startswith("modelo.workspace."), (
            f"{row.action_id} destroys its subject but lands on {row.result_destination}"
        )


def test_every_port_is_a_member_of_the_closed_set() -> None:
    """A row may not describe a reach the cohort has not adjudicated."""
    for row in MODELO_ACTION_DISPATCH.values():
        assert isinstance(row.port, ModeloActionPort)


def test_an_unknown_operation_resolves_to_none_rather_than_raising() -> None:
    """Not dispatched here is an ordinary answer, distinct from not existing."""
    assert action_for_operation("modelo.work.rename") is not None
    assert action_for_operation("modelo.nonexistent.operation") is None


def test_the_view_declares_no_more_fields_than_the_cohort_adjudicated() -> None:
    """Anti-drift: a new field on the row is a new claim about every action.

    Named explicitly so adding one is a deliberate act with this test as the
    place the decision is recorded, rather than a field that quietly appears
    on all seven rows at once.
    """
    assert {field.name for field in dataclasses.fields(ModeloActionView)} == {
        "action_id",
        "port",
        "capability",
        "result_destination",
        "destroys_subject",
    }
