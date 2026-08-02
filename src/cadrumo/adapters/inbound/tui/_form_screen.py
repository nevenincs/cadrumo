"""One editable page of fields, for the surfaces that are not the whole profile.

The profile manager answers "what does my profile hold"; some doors ask a
much smaller question — who represents me, who are my descendants — and
used to answer it with a paged flow: one question per screen, next, next,
back, submit. That paradigm is being retired, and the replacement is the
manager's: put the fields on one page, let the operator edit any of them
in any order, and commit when they say so.

This module is that page, generalised. A caller declares a
:class:`FormField` per value it wants, optionally validates each one, and
receives the collected values or ``None`` if the operator walked away.
Nothing here knows what a NIF or a descendant is: field kinds, labels,
choices and validation all arrive from the caller, so the same screen
serves any bounded field set without growing a branch per door.

The screen owns no application logic — it is the same injected-door
arrangement :class:`~cadrumo.adapters.inbound.tui.ProfileManagerApp` uses,
for the same reason: an adapter renders and reports intent, and the entry
point composes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, override

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Input, Label, OptionList, SelectionList, Static

from ....core.i18n import tr
from ._theme import BASE_CSS, ContentScroll, install_cadrumo_themes, toggle_appearance

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence


class FormFieldKind(StrEnum):
    """How one field is edited."""

    TEXT = "text"
    """A free-text value typed into an input."""

    MULTI_CHOICE = "multi_choice"
    """Any number of values picked from a fixed list, stored comma-separated."""

    SINGLE_CHOICE = "single_choice"
    """Exactly one value picked from a fixed list.

    Also how a yes/no question is asked: two named options read better on a
    page of mixed fields than a checkbox whose meaning depends on which row
    the cursor happens to be on.
    """


@dataclass(frozen=True, slots=True)
class FormChoice:
    """One selectable option: the token stored, and the words shown."""

    value: str
    label: str


@dataclass(frozen=True, slots=True)
class FormField:
    """One value the page collects.

    ``validate`` returns a refusal to show, or ``None`` to accept. It runs
    when the operator leaves the edit dialog, so a bad value is caught
    where it was typed rather than at submit, when they have forgotten
    which field it came from.
    """

    key: str
    label: str
    value: str = ""
    kind: FormFieldKind = FormFieldKind.TEXT
    choices: tuple[FormChoice, ...] = ()
    hint: str = ""
    validate: Callable[[str], str | None] | None = None
    """Per-field check, owned by the caller — this screen has no opinion on
    what any particular value means."""


@dataclass(frozen=True, slots=True)
class FormPage:
    """The whole page: a title, a section heading, and the fields."""

    title: str
    section: str
    fields: tuple[FormField, ...] = field(default_factory=tuple)


_MULTI_CHOICE_SEPARATOR = ","
"""Token separator for a multi-choice value, matching the CHECKBOX
convention the profile facts already store."""


_EDIT_DIALOG_CSS = """
#edit-dialog {
    border: thick $accent;
    background: $surface;
    padding: 1 3;
    width: 60%;
    height: auto;
}
#edit-label { text-style: bold; }
#edit-path { color: $text-muted; margin: 0 0 1 0; }
#edit-refusal { color: $error; }
#edit-dialog Input { margin: 0 0 1 0; }
#edit-actions { height: auto; align-horizontal: right; margin: 1 0 0 0; }
#edit-actions Button { margin: 0 0 0 2; }
"""
"""Dialog styling carried by the edit screens themselves.

