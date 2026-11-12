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
it. Only a box whose value is the filer's own entry can be confirmed this way:
a manual box, or a value the form asks for that no box prints. A box a source
fills is never confirmed, because a value kept over a source replaces it.

A statement the form serves -- that a family of boxes holds no amount -- is
staged on every box it names, each as its own change, so it is reviewed and
applied with the rest; its words are the form's own, never the workbench's.
Only a family the form serves now can be staged, and only on boxes the form
shows.

When the declaration moves underneath the staged changes -- another
calculation, new source data -- the changes are kept and re-based on what the
declaration holds now: each is checked again against its field, a change that
can no longer be made is dropped, and a change whose box now reads differently
is marked, so the review can ask the filer to look at it again.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum

from .....application.modelo.edit_models import ModeloEditHeldChangeV1, ModeloEditHeldKind
from .....application.modelo.work_form_field_vocabulary import (
    ModeloFormBindingAddressV1,
    ModeloFormEditability,
    ModeloFormOrigin,
    ModeloFormScalar,
    address_key,
)
from .....application.modelo.work_form_models import (
    ModeloFormCarryAttestation,
    ModeloFormField,
    ModeloWorkForm,
    confirmable,
    edit_address,
)
from .....application.modelo.work_form_prior_value_models import ModeloFormPriorValueAttestation
from .....application.modelo.work_form_rebase import ModeloFormRebaseOutcome, held_change, rebase_outcome
from .....application.modelo.work_form_scalar_values import comparable_entry
from .....application.modelo.work_form_typing_effect import ModeloFormDisplacement, field_displacement
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .casilla_list_models import AddressKey, CasillaListEntry
from .casilla_list_values import value_text
from .page_items import StagedDisplay
from .ports import WorkbenchChange, WorkbenchChangeKind

_FIGURE_KINDS = frozenset({WorkbenchChangeKind.SET, WorkbenchChangeKind.STATE_PRIOR_VALUE})


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
    displaces: ModeloFormDisplacement
    #: The box read differently when the declaration was read again after the change was staged.
    before_changed: bool = False
    #: The served statement a ``STATE_ABSENT`` change makes, whose words it shows; ``None`` for any other change.
    statement: ModeloFormCarryAttestation | None = None
    #: The served entry a ``STATE_PRIOR_VALUE`` change states the figure of, whose words it shows; else ``None``.
    prior_value: ModeloFormPriorValueAttestation | None = None

    @property
    def key(self) -> AddressKey:
        """The semantic identity of the field the change is staged on."""
        return address_key(self.field.address)

    @property
    def change(self) -> WorkbenchChange:
        """The typed change the application receives."""
        return WorkbenchChange(address=edit_address(self.field), kind=self.kind, value=self.value)

    @property
    def held(self) -> ModeloEditHeldChangeV1:
        """The change as the application judges it again: its box, its kind, and the box as it stood."""
        return held_change(self.field, ModeloEditHeldKind(self.kind.value))


