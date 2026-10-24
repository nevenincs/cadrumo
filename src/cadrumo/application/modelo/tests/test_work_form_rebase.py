"""A held change is judged again against its box as it stands, by the rules that let it be staged.

Fields come from the real Modelo 130 builder and are revised the way a newer
read would show them: the same box unchanged keeps the change, a box whose
value moved marks it changed, a box that no longer takes that kind of change
or that the form no longer has drops it. A box tells a frontend whether it
takes typing or clearing and the filer's own value, compared as figures, so a
retyped equal amount changes nothing.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..edit_models import ModeloEditHeldChangeV1, ModeloEditHeldKind
from ..work_form_models import (
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    comparable_entry,
    revised_field,
)
from ..work_form_rebase import ModeloFormRebaseOutcome, held_change, rebase_outcome
from .work_form_fixture import built_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _entered(operation: PinnedAuthorityOperation) -> ModeloFormField:
    field = next(field for field in built_form(operation, "130", 2026, "1T").fields() if not field.bindings)
    return revised_field(
        field,
        editability=ModeloFormEditability.EDITABLE_VALUE,
        origin=ModeloFormOrigin.ENTERED,
        value=Decimal("100.00"),
    )


def _held(field: ModeloFormField, kind: ModeloEditHeldKind) -> ModeloEditHeldChangeV1:
    return held_change(field, kind)


def test_a_box_says_what_it_takes_and_the_filers_own_value_as_a_figure(operation: PinnedAuthorityOperation) -> None:
    entered = _entered(operation)
    assumed = revised_field(entered, origin=ModeloFormOrigin.DEFAULT_TO_CONFIRM)
    closed = revised_field(entered, editability=ModeloFormEditability.NOT_WRITABLE, not_writable_reason="closed")

    assert (entered.takes_typed_value, entered.clearable) == (True, True)
    assert (assumed.takes_typed_value, assumed.clearable) == (True, False)
    assert (closed.takes_typed_value, closed.clearable) == (False, False)
    # The filer typing 100 over their own 100.00 changes nothing; an assumed value is nobody's own.
    assert entered.own_value == comparable_entry(Decimal("100")) == "100"
    assert assumed.own_value is None
    assert comparable_entry(Decimal("100.50")) == comparable_entry(Decimal("100.5"))


def test_a_held_change_is_kept_changed_or_dropped_by_its_box_now(operation: PinnedAuthorityOperation) -> None:
    entered = _entered(operation)
    held_set = _held(entered, ModeloEditHeldKind.SET)
    held_clear = _held(entered, ModeloEditHeldKind.CLEAR)

    same_figure = revised_field(entered, value=Decimal("100"))
    moved = revised_field(entered, value=Decimal("250.00"))
    sourced = revised_field(entered, origin=ModeloFormOrigin.IMPORTED)
    closed = revised_field(entered, editability=ModeloFormEditability.NOT_WRITABLE, not_writable_reason="closed")

    assert rebase_outcome(held_set, entered) is ModeloFormRebaseOutcome.KEPT
    assert rebase_outcome(held_set, same_figure) is ModeloFormRebaseOutcome.KEPT
    assert rebase_outcome(held_set, moved) is ModeloFormRebaseOutcome.CHANGED
    assert rebase_outcome(held_set, sourced) is ModeloFormRebaseOutcome.CHANGED
    assert rebase_outcome(held_set, closed) is ModeloFormRebaseOutcome.DROPPED
    assert rebase_outcome(held_set, None) is ModeloFormRebaseOutcome.DROPPED
    # Only the filer's own entry can be cleared, so once a source fills the box the clear is dropped.
    assert rebase_outcome(held_clear, sourced) is ModeloFormRebaseOutcome.DROPPED
