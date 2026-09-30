"""The filer's staged changes: in memory only, keyed by address, applied together after review.

Nothing is saved while the filer edits. Each change remembers how the field
read before it, so the list can show "was ..." beside the new value and the
review can say what the change displaces. Staging the value a field already
holds removes the change, so a field is never dirty without a difference.

A change is only offered where the field's editability allows it: a typed value
where the filer types, a clear where they declared a value, and a restore where
their value replaces a source. Anything else is refused here with the reason,
before it could reach the application.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .....application.modelo.work_form_models import (
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormScalar,
    address_key,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .casilla_list import AddressKey, CasillaListEntry, value_text
from .page_items import StagedDisplay
from .ports import WorkbenchChange, WorkbenchChangeKind
from .vocabulary import TYPED_EDITABILITIES


class Displacement(StrEnum):
    """What a staged change replaces, for the review's warnings."""

    NOTHING = "nothing"
    SOURCE = "source"
    CALCULATION = "calculation"
    FILER = "filer"


class StageRefusal(StrEnum):
    """Why a change could not be staged on a field."""

    NOT_EDITABLE = "not_editable"
    NOTHING_TO_CLEAR = "nothing_to_clear"
    NOTHING_TO_RESTORE = "nothing_to_restore"


@dataclass(frozen=True, slots=True)
class StagedChange:
    """One change the filer staged, with how the field read before it."""

    field: ModeloFormField
    kind: WorkbenchChangeKind
    value: ModeloFormScalar
    text: str
    previous_text: str
    displaces: Displacement

    @property
    def change(self) -> WorkbenchChange:
        """The typed change the application receives."""
        return WorkbenchChange(address=self.field.address, kind=self.kind, value=self.value)


def _displacement(field: ModeloFormField) -> Displacement:
    if field.origin in {ModeloFormOrigin.IMPORTED, ModeloFormOrigin.OVERRIDES_SOURCE}:
        return Displacement.SOURCE
    if field.origin is ModeloFormOrigin.CALCULATED:
        return Displacement.CALCULATION
    if field.origin is ModeloFormOrigin.ENTERED:
        return Displacement.FILER
    return Displacement.NOTHING


class WorkbenchEditSession:
    """The staged changes of one workbench, in memory only."""

    def __init__(self, language: OutputLanguage) -> None:
        """Start clean, in the filer's language."""
        self._language = language
        self._changes: dict[AddressKey, StagedChange] = {}

    @property
    def changes(self) -> tuple[StagedChange, ...]:
        """The staged changes, in the order they were first made."""
        return tuple(self._changes.values())

    @property
    def dirty(self) -> bool:
        """Whether anything is staged."""
        return bool(self._changes)

    def display(self) -> dict[AddressKey, StagedDisplay]:
        """How each staged change reads on its line."""
        return {
            key: StagedDisplay(text=change.text, previous_text=change.previous_text)
            for key, change in self._changes.items()
        }

    def _before(self, field: ModeloFormField) -> str:
        return value_text(CasillaListEntry(field), self._language)

    def stage_value(self, field: ModeloFormField, value: ModeloFormScalar, display: str) -> StageRefusal | None:
        """Stage a typed value, or drop the change when it equals what the field holds."""
        if field.editability not in TYPED_EDITABILITIES:
            return StageRefusal.NOT_EDITABLE
        key = address_key(field.address)
        if value == field.value and field.origin in {ModeloFormOrigin.ENTERED, ModeloFormOrigin.OVERRIDES_SOURCE}:
            self._changes.pop(key, None)
            return None
        self._changes[key] = StagedChange(
            field=field,
            kind=WorkbenchChangeKind.SET,
            value=value,
            text=display,
            previous_text=self._before(field),
            displaces=_displacement(field),
        )
        return None

    def stage_clear(self, field: ModeloFormField) -> StageRefusal | None:
        """Stage removing a value the filer declared."""
        if field.editability is not ModeloFormEditability.EDITABLE_VALUE:
            return StageRefusal.NOT_EDITABLE
        if field.origin not in {ModeloFormOrigin.ENTERED, ModeloFormOrigin.DEFAULT_TO_CONFIRM}:
            return StageRefusal.NOTHING_TO_CLEAR
        self._changes[address_key(field.address)] = StagedChange(
            field=field,
            kind=WorkbenchChangeKind.CLEAR,
            value=None,
            text=tr("tui.modelo.workbench.staged.clear"),
            previous_text=self._before(field),
            displaces=Displacement.FILER,
        )
        return None

    def stage_restore(self, field: ModeloFormField) -> StageRefusal | None:
        """Stage giving a field back to its source."""
        if field.editability not in {
            ModeloFormEditability.OVERRIDABLE_SOURCE,
            ModeloFormEditability.EDITABLE_OVERRIDE,
        }:
            return StageRefusal.NOT_EDITABLE
        if field.origin not in {ModeloFormOrigin.OVERRIDES_SOURCE, ModeloFormOrigin.ENTERED}:
            return StageRefusal.NOTHING_TO_RESTORE
        self._changes[address_key(field.address)] = StagedChange(
            field=field,
            kind=WorkbenchChangeKind.RESTORE,
            value=None,
            text=tr("tui.modelo.workbench.staged.restore"),
            previous_text=self._before(field),
            displaces=Displacement.FILER,
        )
        return None

    def revert(self, key: AddressKey) -> bool:
        """Drop the change staged on one address; ``False`` when there was none."""
        return self._changes.pop(key, None) is not None

    def discard(self) -> None:
        """Drop every staged change."""
        self._changes.clear()

    def payload(self) -> tuple[WorkbenchChange, ...]:
        """The typed changes to submit, in staging order."""
        return tuple(change.change for change in self._changes.values())


__all__ = ["Displacement", "StageRefusal", "StagedChange", "WorkbenchEditSession"]
