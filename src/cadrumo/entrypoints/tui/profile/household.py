"""The household destination: the people the profile states, and adding or removing one.

Every word about a group, a person or a fact is the one the profile view serves
on its ``family_rows`` stream: group labels, leaf labels and help, answer sets,
the "stated, recorded" sentence of an incomplete group and the words of the add
and remove controls. The screen authors only chrome around them.

A person is added through the group's served add control: the new-person form
offers exactly the group's served leaves, each leaf only while one of the
answers it is served after holds, and sends only the person typed. A person is
removed through the served remove control, named by the ``row_index`` the read
served it at and bound to that read's revision, so a household that moved in
between is refused as a conflict rather than losing whoever holds that index
now. Neither resends the people left alone; the operation composes the set.

A refusal is shown as served through a :class:`RefusalSlot`. A change whose
outcome is unknown stays unknown: it is never reported as saved or as refused,
and further changes wait until the operator reads the household again.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextvars import copy_context
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final, Protocol, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.worker import Worker, WorkerState

from cadrumo_client.transport.profile_mutations import ProfileMutationRunError

from ....application.user_profile.family_rows import (
    ProfileFamilyGroupState,
    ProfileFamilyLeaf,
    ProfileFamilyLeafCondition,
    ProfileFamilyRowAction,
    ProfileViewFamilyGroupItem,
    ProfileViewFamilyRowItem,
)
from ....application.user_profile.presentation import profile_field_shape_hint
from ....core.i18n.render import tr
from ....core.operations import OperationEffect, OperationTerminalCondition
from ..components.language import localized, refresh_localized_widgets
from ..components.theme import tokenised
from ..components.widgets import ContentScroll
from ..refusal.panel import RefusalSlot
from ..refusal.served import ServedRefusalV1, served_refusal
from .client_errors import ProfileManagerCompletedViewUnavailableError, is_profile_edit_conflict
from .overview_contracts import REQUIRED_MARK, ROW_INDEX_SEPARATOR

HOUSEHOLD_TITLE_LOCALE_KEY: Final = "flows.manager.household.title"
_READING_LOCALE_KEY: Final = "flows.manager.household.reading"
_READ_FAILED_LOCALE_KEY: Final = "flows.manager.household.read_failed"
_READ_AGAIN_LOCALE_KEY: Final = "flows.manager.household.read_again"
_CLOSE_LOCALE_KEY: Final = "flows.manager.household.close"
_FULL_LOCALE_KEY: Final = "flows.manager.household.full"
_UNKNOWN_OUTCOME_LOCALE_KEY: Final = "flows.manager.household.unknown_outcome"
_STATE_LOCALE_KEYS: Final[Mapping[ProfileFamilyGroupState, str]] = {
    ProfileFamilyGroupState.UNKNOWN: "flows.manager.household.state_unknown",
    ProfileFamilyGroupState.NONE_DECLARED: "flows.manager.household.state_none_declared",
    ProfileFamilyGroupState.NOT_SERVED: "flows.manager.household.state_not_served",
}
_SAVED_LOCALE_KEY: Final = "flows.manager.edit.saved"
_NO_CHANGE_LOCALE_KEY: Final = "flows.manager.edit.no_change"
_CONFLICT_LOCALE_KEY: Final = "flows.manager.edit.conflict"
_WRITE_FAILED_LOCALE_KEY: Final = "flows.manager.edit.write_failed"
_COMPLETED_UNREAD_LOCALE_KEY: Final = "flows.manager.edit.completed_refresh_unavailable"
_REQUIRED_BLANK_LOCALE_KEY: Final = "flows.manager.edit.required_blank"
_CANCEL_LOCALE_KEY: Final = "flows.manager.edit.cancel"
_SAVE_LOCALE_KEY: Final = "flows.manager.edit.save"

_MASK: Final = "••••••••"
"""What a hidden fact shows in place of its value: a glyph run, not copy."""

_FACT_SEPARATOR: Final = "; "
_LABEL_SEPARATOR: Final = ": "

_HOUSEHOLD_CSS: Final = tokenised("""
#household-dialog {
    border: $cadrumo-radius-overlay $accent;
    background: $surface;
    padding: $cadrumo-space-0 $cadrumo-space-1;
    width: 100%;
    height: auto;
    max-height: 100%;
}
#household-body { height: auto; max-height: $cadrumo-modal-max-height; }
#household-title { text-style: bold; }
#household-status { color: $text-muted; }
#household-status.household-unknown { color: $warning; text-style: bold; }
.household-group { height: auto; margin-top: $cadrumo-space-1; }
.household-group-label { text-style: bold; }
.household-group-note { color: $text-muted; }
.household-row { height: auto; }
.household-row Static { width: 1fr; }
.household-row Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
#household-actions { height: auto; align-horizontal: right; margin: $cadrumo-space-0; }
#household-actions Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
""")

_PERSON_CSS: Final = tokenised("""
#household-person-dialog {
    border: $cadrumo-radius-overlay $accent;
    background: $surface;
    padding: $cadrumo-space-0 $cadrumo-space-1;
    width: 100%;
    height: auto;
    max-height: 100%;
}
#household-person-body { height: auto; max-height: $cadrumo-modal-max-height; }
#household-person-title { text-style: bold; }
.household-leaf { height: auto; margin-bottom: $cadrumo-space-1; }
.household-leaf-help { color: $text-muted; }
#household-person-refusal { color: $error; text-style: bold; }
#household-person-actions { height: auto; align-horizontal: right; margin: $cadrumo-space-0; }
#household-person-actions Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
""")


@dataclass(frozen=True, slots=True)
class HouseholdGroupView:
    """One served group and the people it stores, in the order served."""

    group: ProfileViewFamilyGroupItem
    rows: tuple[ProfileViewFamilyRowItem, ...]


@dataclass(frozen=True, slots=True)
class HouseholdView:
    """The household at the profile revision it was read at, which a change names as its baseline."""

    profile_id: str
    record_revision: int
    content_digest: str
    groups: tuple[HouseholdGroupView, ...]


@dataclass(frozen=True, slots=True)
class HouseholdRowChange:
    """One person added or removed through a served control's registered operation.

    Exactly one of ``add_row`` (the leaves typed for the new person) and
    ``remove_row_index`` (the index a read served) is set.
    """

    operation_id: str
    expected_revision: int
    expected_content_digest: str
    add_row: Mapping[str, str] | None = None
    remove_row_index: str | None = None


class HouseholdPort(Protocol):
    """The host's doors for the household, bound to one exact profile session.

    ``read`` and ``change`` block on the runtime and run off the event loop.
    ``change`` returns the household as storage holds it after the change.
    """

    def read(self) -> HouseholdView:
        """Read the household in the current output language."""
        ...

    def change(self, change: HouseholdRowChange, /) -> HouseholdView:
        """Submit one served add or remove and read the household again."""
        ...

    def accepts(self, operation_id: str, /) -> bool:
        """Whether this host submits the registered operation a served control names."""
        ...


class HouseholdOutcome(StrEnum):
    """How a finished change is told to the operator; each is drawn apart."""

    SAVED = "saved"
    REFUSED = "refused"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"
    COMPLETED_UNREAD = "completed_unread"
    FAILED = "failed"


def household_change_outcome(error: BaseException | None) -> HouseholdOutcome:
    """Classify a finished change by what is known to have been written.

    A refusal or a failure the runtime observed with no effect wrote nothing.
    An operation observed to complete whose household could not be read again
    is completed. Any other submitted operation may have written: its effect
    was unknown, partial, or never observed.
    """
    if error is None:
        return HouseholdOutcome.SAVED
    if isinstance(error, ProfileManagerCompletedViewUnavailableError):
        return HouseholdOutcome.COMPLETED_UNREAD
    if is_profile_edit_conflict(error):
        return HouseholdOutcome.CONFLICT
    if isinstance(error, ProfileMutationRunError):
        settled_without_effect = error.effect is OperationEffect.NONE and error.terminal_condition in {
            OperationTerminalCondition.REFUSED,
            OperationTerminalCondition.FAILED,
        }
        return HouseholdOutcome.REFUSED if settled_without_effect else HouseholdOutcome.UNKNOWN
    return HouseholdOutcome.FAILED


def household_refusal(error: BaseException | None) -> ServedRefusalV1 | None:
    """The refusal the operation served for a change that wrote nothing, or ``None``."""
    if isinstance(error, ProfileMutationRunError):
        return served_refusal(error.detail, refusal_code=error.reason)
    return None


def submitted_operation(action: ProfileFamilyRowAction | None, accepts: Callable[[str], bool]) -> str | None:
    """The one registered operation a served control submits, or ``None`` when this host cannot send it."""
    if action is None or len(action.target_operation_ids) != 1:
        return None
    operation_id = action.target_operation_ids[0]
    return operation_id if accepts(operation_id) else None


def _holds(condition: ProfileFamilyLeafCondition, answer: str) -> bool:
    if condition.equals is not None:
        return answer == condition.equals
    if condition.contains is not None:
        return condition.contains in (token.strip() for token in answer.split(","))
    return False


def shown_leaves(leaves: Sequence[ProfileFamilyLeaf], answers: Mapping[str, str]) -> tuple[ProfileFamilyLeaf, ...]:
    """The leaves asked of a person with these answers, in served order.

    A leaf served with no condition is always asked; any other while one of its
    conditions holds on a leaf that is itself asked. An answer to a leaf no
    longer asked counts for nothing.
    """
    by_key = {leaf.leaf: leaf for leaf in leaves}
    asked: dict[str, bool] = {}

    def is_asked(leaf: ProfileFamilyLeaf, seen: frozenset[str]) -> bool:
        if leaf.leaf in asked:
            return asked[leaf.leaf]
        if leaf.leaf in seen:
            return False
        shown = not leaf.shown_when or any(
            condition.leaf in by_key
            and is_asked(by_key[condition.leaf], seen | {leaf.leaf})
            and _holds(condition, answers.get(condition.leaf, "").strip())
            for condition in leaf.shown_when
        )
        asked[leaf.leaf] = shown
        return shown

    return tuple(leaf for leaf in leaves if is_asked(leaf, frozenset()))


def person_text(group: ProfileViewFamilyGroupItem, row: ProfileViewFamilyRowItem, number: int) -> str:
    """One person as a line: its place, then each stated fact under its served label, hidden ones masked."""
    leaves = {leaf.leaf: leaf for leaf in group.leaves}
    facts: list[str] = []
    for fact in row.facts:
        leaf = leaves.get(fact.leaf)
        if leaf is None:
            continue
        value = (
            _MASK
            if fact.masked
            else next((choice.label for choice in leaf.choices if choice.value == fact.value), fact.value)
        )
        facts.append(f"{leaf.label}{_LABEL_SEPARATOR}{value}")
    return f"{number}{ROW_INDEX_SEPARATOR}{_FACT_SEPARATOR.join(facts)}"


def _group_note(group: ProfileViewFamilyGroupItem) -> str | None:
    if group.state is ProfileFamilyGroupState.INCOMPLETE:
        return group.incomplete_words
    key = _STATE_LOCALE_KEYS.get(group.state)
    return None if key is None else tr(key)


class HouseholdPersonScreen(ModalScreen[dict[str, str] | None]):
    """The form of one new person: the group's served leaves, each while it is asked."""

    DEFAULT_CSS = _PERSON_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, group: ProfileViewFamilyGroupItem, title: str) -> None:
        """Hold the served group whose leaves are the form, and the served words that title it."""
        super().__init__()
        self._form_group = group
        self._form_title = title

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="household-person-dialog"):
            yield Label(self._form_title, id="household-person-title", markup=False)
            with ContentScroll(id="household-person-body"):
                for index, leaf in enumerate(self._form_group.leaves):
                    with Vertical(id=f"household-leaf-{index}", classes="household-leaf"):
                        yield Label(f"{leaf.label}{REQUIRED_MARK if leaf.required else ''}", markup=False)
                        if leaf.help is not None and leaf.help.strip():
                            yield Static(leaf.help, classes="household-leaf-help", markup=False)
                        if leaf.choices:
                            yield OptionList(*(choice.label for choice in leaf.choices), id=f"household-option-{index}")
                        else:
                            yield Input(
                                placeholder=profile_field_shape_hint(leaf.field_type), id=f"household-input-{index}"
                            )
            yield Static(id="household-person-refusal", markup=False)
            with Horizontal(id="household-person-actions"):
                yield localized(Button(tr(_CANCEL_LOCALE_KEY), id="household-person-cancel"), _CANCEL_LOCALE_KEY)
                yield localized(
                    Button(tr(_SAVE_LOCALE_KEY), id="household-person-save", classes="-primary"), _SAVE_LOCALE_KEY
                )

    def on_mount(self) -> None:
        """Start with no answer chosen, so every answer is the operator's, and ask what is asked now."""
        for index, leaf in enumerate(self._form_group.leaves):
            if leaf.choices:
                self.query_one(f"#household-option-{index}", OptionList).highlighted = None
        self._show_asked()

    def answers(self) -> dict[str, str]:
        """What the operator has answered so far, by leaf, blanks included."""
        answers: dict[str, str] = {}
        for index, leaf in enumerate(self._form_group.leaves):
            if leaf.choices:
                highlighted = self.query_one(f"#household-option-{index}", OptionList).highlighted
                answers[leaf.leaf] = "" if highlighted is None else leaf.choices[highlighted].value
            else:
                answers[leaf.leaf] = self.query_one(f"#household-input-{index}", Input).value
        return answers

    def asked(self) -> tuple[ProfileFamilyLeaf, ...]:
        """The leaves asked of this person with what is answered now."""
        return shown_leaves(self._form_group.leaves, self.answers())

    def _show_asked(self) -> None:
        asked = {leaf.leaf for leaf in self.asked()}
        for index, leaf in enumerate(self._form_group.leaves):
            self.query_one(f"#household-leaf-{index}", Vertical).display = leaf.leaf in asked

    def on_input_changed(self, _event: Input.Changed) -> None:
        """Ask again after a typed answer changes."""
        self._show_asked()

    def on_option_list_option_highlighted(self, _event: OptionList.OptionHighlighted) -> None:
        """Ask again after a chosen answer changes."""
        self._show_asked()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Submit the person, or leave without adding anyone."""
        if event.button.id == "household-person-save":
            self._submit()
        else:
            self.dismiss(None)

    def _submit(self) -> None:
        answers = self.answers()
        asked = self.asked()
        blank = next((leaf for leaf in asked if leaf.required and not answers[leaf.leaf].strip()), None)
        if blank is not None:
            self.query_one("#household-person-refusal", Static).update(
                tr(_REQUIRED_BLANK_LOCALE_KEY, field=blank.label)
            )
            return
        person = {leaf.leaf: answers[leaf.leaf].strip() for leaf in asked if answers[leaf.leaf].strip()}
        if not person:
            return
        self.dismiss(person)

    def action_cancel(self) -> None:
        """Leave without adding anyone."""
        self.dismiss(None)

    async def refresh_language(self) -> None:
        """Reword the chrome; the served words stay those of the read the form was opened from."""
        refresh_localized_widgets(self)


class HouseholdRemoveScreen(ModalScreen[bool]):
    """Ask whether to take one served person out, in the served words of the remove control."""

    DEFAULT_CSS = _PERSON_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, words: str, person: str) -> None:
        """Hold the served remove words and the person's line as the household read showed it."""
        super().__init__()
        self._remove_words = words
        self._remove_person = person

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="household-person-dialog"):
            yield Label(self._remove_words, id="household-person-title", markup=False)
            yield Static(self._remove_person, id="household-remove-person", markup=False)
            with Horizontal(id="household-person-actions"):
                yield localized(Button(tr(_CANCEL_LOCALE_KEY), id="household-remove-cancel"), _CANCEL_LOCALE_KEY)
                yield Button(self._remove_words, id="household-remove-confirm", classes="-error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Return whether the operator confirmed the removal."""
        self.dismiss(event.button.id == "household-remove-confirm")

    def action_cancel(self) -> None:
        """Decline the removal."""
        self.dismiss(False)

    async def refresh_language(self) -> None:
        """Reword the chrome."""
        refresh_localized_widgets(self)


class HouseholdScreen(ModalScreen[bool | None]):
    """The people the profile states, with the served controls that add or remove one.

    Dismissed with whether a change landed or may have landed, so the page
    that opened it reads the profile again.
    """

    DEFAULT_CSS = _HOUSEHOLD_CSS
    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]

    def __init__(self, port: HouseholdPort) -> None:
        """Bind the host's household doors; nothing is read until the screen is mounted."""
        super().__init__()
        self._port = port
        self._view: HouseholdView | None = None
        self._household_job: Worker[HouseholdView] | None = None
        self._job_is_change = False
        self._unsettled = False
        """A change whose outcome is unknown: no other change is sent until the household is read again."""
        self._touched = False
        """Whether a change landed or may have landed while the screen was open."""

    @property
    def view(self) -> HouseholdView | None:
        """The household as last read, or ``None`` before the first read."""
        return self._view

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="household-dialog"):
            yield localized(Label(tr(HOUSEHOLD_TITLE_LOCALE_KEY), id="household-title"), HOUSEHOLD_TITLE_LOCALE_KEY)
            yield Static(id="household-status", markup=False)
            yield RefusalSlot(id="household-refusal")
            with ContentScroll(id="household-body"):
                yield Vertical(id="household-groups")
            with Horizontal(id="household-actions"):
                yield localized(Button(tr(_READ_AGAIN_LOCALE_KEY), id="household-read"), _READ_AGAIN_LOCALE_KEY)
                yield localized(Button(tr(_CLOSE_LOCALE_KEY), id="household-close"), _CLOSE_LOCALE_KEY)

    def on_mount(self) -> None:
        """Read the household off the event loop."""
        self._read()

    def _status(self, text: str, *, unknown: bool = False) -> None:
        status = self.query_one("#household-status", Static)
        status.update(text)
        status.set_class(unknown, "household-unknown")

    def _start(self, job: Callable[[], HouseholdView], *, change: bool) -> None:
        context = copy_context()
        self._job_is_change = change
        self._household_job = self.run_worker(
            lambda: context.run(job),
            name="profile-household",
            group="profile-household",
            exit_on_error=False,
            thread=True,
        )
        self._lock_controls()

    def _read(self) -> None:
        if self._household_job is not None:
            return
        self.query_one("#household-refusal", RefusalSlot).show(None)
        if not self._unsettled:
            self._status(tr(_READING_LOCALE_KEY))
        self._start(self._port.read, change=False)

    def _submit(self, change: HouseholdRowChange) -> None:
        if self._household_job is not None or self._unsettled:
            return
        self.query_one("#household-refusal", RefusalSlot).show(None)
        self._status("")
        self._start(lambda: self._port.change(change), change=True)

    async def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Land a finished read or change on the UI task."""
        job = self._household_job
        if job is None or event.worker is not job:
            return
        if event.state not in {WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED}:
            return
        self._household_job = None
        if self._job_is_change:
            await self._settle_change(job)
        else:
            await self._settle_read(job)

    async def _settle_read(self, job: Worker[HouseholdView]) -> None:
        if job.state is WorkerState.SUCCESS and job.result is not None:
            self._view = job.result
            # The household now shows what storage holds, so the unknown
            # notice and the lock end with this read; a failed read keeps both.
            self._unsettled = False
            self._status("")
            await self._draw()
            return
        if not self._unsettled:
            self._status(tr(_READ_FAILED_LOCALE_KEY))
        self._lock_controls()

    async def _settle_change(self, job: Worker[HouseholdView]) -> None:
        error = None if job.state is WorkerState.SUCCESS and job.result is not None else job.error
        outcome = household_change_outcome(error)
        if outcome is HouseholdOutcome.SAVED and job.result is not None:
            changed = self._view is None or job.result.record_revision > self._view.record_revision
            self._touched = self._touched or changed
            self._view = job.result
            self._status(tr(_SAVED_LOCALE_KEY if changed else _NO_CHANGE_LOCALE_KEY))
            await self._draw()
            return
        if outcome is HouseholdOutcome.REFUSED:
            refusal = household_refusal(error)
            if refusal is not None:
                self.query_one("#household-refusal", RefusalSlot).show(refusal)
            else:
                self._status(tr(_WRITE_FAILED_LOCALE_KEY))
            self._lock_controls()
            return
        if outcome is HouseholdOutcome.CONFLICT:
            self._status(tr(_CONFLICT_LOCALE_KEY))
            self._read()
            return
        if outcome is HouseholdOutcome.COMPLETED_UNREAD:
            self._touched = True
            self._status(tr(_COMPLETED_UNREAD_LOCALE_KEY))
            self._lock_controls()
            return
        if outcome is HouseholdOutcome.UNKNOWN:
            self._touched = True
            self._unsettled = True
            self._status(tr(_UNKNOWN_OUTCOME_LOCALE_KEY), unknown=True)
            self._lock_controls()
            return
        self._status(tr(_WRITE_FAILED_LOCALE_KEY))
        self._lock_controls()

    async def _draw(self) -> None:
        body = self.query_one("#household-groups", Vertical)
        await body.remove_children()
        view = self._view
        if view is None:
            return
        for group_index, entry in enumerate(view.groups):
            await body.mount(self._group_widget(group_index, entry))
        self._lock_controls()

    def _group_widget(self, group_index: int, entry: HouseholdGroupView) -> Vertical:
        group = entry.group
        children: list[Static | Horizontal | Button] = [
            Static(group.label, classes="household-group-label", markup=False)
        ]
        note = _group_note(group)
        if note is not None and note.strip():
            children.append(Static(note, classes="household-group-note", markup=False))
        remove_operation = submitted_operation(group.remove_row_action, self._port.accepts)
        for number, row in enumerate(entry.rows, start=1):
            line: list[Static | Button] = [Static(person_text(group, row, number), markup=False)]
            if remove_operation is not None and group.remove_row_action is not None:
                line.append(
                    Button(
                        group.remove_row_action.action_words,
                        id=f"household-remove-{group_index}-{row.row_index}",
                        classes="household-control",
                        compact=True,
                    )
                )
            children.append(Horizontal(*line, classes="household-row"))
        add_operation = submitted_operation(group.add_row_action, self._port.accepts)
        if add_operation is not None and group.add_row_action is not None:
            children.append(
                Button(
                    group.add_row_action.action_words,
                    id=f"household-add-{group_index}",
                    classes="household-control",
                    compact=True,
                )
            )
        elif group.max_rows is not None and len(entry.rows) >= group.max_rows:
            children.append(Static(tr(_FULL_LOCALE_KEY), classes="household-group-note", markup=False))
        return Vertical(*children, classes="household-group")

    def _lock_controls(self) -> None:
        busy = self._household_job is not None
        for button in self.query(".household-control").results(Button):
            button.disabled = busy or self._unsettled
        self.query_one("#household-read", Button).disabled = busy

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route the screen's own controls and the served add and remove controls."""
        button_id = event.button.id or ""
        if button_id == "household-close":
            self.action_close()
        elif button_id == "household-read":
            self._read()
        elif button_id.startswith("household-add-"):
            self._open_add(int(button_id.removeprefix("household-add-")))
        elif button_id.startswith("household-remove-"):
            group_index, row_index = button_id.removeprefix("household-remove-").split("-", 1)
            self._open_remove(int(group_index), row_index)

    def _open_add(self, group_index: int) -> None:
        view = self._view
        if view is None or self._household_job is not None or self._unsettled:
            return
        group = view.groups[group_index].group
        operation_id = submitted_operation(group.add_row_action, self._port.accepts)
        if operation_id is None or group.add_row_action is None:
            return

        def _added(person: dict[str, str] | None) -> None:
            current = self._view
            if person is None or current is None:
                return
            self._submit(
                HouseholdRowChange(
                    operation_id=operation_id,
                    expected_revision=current.record_revision,
                    expected_content_digest=current.content_digest,
                    add_row=person,
                )
            )

        self.app.push_screen(HouseholdPersonScreen(group, group.add_row_action.action_words), _added)

    def _open_remove(self, group_index: int, row_index: str) -> None:
        view = self._view
        if view is None or self._household_job is not None or self._unsettled:
            return
        entry = view.groups[group_index]
        group = entry.group
        operation_id = submitted_operation(group.remove_row_action, self._port.accepts)
        place = next((number for number, row in enumerate(entry.rows, start=1) if row.row_index == row_index), None)
        if operation_id is None or group.remove_row_action is None or place is None:
            return
        row = entry.rows[place - 1]

        def _confirmed(confirmed: bool | None) -> None:
            # Bound to the read that served this index: a household that moved
            # since is refused as a conflict, never a different person removed.
            if confirmed is True:
                self._submit(
                    HouseholdRowChange(
                        operation_id=operation_id,
                        expected_revision=view.record_revision,
                        expected_content_digest=view.content_digest,
                        remove_row_index=row.row_index,
                    )
                )

        self.app.push_screen(
            HouseholdRemoveScreen(group.remove_row_action.action_words, person_text(group, row, place)), _confirmed
        )

    def action_close(self) -> None:
        """Leave, unless a change is still landing: its outcome must be seen."""
        if self._household_job is not None and self._job_is_change:
            return
        self.dismiss(self._touched)

    async def refresh_language(self) -> None:
        """Reword the chrome and read the household again for its served words."""
        refresh_localized_widgets(self)
        self._read()


__all__ = [
    "HOUSEHOLD_TITLE_LOCALE_KEY",
    "HouseholdGroupView",
    "HouseholdOutcome",
    "HouseholdPersonScreen",
    "HouseholdPort",
    "HouseholdRemoveScreen",
    "HouseholdRowChange",
    "HouseholdScreen",
    "HouseholdView",
    "household_change_outcome",
    "household_refusal",
    "person_text",
    "shown_leaves",
    "submitted_operation",
]