These rules used to live on the host application's ``CSS``, which was
enough while the only host was :class:`FormApp`. The page is now also
pushed into the profile manager, and a dialog that took its appearance
from whichever application happened to be hosting it would render
unstyled in the second one. Carrying the rules on the screens makes them
self-sufficient in any host.
"""


class TextEditScreen(ModalScreen[str | None]):
    """Type one text value. Dismisses with the new value, or ``None``."""

    DEFAULT_CSS = _EDIT_DIALOG_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, field: FormField) -> None:
        super().__init__()
        self._field = field

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="edit-dialog"):
            yield Label(self._field.label, id="edit-label")
            if self._field.hint:
                yield Static(self._field.hint, id="edit-path")
            yield Input(value=self._field.value, id="edit-input")
            yield Static(id="edit-refusal")
            with Horizontal(id="edit-actions"):
                yield Button(tr("flows.manager.edit.cancel"), id="btn-edit-cancel")
                yield Button(tr("flows.manager.edit.save"), id="btn-edit-save", classes="-primary")

    def on_mount(self) -> None:
        self.query_one("#edit-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-edit-save":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        """Accept the typed value, or hold the dialog open showing why not."""
        candidate = self.query_one("#edit-input", Input).value
        refusal = self._field.validate(candidate) if self._field.validate is not None else None
        if refusal is not None:
            self.query_one("#edit-refusal", Static).update(refusal)
            return
        self.dismiss(candidate)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ChoiceEditScreen(ModalScreen[str | None]):
    """Pick any number of options. Dismisses with a comma-joined token list."""

    DEFAULT_CSS = _EDIT_DIALOG_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, field: FormField) -> None:
        super().__init__()
        self._field = field

    @override
    def compose(self) -> ComposeResult:
        selected = {token for token in self._field.value.split(_MULTI_CHOICE_SEPARATOR) if token}
        with Vertical(id="edit-dialog"):
            yield Label(self._field.label, id="edit-label")
            if self._field.hint:
                yield Static(self._field.hint, id="edit-path")
            yield SelectionList[str](
                *[(choice.label, choice.value, choice.value in selected) for choice in self._field.choices],
                id="edit-choices",
            )
            with Horizontal(id="edit-actions"):
                yield Button(tr("flows.manager.edit.cancel"), id="btn-edit-cancel")
                yield Button(tr("flows.manager.edit.save"), id="btn-edit-save", classes="-primary")

    def on_mount(self) -> None:
        self.query_one("#edit-choices", SelectionList).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "btn-edit-save":
            self.dismiss(None)
            return
        picked = self.query_one("#edit-choices", SelectionList).selected
        self.dismiss(_MULTI_CHOICE_SEPARATOR.join(str(token) for token in picked))


class OneChoiceEditScreen(ModalScreen[str | None]):
    """Pick exactly one option. Dismisses with its token."""

    DEFAULT_CSS = _EDIT_DIALOG_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, field: FormField) -> None:
        super().__init__()
        self._field = field

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="edit-dialog"):
            yield Label(self._field.label, id="edit-label")
            if self._field.hint:
                yield Static(self._field.hint, id="edit-path")
            yield OptionList(*[choice.label for choice in self._field.choices], id="edit-options")
            with Horizontal(id="edit-actions"):
                yield Button(tr("flows.manager.edit.cancel"), id="btn-edit-cancel")
                yield Button(tr("flows.manager.edit.save"), id="btn-edit-save", classes="-primary")

    def on_mount(self) -> None:
        options = self.query_one("#edit-options", OptionList)
        current = next(
            (index for index, choice in enumerate(self._field.choices) if choice.value == self._field.value),
            None,
        )
        if current is not None:
            options.highlighted = current
        options.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "btn-edit-save":
            self.dismiss(None)
            return
        self._dismiss_highlighted()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self._dismiss_highlighted()

    def _dismiss_highlighted(self) -> None:
        highlighted = self.query_one("#edit-options", OptionList).highlighted
        if highlighted is None:
            self.dismiss(None)
            return
        self.dismiss(self._field.choices[highlighted].value)

    def action_cancel(self) -> None:
        self.dismiss(None)


def _edit_screen_for(field: FormField) -> ModalScreen[str | None]:
    """Return the dialog that edits one field, by its declared kind."""
    match field.kind:
        case FormFieldKind.MULTI_CHOICE:
            return ChoiceEditScreen(field)
        case FormFieldKind.SINGLE_CHOICE:
            return OneChoiceEditScreen(field)
        case FormFieldKind.TEXT:
            return TextEditScreen(field)


class FormScreen(Screen["Mapping[str, str] | None"]):
    """The editable field page itself, as a screen any host can push.

    A plain screen rather than a modal one: the modal styling centres its
    content and tints whatever lies beneath, which suits the small
    single-value dialogs above but not this. The page is a whole surface
    in its own right, so it covers its host completely and keeps the
    full-width layout it had when it was an application.

    The page began life fused to :class:`FormApp`, which was sufficient
    while the only way to reach it was to start an application for it. The
    profile manager now offers the same doors from inside an application
    that is already running, where starting a second one is impossible:
    an application owns an event loop, and starting one from a thread that
    already has a running loop raises rather than nesting.

    Separating the page from its host is what lets both reach it. The
    standalone entry point keeps its own application; the manager pushes
    this screen onto the one it is already running. That leaves one page
    implementation and two hosts, rather than a copy per host which would
    drift apart the first time either one changed.
    """

    DEFAULT_CSS = """
    #form-table { height: auto; width: 100%; background: $surface; }
    #form-refusal { color: $error; margin: 1 0 0 0; }
    #form-actions { height: auto; align-horizontal: right; margin: 1 0 0 0; }
    #form-actions Button { margin: 0 0 0 2; }
    """

    BINDINGS: ClassVar = [Binding("escape", "abandon", "", show=False)]

    def __init__(
        self,
        page: FormPage,
        *,
        rebuild: Callable[[Mapping[str, str]], FormPage] | None = None,
    ) -> None:
        super().__init__()
        self._page = page
        self._rebuild = rebuild
        """Recomputes the field list after an edit, for a page whose shape
        depends on its own answers — a descendant count deciding how many
        children to ask about. ``None`` for a page of fixed shape."""
        self._values: dict[str, str] = {field.key: field.value for field in page.fields}
        self.collected: Mapping[str, str] | None = None
        """The committed values, or ``None`` when the operator left without
        committing. Callers read this rather than catching an exception,
        because abandoning is an ordinary choice."""

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="form-banner", classes="cadrumo-banner")
        with (
            ContentScroll(classes="cadrumo-scroll"),
            Vertical(classes="cadrumo-column"),
            Vertical(id="form-body", classes="cadrumo-panel"),
        ):
            yield DataTable(id="form-table", cursor_type="row", zebra_stripes=True)
            yield Static(id="form-refusal")
            with Horizontal(id="form-actions"):
                yield Button(tr("flows.manager.edit.cancel"), id="btn-form-cancel")
                yield Button(tr("flows.manager.edit.save"), id="btn-form-save", classes="-primary")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#form-banner", Static).update(self._page.title)
        self.query_one("#form-body", Vertical).border_title = self._page.section
        table: DataTable[str] = self.query_one("#form-table", DataTable)
        table.add_columns(tr("flows.manager.column.field"), tr("flows.manager.column.value"))
        self._render_rows()

    def _render_rows(self) -> None:
        """Rebuild the row set from the current field list and values.

        Named for the rows rather than for rendering because ``_render``
        belongs to Textual: a widget's is what produces its visual, and a
        screen that shadowed it with a table rebuild returning ``None``
        would fail to draw at all. Harmless while this page was an
        application, which has no such method — and precisely the kind of
        collision that only appears once the page becomes a screen.
        """
        table: DataTable[str] = self.query_one("#form-table", DataTable)
        table.clear()
        for form_field in self._page.fields:
            table.add_row(form_field.label, self._values.get(form_field.key, ""), key=form_field.key)

    def _field(self, key: str) -> FormField | None:
        return next((form_field for form_field in self._page.fields if form_field.key == key), None)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value
        if key is None:
            return
        form_field = self._field(str(key))
        if form_field is None:
            return
        current = form_field.__class__(
            key=form_field.key,
            label=form_field.label,
            value=self._values.get(form_field.key, ""),
            kind=form_field.kind,
            choices=form_field.choices,
            hint=form_field.hint,
            validate=form_field.validate,
        )
        screen = _edit_screen_for(current)
        # The stack belongs to the application, not to a screen on it, so
        # the dialog is pushed through the host rather than by this page.
        self.app.push_screen(screen, self._accept_for(current.key))

    def _accept_for(self, key: str) -> Callable[[str | None], None]:
        def _accept(value: str | None) -> None:
            if value is None:
                return
            self._values[key] = value
            if self._rebuild is not None:
                self._page = self._rebuild(dict(self._values))
                # Fields the rebuild introduced start from their declared
                # value; ones it dropped stop being collected, so a shrunk
                # count cannot commit a stale child.
                self._values = {
                    form_field.key: self._values.get(form_field.key, form_field.value)
                    for form_field in self._page.fields
                }
            self._render_rows()

        return _accept

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-form-save":
            self.action_commit()
        elif event.button.id == "btn-form-cancel":
            self.action_abandon()

    def action_commit(self) -> None:
        """Re-check every field, then hand the values back.

        Validation runs again here rather than trusting the per-edit pass:
        a field the operator never opened has never been checked, and a
        rebuild can introduce fields that were never edited at all.
        """
        for form_field in self._page.fields:
            if form_field.validate is None:
                continue
            refusal = form_field.validate(self._values.get(form_field.key, ""))
            if refusal is not None:
                self.query_one("#form-refusal", Static).update(f"{form_field.label}: {refusal}")
                return
        self.collected = dict(self._values)
        self.dismiss(self.collected)

    def action_abandon(self) -> None:
        self.collected = None
        self.dismiss(None)


class FormApp(App["Mapping[str, str] | None"]):
    """Standalone host for :class:`FormScreen`.

    Everything that makes the page a page lives on the screen; this exists
    only to give it an application to run in when there is not already
    one, which is the case for every caller that reaches a form straight
    from the command line.
    """

    CSS = BASE_CSS

    BINDINGS: ClassVar = [Binding("f3", "toggle_appearance", "", show=False)]

    def __init__(
        self,
        page: FormPage,
        *,
        rebuild: Callable[[Mapping[str, str]], FormPage] | None = None,
    ) -> None:
        super().__init__()
        self._page = page
        self._rebuild = rebuild
        self.collected: Mapping[str, str] | None = None
        """The committed values, or ``None`` when the operator left without
        committing. Callers read this rather than catching an exception,
        because abandoning is an ordinary choice."""

    def on_mount(self) -> None:
        install_cadrumo_themes(self)
        self.push_screen(FormScreen(self._page, rebuild=self._rebuild), self._finish)

    def _finish(self, collected: Mapping[str, str] | None) -> None:
        """Carry the screen's answer out to the caller and close.

        The application exists only for the one screen, so its dismissal
        is the application's result: there is nothing left to show once
        the page is done with.
        """
        self.collected = collected
        self.exit(collected)

    def action_toggle_appearance(self) -> None:
        toggle_appearance(self)


def run_form_tui(
    page: FormPage,
    *,
    rebuild: Callable[[Mapping[str, str]], FormPage] | None = None,
) -> Mapping[str, str] | None:
    """Run one form page and return the committed values, or ``None``.

    For a caller that has no application of its own. A caller already
    running one pushes :class:`FormScreen` instead — starting a second
    application from inside a running event loop is what this function
    cannot do.
    """
    app = FormApp(page, rebuild=rebuild)
    app.run()
    return app.collected


def multi_choice_tokens(value: str) -> tuple[str, ...]:
    """Split a stored multi-choice value back into its tokens."""
    return tuple(token for token in value.split(_MULTI_CHOICE_SEPARATOR) if token)


def form_choices(pairs: Sequence[tuple[str, str]]) -> tuple[FormChoice, ...]:
    """Build the choice tuple from ``(value, label)`` pairs."""
    return tuple(FormChoice(value=value, label=label) for value, label in pairs)


__all__ = [
    "ChoiceEditScreen",
    "FormApp",
    "FormChoice",
    "FormField",
    "FormFieldKind",
    "FormPage",
    "FormScreen",
    "OneChoiceEditScreen",
    "TextEditScreen",
    "form_choices",
    "multi_choice_tokens",
    "run_form_tui",
]