@dataclass(frozen=True, slots=True)
class Rebase:
    """What reading the declaration again did to the staged changes."""

    #: Kept, but their box reads differently now; the review marks them.
    changed: tuple[StagedChange, ...] = ()
    #: No longer possible, or no longer needed, on the declaration as it stands.
    dropped: tuple[StagedChange, ...] = ()


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

    def refresh_language(
        self, language: OutputLanguage, statements: tuple[ModeloFormCarryAttestation, ...] = ()
    ) -> None:
        """Reformat retained changes without restaging, rebasing or changing their values.

        A staged statement takes the words of the same family among ``statements``, the form's in
        ``language``; without them it keeps the words it was staged with.
        """
        self._language = language
        worded = {statement.family: statement for statement in statements}
        for key, change in tuple(self._changes.items()):
            if change.statement is not None:
                served = worded.get(change.statement.family, change.statement)
                self._changes[key] = replace(
                    change, text=served.action_words, previous_text=self._before(change.field), statement=served
                )
                continue
            if change.kind is WorkbenchChangeKind.CLEAR:
                text = tr("workspace.modelo.staged.clear")
            elif change.kind is WorkbenchChangeKind.RESTORE:
                text = tr("workspace.modelo.staged.restore")
            else:
                text = value_text(CasillaListEntry(change.field.model_copy(update={"value": change.value})), language)
            self._changes[key] = replace(change, text=text, previous_text=self._before(change.field))

    def display(self) -> dict[AddressKey, StagedDisplay]:
        """How each staged change reads on its line."""
        return {
            key: StagedDisplay(
                text=change.text,
                previous_text=change.previous_text,
                concrete_value=change.kind in _FIGURE_KINDS and change.value is not None,
            )
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
        if not field.takes_typed_value:
            return StageRefusal.NOT_EDITABLE
        key = address_key(field.address)
        if field.own_value is not None and comparable_entry(value) == field.own_value:
            self._changes.pop(key, None)
            return None
        self._changes[key] = StagedChange(
            field=field,
            kind=WorkbenchChangeKind.SET,
            value=value,
            text=display,
            previous_text=self._before(field),
            displaces=field_displacement(field),
        )
        return None

    def stage_confirmation(self, field: ModeloFormField) -> StageRefusal | None:
        """Stage an assumed value as the filer's own, without retyping it.

        Only a value the filer types, that nobody is recorded as having
        entered, can be confirmed. A box a source fills is refused, since
        keeping a value over it would replace the source rather than confirm
        it, and so is a box that takes no typed value here.
        """
        if confirmable(field):
            return self.stage_value(field, field.value, self._before(field))
        if field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM and field.value is not None:
            return StageRefusal.NOT_EDITABLE
        return StageRefusal.NOTHING_TO_CONFIRM

    def stage_clear(self, field: ModeloFormField) -> StageRefusal | None:
        """Stage removing a value the filer declared.

        Only the filer's own value can be removed. An assumed value is nobody's:
        the application refuses to empty a box something else fills, so the
        filer confirms it or types another value, 0 included, instead.
        """
        if field.editability is not ModeloFormEditability.EDITABLE_VALUE:
            return StageRefusal.NOT_EDITABLE
        if not field.clearable:
            return StageRefusal.NOTHING_TO_CLEAR
        self._changes[address_key(field.address)] = StagedChange(
            field=field,
            kind=WorkbenchChangeKind.CLEAR,
            value=None,
            text=tr("workspace.modelo.staged.clear"),
            previous_text=self._before(field),
            displaces=ModeloFormDisplacement.FILER,
        )
        return None

    def stage_restore(self, field: ModeloFormField) -> StageRefusal | None:
        """Stage giving a field back to its source."""
        if field.editability not in {
            ModeloFormEditability.OVERRIDABLE_SOURCE,
            ModeloFormEditability.EDITABLE_OVERRIDE,
        }:
            return StageRefusal.NOT_EDITABLE
        if not field.restorable:
            return StageRefusal.NOTHING_TO_RESTORE
        self._changes[address_key(field.address)] = StagedChange(
            field=field,
            kind=WorkbenchChangeKind.RESTORE,
            value=None,
            text=tr("workspace.modelo.staged.restore"),
            previous_text=self._before(field),
            displaces=ModeloFormDisplacement.FILER,
        )
        return None

    def stage_statement(self, form: ModeloWorkForm, statement: ModeloFormCarryAttestation) -> bool:
        """Stage ``statement`` on every box it names; ``False``, staging nothing, when one is not on the form.

        The statement is staged only as ``form`` serves it now: a family it no
        longer serves, or a box it no longer names, is not staged.
        """
        if statement not in form.carry_attestations:
            return False
        placed = statement_fields(form, statement)
        if placed is None:
            return False
        for field in placed:
            self._changes[address_key(field.address)] = StagedChange(
                field=field,
                kind=WorkbenchChangeKind.STATE_ABSENT,
                value=None,
                text=statement.action_words,
                previous_text=self._before(field),
                displaces=field_displacement(field),
                statement=statement,
            )
        return True

    def withdraw_statement(self, statement: ModeloFormCarryAttestation) -> bool:
        """Drop every staged change making a statement of ``statement``'s family; ``False`` when none was staged."""
        keys = [
            key
            for key, change in self._changes.items()
            if change.statement is not None and change.statement.family is statement.family
        ]
        for key in keys:
            del self._changes[key]
        return bool(keys)

    def withdraw_stated(self, form: ModeloWorkForm, field: ModeloFormField) -> StageRefusal | None:
        """Stage withdrawing the statement ``field`` was stated by, on every box of its family at once.

        A family is one statement: withdrawing one of its boxes withdraws them
        all, so no state where only some of them stay stated is ever staged.
        Each box takes whichever withdrawal the form allows it; when one box
        allows none, nothing is staged and its refusal is returned.
        """
        family = field.stated_absent
        if family is None:
            return self._withdraw_stated_prior(form, field)
        members = [member for member in form.fields() if member.stated_absent is family]
        staged = dict(self._changes)
        for member in members:
            refusal = self.stage_clear(member)
            if refusal is not None:
                refusal = self.stage_restore(member)
            if refusal is not None:
                self._changes = staged
                return refusal
        return None

    def _withdraw_stated_prior(self, form: ModeloWorkForm, field: ModeloFormField) -> StageRefusal | None:
        """Withdraw the figure stated on ``field`` for earlier returns: its whole family as the form serves it."""
        stated = field.stated_prior_value
        if stated is None or stated.family_id is None:
            refusal = self.stage_clear(field)
            return refusal if refusal is None else self.stage_restore(field)
        for attestation in form.prior_value_attestations:
            if attestation.family_id == stated.family_id and attestation.withdrawal is not None:
                return self.stage_prior_withdrawal(form, attestation)
        return StageRefusal.NOT_EDITABLE

    def stage_prior_withdrawal(
        self, form: ModeloWorkForm, attestation: ModeloFormPriorValueAttestation
    ) -> StageRefusal | None:
        """Stage the withdrawal the form serves for ``attestation``'s family, on every carry of it at once.

        A family of stated figures is one statement: it is withdrawn whole or not at all. Each carry
        takes whichever withdrawal the form allows it; when one allows none, nothing is staged.
        """
        withdrawal = attestation.withdrawal
        if withdrawal is None or attestation not in form.prior_value_attestations:
            return StageRefusal.NOT_EDITABLE
        placed = binding_fields(form, withdrawal.binding_ids)
        if placed is None:
            return StageRefusal.NOT_EDITABLE
        staged = dict(self._changes)
        for member in placed:
            refusal = self.stage_clear(member)
            if refusal is not None:
                refusal = self.stage_restore(member)
            if refusal is not None:
                self._changes = staged
                return refusal
        return None

    def stages_prior_withdrawal(self, attestation: ModeloFormPriorValueAttestation) -> bool:
        """Whether a withdrawal of ``attestation``'s family is staged."""
        return bool(self._prior_withdrawal_keys(attestation))

    def unstage_prior_withdrawal(self, attestation: ModeloFormPriorValueAttestation) -> bool:
        """Drop every staged change withdrawing ``attestation``'s family; ``False`` when none was staged."""
        keys = self._prior_withdrawal_keys(attestation)
        for key in keys:
            del self._changes[key]
        return bool(keys)

    def _prior_withdrawal_keys(self, attestation: ModeloFormPriorValueAttestation) -> list[AddressKey]:
        withdrawn = (WorkbenchChangeKind.CLEAR, WorkbenchChangeKind.RESTORE)
        return [
            key
            for key, change in self._changes.items()
            if change.kind in withdrawn
            and change.field.stated_prior_value is not None
            and change.field.stated_prior_value.family_id == attestation.family_id
        ]

    def stage_prior_figures(
        self, form: ModeloWorkForm, family_id: str, figures: Mapping[str, tuple[ModeloFormScalar, str]]
    ) -> StageRefusal | None:
        """Stage the figures stated for one family's earlier returns, on every carry of it at once.

        A family is one statement: it is stated whole or not at all. Nothing is staged unless the form
        serves the family now, admits a statement on every carry, holds no figure stated for it, shows
        every carry, and ``figures`` gives each carry one figure (a value and how it reads back).
        """
        members = tuple(item for item in form.prior_value_attestations if item.family_id == family_id)
        if not members or any(item.stated or not item.admitted for item in members):
            return StageRefusal.NOT_EDITABLE
        binding_ids = tuple(item.binding_id for item in members)
        if set(figures) != set(binding_ids) or any(value is None for value, _ in figures.values()):
            return StageRefusal.NOT_EDITABLE
        placed = binding_fields(form, binding_ids)
        if placed is None:
            return StageRefusal.NOT_EDITABLE
        for member, field in zip(members, placed, strict=True):
            value, display = figures[member.binding_id]
            self._changes[address_key(field.address)] = StagedChange(
                field=field,
                kind=WorkbenchChangeKind.STATE_PRIOR_VALUE,
                value=value,
                text=display,
                previous_text=self._before(field),
                displaces=field_displacement(field),
                prior_value=member,
            )
        return None

    def stages_prior_figures(self, family_id: str) -> bool:
        """Whether figures stated for ``family_id``'s earlier returns are staged."""
        return bool(self._prior_figure_keys(family_id))

    def prior_figures(self, family_id: str) -> dict[str, tuple[ModeloFormScalar, str]]:
        """The figures staged for ``family_id``'s earlier returns by carry: each a value and how it reads."""
        return {
            change.prior_value.binding_id: (change.value, change.text)
            for key in self._prior_figure_keys(family_id)
            if (change := self._changes[key]).prior_value is not None
        }

    def unstage_prior_figures(self, family_id: str) -> bool:
        """Drop every staged figure of ``family_id``; ``False`` when none was staged."""
        keys = self._prior_figure_keys(family_id)
        for key in keys:
            del self._changes[key]
        return bool(keys)

    def _prior_figure_keys(self, family_id: str) -> list[AddressKey]:
        return [
            key
            for key, change in self._changes.items()
            if change.prior_value is not None and change.prior_value.family_id == family_id
        ]

    def stages_statement(self, statement: ModeloFormCarryAttestation) -> bool:
        """Whether a statement of ``statement``'s family is staged."""
        return any(
            change.statement is not None and change.statement.family is statement.family
            for change in self._changes.values()
        )

    def rebase(self, form: ModeloWorkForm) -> Rebase:
        """Check every staged change again against ``form``, keeping the ones that still apply."""
        fields = {address_key(field.address): field for field in form.fields()}
        staged = self._changes
        self._changes = {}
        changed: list[StagedChange] = []
        dropped: list[StagedChange] = []
        for key, change in staged.items():
            field = fields.get(key)
            if change.statement is not None:
                if not self._restate(form, change, key):
                    dropped.append(change)
                continue
            if change.prior_value is not None:
                if not self._restate_prior(form, change, key):
                    dropped.append(change)
                continue
            outcome = rebase_outcome(change.held, field)
            if (
                field is None
                or outcome is ModeloFormRebaseOutcome.DROPPED
                or self._restage(change, field) is not None
                or key not in self._changes
            ):
                self._changes.pop(key, None)
                dropped.append(change)
                continue
            if outcome is ModeloFormRebaseOutcome.CHANGED:
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
        lost = {item.prior_value.family_id for item in dropped if item.prior_value is not None}
        for key, change in tuple(self._changes.items()):
            if change.prior_value is not None and change.prior_value.family_id in lost:
                del self._changes[key]
                dropped.append(change)
        return Rebase(changed=tuple(changed), dropped=tuple(dropped))

    def _restate_prior(self, form: ModeloWorkForm, change: StagedChange, key: AddressKey) -> bool:
        """Keep a staged figure only while the form still admits it on its carry for the same earlier returns."""
        stated = change.prior_value
        if stated is None:
            return False
        for served in form.prior_value_attestations:
            if served.binding_id != stated.binding_id or served.family_id != stated.family_id:
                continue
            if served.stated or not served.admitted:
                return False
            placed = binding_fields(form, (served.binding_id,))
            if placed is None or address_key(placed[0].address) != key:
                return False
            self._changes[key] = replace(
                change, field=placed[0], previous_text=self._before(placed[0]), prior_value=served
            )
            return True
        return False

    def _restate(self, form: ModeloWorkForm, change: StagedChange, key: AddressKey) -> bool:
        """Keep a staged statement on its box only while the form still serves its family naming that box."""
        statement = change.statement
        if statement is None:
            return False
        for served in form.carry_attestations:
            if served.family is not statement.family:
                continue
            for field in statement_fields(form, served) or ():
                if address_key(field.address) == key:
                    self._changes[key] = replace(
                        change,
                        field=field,
                        text=served.action_words,
                        previous_text=self._before(field),
                        statement=served,
                    )
                    return True
        return False

    def _restage(self, change: StagedChange, field: ModeloFormField) -> StageRefusal | None:
        if change.kind is WorkbenchChangeKind.SET:
            return self.stage_value(field, change.value, change.text)
        if change.kind is WorkbenchChangeKind.CLEAR:
            return self.stage_clear(field)
        return self.stage_restore(field)

    def acknowledge(self) -> None:
        """Take the marks off the changes the filer has looked at again."""
        self._changes = {key: replace(change, before_changed=False) for key, change in self._changes.items()}

    def revert(self, key: AddressKey) -> bool:
        """Drop the change staged on one address; ``False`` when there was none."""
        return self._changes.pop(key, None) is not None

    def discard(self) -> None:
        """Drop every staged change."""
        self._changes.clear()

    def payload(self) -> tuple[WorkbenchChange, ...]:
        """The typed changes to submit, in staging order."""
        return tuple(change.change for change in self._changes.values())


def statement_fields(form: ModeloWorkForm, statement: ModeloFormCarryAttestation) -> tuple[ModeloFormField, ...] | None:
    """The boxes ``statement`` names, in its order: each the field whose edit goes to a binding it names.

    ``None`` when the form shows a named binding nowhere, so a statement is never staged on part of what it names.
    """
    return binding_fields(form, statement.binding_ids)


def binding_fields(form: ModeloWorkForm, binding_ids: tuple[str, ...]) -> tuple[ModeloFormField, ...] | None:
    """The boxes whose edit goes to each of ``binding_ids``, in that order; ``None`` when the form shows one nowhere."""
    by_binding: dict[str, ModeloFormField] = {}
    for field in form.fields():
        address = edit_address(field)
        if isinstance(address, ModeloFormBindingAddressV1):
            by_binding.setdefault(address.binding_id, field)
    placed = [by_binding[binding_id] for binding_id in binding_ids if binding_id in by_binding]
    return tuple(placed) if len(placed) == len(binding_ids) else None


__all__ = ["Rebase", "StageRefusal", "StagedChange", "WorkbenchEditSession", "binding_fields", "statement_fields"]
