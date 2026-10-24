"""What becomes of the changes a frontend holds when the declaration under them moves.

A frontend stages changes on boxes as they stood when it read the form: a
typed value, a cleared value, or a box given back to its source. When the
declaration moves under them, each held change is judged against the box as it
stands now, by the same rules that let it be staged:

* the box is gone, or no longer takes that kind of change: the change is
  dropped;
* the box's value or origin moved since the change was staged: the change is
  kept, and the frontend shows it as changed underneath, for the filer to look
  at again;
* otherwise the change is kept as it was.

A held change names its edit address, its kind and the box's state digest
when it was staged. The digest is derived from the box's value, so a held
change travels only inside a preflight's transient submission, in process
memory; the answer carries what became of each change and nothing derived
from a value. Whether a typed value now equals the filer's own value, and so
changes nothing, is the comparison against the box's ``own_value``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG
from .edit_models import (
    ModeloEditBindingAddressV1,
    ModeloEditHeldAddressV1,
    ModeloEditHeldChangeV1,
    ModeloEditHeldKind,
    ModeloEditScalarAddressV1,
)
from .work_form_models import (
    ModeloFormAddressV1,
    ModeloFormBindingAddressV1,
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloWorkForm,
    address_key,
    edit_address,
)


class ModeloFormRebaseOutcome(StrEnum):
    """What the declaration's move did to one held change."""

    KEPT = "kept"
    CHANGED = "changed"
    DROPPED = "dropped"


class ModeloFormRebaseEntryV1(BaseModel):
    """One held change, by its edit address and kind, and what became of it."""

    model_config = STRICT_FROZEN_CONFIG

    address: ModeloEditHeldAddressV1
    kind: ModeloEditHeldKind
    outcome: ModeloFormRebaseOutcome


_ACCEPTS: Final[Mapping[ModeloEditHeldKind, Callable[[ModeloFormField], bool]]] = MappingProxyType(
    {
        ModeloEditHeldKind.SET: lambda field: field.takes_typed_value,
        ModeloEditHeldKind.CLEAR: lambda field: field.clearable,
        ModeloEditHeldKind.RESTORE: lambda field: field.restorable,
    }
)
"""The field's own flag that says whether it takes each kind of change; total over the kinds."""


def accepts(field: ModeloFormField, kind: ModeloEditHeldKind) -> bool:
    """Whether ``field`` takes a change of ``kind`` as it stands."""
    return _ACCEPTS[kind](field)


def held_edit_address(address: ModeloFormAddressV1) -> ModeloEditHeldAddressV1:
    """The edit address a change at a field's edit address is held under."""
    if isinstance(address, ModeloFormCasillaAddressV1):
        return ModeloEditScalarAddressV1(casilla_id=address.casilla_id)
    return ModeloEditBindingAddressV1(binding_id=address.binding_id)


def _form_edit_address(address: ModeloEditHeldAddressV1) -> ModeloFormAddressV1:
    if isinstance(address, ModeloEditScalarAddressV1):
        return ModeloFormCasillaAddressV1(casilla_id=address.casilla_id)
    return ModeloFormBindingAddressV1(binding_id=address.binding_id)


def held_change(field: ModeloFormField, kind: ModeloEditHeldKind) -> ModeloEditHeldChangeV1:
    """A change of ``kind`` staged on ``field`` as it stands, as a preflight judges it again later."""
    return ModeloEditHeldChangeV1(
        address=held_edit_address(edit_address(field)), kind=kind, held_state=field.state_digest
    )


def rebase_outcome(change: ModeloEditHeldChangeV1, field: ModeloFormField | None) -> ModeloFormRebaseOutcome:
    """What becomes of one held change on the box as it stands now; ``None`` is a box the form no longer has."""
    if field is None or not accepts(field, change.kind):
        return ModeloFormRebaseOutcome.DROPPED
    if field.state_digest != change.held_state:
        return ModeloFormRebaseOutcome.CHANGED
    return ModeloFormRebaseOutcome.KEPT


def rebase_report(
    held: tuple[ModeloEditHeldChangeV1, ...], form: ModeloWorkForm
) -> tuple[ModeloFormRebaseEntryV1, ...]:
    """What becomes of each held change on ``form``, by the box its edit address reaches, in the order held."""
    fields = {address_key(edit_address(field)): field for field in form.fields()}
    return tuple(
        ModeloFormRebaseEntryV1(
            address=change.address,
            kind=change.kind,
            outcome=rebase_outcome(change, fields.get(address_key(_form_edit_address(change.address)))),
        )
        for change in held
    )


def _require_total_kinds() -> None:
    if set(_ACCEPTS) != set(ModeloEditHeldKind):
        raise ValueError("every kind of held change needs the field flag that says whether a box takes it")


_require_total_kinds()

__all__ = [
    "ModeloFormRebaseEntryV1",
    "ModeloFormRebaseOutcome",
    "accepts",
    "held_change",
    "held_edit_address",
    "rebase_outcome",
    "rebase_report",
]
