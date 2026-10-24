"""What becomes of the changes a frontend holds when the declaration under them moves.

A frontend stages changes on boxes as they stood when it read the form: a
typed value, a cleared value, or a box given back to its source. When the
edit baseline is renewed because the declaration changed, each held change is
judged against the box as it stands now, by the same rules that let it be
staged:

* the box is gone, or no longer takes that kind of change: the change is
  dropped;
* the box's value or origin moved since the change was staged: the change is
  kept, and the frontend shows it as changed underneath, for the filer to look
  at again;
* otherwise the change is kept as it was.

A held change names its box, its kind and the digest of the box as it stood,
never a value, so the report travels as a plain payload. Whether a typed value
now equals the filer's own value, and so changes nothing, is the frontend's
comparison against the box's ``own_value``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from .work_form_models import ModeloFormAddressV1, ModeloFormField, ModeloWorkForm, address_key


class ModeloFormStagedKind(StrEnum):
    """The kind of change a frontend holds on a box."""

    SET = "set"
    CLEAR = "clear"
    RESTORE = "restore"


class ModeloFormStagedChangeV1(BaseModel):
    """One change a frontend holds: its box, its kind and the box's state digest when it was staged."""

    model_config = STRICT_FROZEN_CONFIG

    address: ModeloFormAddressV1
    kind: ModeloFormStagedKind
    held_state: str = Field(min_length=64, max_length=64)


class ModeloFormRebaseOutcome(StrEnum):
    """What a renewal did to one held change."""

    KEPT = "kept"
    CHANGED = "changed"
    DROPPED = "dropped"


class ModeloFormRebaseEntryV1(BaseModel):
    """One held change and what the renewal did to it."""

    model_config = STRICT_FROZEN_CONFIG

    address: ModeloFormAddressV1
    kind: ModeloFormStagedKind
    outcome: ModeloFormRebaseOutcome


_ACCEPTS: Final[Mapping[ModeloFormStagedKind, Callable[[ModeloFormField], bool]]] = MappingProxyType(
    {
        ModeloFormStagedKind.SET: lambda field: field.takes_typed_value,
        ModeloFormStagedKind.CLEAR: lambda field: field.clearable,
        ModeloFormStagedKind.RESTORE: lambda field: field.restorable,
    }
)
"""The field's own flag that says whether it takes each kind of change; total over the kinds."""


def accepts(field: ModeloFormField, kind: ModeloFormStagedKind) -> bool:
    """Whether ``field`` takes a change of ``kind`` as it stands."""
    return _ACCEPTS[kind](field)


def rebase_outcome(change: ModeloFormStagedChangeV1, field: ModeloFormField | None) -> ModeloFormRebaseOutcome:
    """What becomes of one held change on the box as it stands now; ``None`` is a box the form no longer has."""
    if field is None or not accepts(field, change.kind):
        return ModeloFormRebaseOutcome.DROPPED
    if field.state_digest != change.held_state:
        return ModeloFormRebaseOutcome.CHANGED
    return ModeloFormRebaseOutcome.KEPT


def rebase_report(
    staged: tuple[ModeloFormStagedChangeV1, ...], form: ModeloWorkForm
) -> tuple[ModeloFormRebaseEntryV1, ...]:
    """What becomes of each held change on ``form``, in the order they were held."""
    fields = {address_key(field.address): field for field in form.fields()}
    return tuple(
        ModeloFormRebaseEntryV1(
            address=change.address,
            kind=change.kind,
            outcome=rebase_outcome(change, fields.get(address_key(change.address))),
        )
        for change in staged
    )


def _require_total_kinds() -> None:
    if set(_ACCEPTS) != set(ModeloFormStagedKind):
        raise ValueError("every kind of held change needs the field flag that says whether a box takes it")


_require_total_kinds()

__all__ = [
    "ModeloFormRebaseEntryV1",
    "ModeloFormRebaseOutcome",
    "ModeloFormStagedChangeV1",
    "ModeloFormStagedKind",
    "accepts",
    "rebase_outcome",
    "rebase_report",
]
