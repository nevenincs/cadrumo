"""The filer's staged changes: in memory only, keyed by address, applied together after review.

Nothing is saved while the filer edits. Each change remembers how the field
read before it, so the list can show "was ..." beside the new value and the
review can say what the change displaces. Staging the value a field already
holds removes the change, so a field is never dirty without a difference.

A change is only offered where the field's editability allows it: a typed value
where the filer types, a clear where they declared a value, and a restore where
their value replaces a source. Anything else is refused here with the reason,
before it could reach the application.

Confirming an assumed value makes it the filer's own: the value the
calculation holds is kept as a typed value, exactly as if the filer had typed
it. Only a box the filer types into can be confirmed this way. A box a source
fills is never confirmed, because a value kept over a source replaces it.

When the declaration moves underneath the staged changes -- another
calculation, new source data -- the changes are kept and re-based on what the
declaration holds now: each is checked again against its field, a change that
can no longer be made is dropped, and a change whose box now reads differently
is marked, so the review can ask the filer to look at it again.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .....application.modelo.work_form_models import (
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormScalar,
    ModeloWorkForm,
    address_key,
    edit_address,
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
    NOTHING_TO_CONFIRM = "nothing_to_confirm"


@dataclass(frozen=True, slots=True)
class StagedChange:
    """One change the filer staged, with how the field read before it."""

    field: ModeloFormField
    kind: WorkbenchChangeKind
    value: ModeloFormScalar
    text: str
    previous_text: str
    displaces: Displacement
    #: The box read differently when the declaration was read again after the change was staged.
    before_changed: bool = False

    @property
    def key(self) -> AddressKey:
        """The semantic identity of the field the change is staged on."""
        return address_key(self.field.address)

    @property
    def change(self) -> WorkbenchChange:
        """The typed change the application receives."""
        return WorkbenchChange(address=edit_address(self.field), kind=self.kind, value=self.value)


@dataclass(frozen=True, slots=True)
class Rebase:
    """What reading the declaration again did to the staged changes."""

    #: Kept, but their box reads differently now; the review marks them.
    changed: tuple[StagedChange, ...] = ()
    #: No longer possible, or no longer needed, on the declaration as it stands.
    dropped: tuple[StagedChange, ...] = ()


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
        """Stage a typed value, or drop the change when it equals what the field holds.

        Only the filer's own value, or their value over a source, is dropped
        when unchanged: an assumed value kept unchanged is staged, because
        keeping it is how the filer confirms it.
        """
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

    def stage_confirmation(self, field: ModeloFormField) -> StageRefusal | None:
        """Stage an assumed value as the filer's own, without retyping it.

        Only a box the filer types into, holding a value nobody is recorded as
        having entered, can be confirmed. A box a source fills is refused, since
        keeping a value over it would replace the source rather than confirm it.
        """
        if field.editability is not ModeloFormEditability.EDITABLE_VALUE or edit_address(field) != field.address:
            return StageRefusal.NOT_EDITABLE
        if field.origin is not ModeloFormOrigin.DEFAULT_TO_CONFIRM or field.value is None:
            return StageRefusal.NOTHING_TO_CONFIRM
        return self.stage_value(field, field.value, self._before(field))

    def stage_clear(self, field: ModeloFormField) -> StageRefusal | None:
        """Stage removing a value the filer declared.

        Only the filer's own value can be removed. An assumed value is nobody's:
        the application refuses to empty a box something else fills, so the
        filer confirms it or types another value, 0 included, instead.
        """
        if field.editability is not ModeloFormEditability.EDITABLE_VALUE:
            return StageRefusal.NOT_EDITABLE
        if field.origin is not ModeloFormOrigin.ENTERED:
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

    def rebase(self, form: ModeloWorkForm) -> Rebase:
        """Check every staged change again against ``form``, keeping the ones that still apply."""
        fields = {address_key(field.address): field for field in form.fields()}
        staged = self._changes
        self._changes = {}
        changed: list[StagedChange] = []
        dropped: list[StagedChange] = []
        for key, change in staged.items():
            field = fields.get(key)
            if field is None or self._restage(change, field) is not None or key not in self._changes:
                self._changes.pop(key, None)
                dropped.append(change)
                continue
            if (field.value, field.origin) != (change.field.value, change.field.origin):
                marked = self._changes[key]
                self._changes[key] = StagedChange(
                    field=marked.field,
                    kind=marked.kind,
                    value=marked.value,
                    text=marked.text,
                    previous_text=marked.previous_text,
                    displaces=marked.displaces,
                    before_changed=True,
                )
                changed.append(self._changes[key])
        return Rebase(changed=tuple(changed), dropped=tuple(dropped))

    def _restage(self, change: StagedChange, field: ModeloFormField) -> StageRefusal | None:
        if change.kind is WorkbenchChangeKind.SET:
            return self.stage_value(field, change.value, change.text)
        if change.kind is WorkbenchChangeKind.CLEAR:
            return self.stage_clear(field)
        return self.stage_restore(field)

    def acknowledge(self) -> None:
        """Take the marks off the changes the filer has looked at again."""
        self._changes = {
            key: StagedChange(
                field=change.field,
                kind=change.kind,
                value=change.value,
                text=change.text,
                previous_text=change.previous_text,
                displaces=change.displaces,
            )
            for key, change in self._changes.items()
        }

    def revert(self, key: AddressKey) -> bool:
        """Drop the change staged on one address; ``False`` when there was none."""
        return self._changes.pop(key, None) is not None

    def discard(self) -> None:
        """Drop every staged change."""
        self._changes.clear()

    def payload(self) -> tuple[WorkbenchChange, ...]:
        """The typed changes to submit, in staging order."""
        return tuple(change.change for change in self._changes.values())


__all__ = ["Displacement", "Rebase", "StageRefusal", "StagedChange", "WorkbenchEditSession"]
