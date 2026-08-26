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
arrangement :class:`~cadrumo.entrypoints.tui.profile.overview.ProfileManagerApp` uses,
for the same reason: an adapter renders and reports intent, and the entry
point composes.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, ClassVar, override

from rich.cells import cell_len
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import DescendantFocus
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Static

from ....core.presentation import (
    FormField,
    FormFieldKind,
    FormPage,
    multi_choice_tokens,
)
from .dialogs import ChoiceEditScreen, OneChoiceEditScreen, TextEditScreen
from .theme import (
    BASE_CSS,
    cadrumo_css_variables,
    install_cadrumo_themes,
    toggle_appearance,
)
from .widgets import ContentDataTable, ContentScroll

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

type FormRebuild = Callable[[Mapping[str, str]], FormPage]
"""Recomputes a page from the answers given to it so far."""

type FormPresenter = Callable[[FormPage, FormRebuild | None], Mapping[str, str] | None]
"""Shows one page and returns what the operator committed, or ``None``.

Takes the rebuild callable positionally so a host can supply the same
shape whether or not the page regenerates itself.
"""


_MASKED_TABLE_VALUE = "••••••••"
"""What a ``secret`` field's row shows once it holds a value.

Fixed-length rather than one bullet per character: this page owns no
application concept of confidentiality (its own docstring is explicit that
it "owns no application logic"), so it does not reach for
``application.user_profile.MASKED_PLACEHOLDER`` and instead states the
same convention locally, the way :class:`TextEditScreen` already masks its
own ``Input`` via ``password=`` rather than importing anything to do it.
Fixed length avoids leaking how long the secret is, which a per-character
mask would not."""


type FormTranslator = Callable[[str], str]


def _display_value(form_field: FormField, value: str, *, translate: FormTranslator) -> str:
    """Render stored choice tokens only through their operator labels."""
    if form_field.secret and value:
        return _MASKED_TABLE_VALUE
    if not value or form_field.kind is FormFieldKind.TEXT:
        return value
    labels_by_value = {choice.value: choice.label for choice in form_field.choices}
    tokens = multi_choice_tokens(value) if form_field.kind is FormFieldKind.MULTI_CHOICE else (value,)
    unavailable = translate("flows.manager.choice_unavailable")
    return ", ".join(labels_by_value.get(token, unavailable) for token in tokens)


def _edit_screen_for(field: FormField, *, translate: FormTranslator) -> ModalScreen[str | None]:
    """Return the dialog that edits one field, by its declared kind."""
    cancel_label = translate("flows.manager.edit.cancel")
    save_label = translate("flows.manager.edit.save")
    match field.kind:
        case FormFieldKind.MULTI_CHOICE:
            return ChoiceEditScreen(field, cancel_label=cancel_label, save_label=save_label)
        case FormFieldKind.SINGLE_CHOICE:
            return OneChoiceEditScreen(field, cancel_label=cancel_label, save_label=save_label)
        case FormFieldKind.TEXT:
            return TextEditScreen(field, cancel_label=cancel_label, save_label=save_label)


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
    #form-refusal { color: $error; margin: 0; }
    #form-actions { height: auto; align-horizontal: right; margin: 0; }
    #form-actions Button { margin: 0 0 0 1; }
    """

    BINDINGS: ClassVar = [Binding("escape", "abandon", "", show=False)]

    def __init__(
        self,
        page: FormPage,
        *,
        translate: FormTranslator,
        rebuild: Callable[[Mapping[str, str]], FormPage] | None = None,
    ) -> None:
        """Initialize one form screen from its immutable page projection."""
        super().__init__()
        self._page = page
        self._translate = translate
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
            yield ContentDataTable(id="form-table", cursor_type="row", zebra_stripes=True)
            yield Static(id="form-refusal")
            with Horizontal(id="form-actions"):
                yield Button(self._translate("flows.manager.edit.cancel"), id="btn-form-cancel")
                yield Button(self._translate("flows.manager.edit.save"), id="btn-form-save", classes="-primary")
        yield Footer()

    def on_mount(self) -> None:
        """Mount the supplied page title, section, and initial rows."""
        self.query_one("#form-banner", Static).update(self._page.title)
        self.query_one("#form-body", Vertical).border_title = self._page.section
        self._render_rows()

    def on_descendant_focus(self, event: DescendantFocus) -> None:
        """Keep the focused action inside the single outer scroll viewport."""
        event.widget.scroll_visible(animate=False)

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
        rows = tuple(
            (
                form_field.key,
                form_field.label,
                _display_value(form_field, self._values.get(form_field.key, ""), translate=self._translate),
            )
            for form_field in self._page.fields
        )
        field_heading = self._translate("flows.manager.column.field")
        value_heading = self._translate("flows.manager.column.value")
        field_width = max((cell_len(label) for _key, label, _value in rows), default=cell_len(field_heading))
        value_width = max((cell_len(value) for _key, _label, value in rows), default=cell_len(value_heading))
        table.clear(columns=True)
        table.add_column(field_heading, width=max(cell_len(field_heading), field_width))
        table.add_column(value_heading, width=max(cell_len(value_heading), value_width))
        for key, label, shown in rows:
            table.add_row(label, shown, key=key)

    def _field(self, key: str) -> FormField | None:
        return next((form_field for form_field in self._page.fields if form_field.key == key), None)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the editor declared by the selected field's kind."""
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
            secret=form_field.secret,
        )
        screen = _edit_screen_for(current, translate=self._translate)
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
        """Commit or abandon according to the selected action button."""
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
        """Dismiss without returning collected values."""
        self.collected = None
        self.dismiss(None)


class FormApp(App["Mapping[str, str] | None"]):
    """Standalone host for :class:`FormScreen`.

    Everything that makes the page a page lives on the screen; this exists
    only to give it an application to run in when there is not already
    one, which is the case for every caller that reaches a form straight
    from the command line.
    """

    def get_css_variables(self) -> dict[str, str]:
        """Expose the canonical Cadrumo tokens to every stylesheet.

        Textual resolves this once per app and hands the result to app-level
        ``CSS`` and every widget's ``DEFAULT_CSS`` alike, which is why the
        design tokens travel here rather than in the theme's own variables.
        """
        return cadrumo_css_variables(super().get_css_variables())

    CSS = BASE_CSS

    BINDINGS: ClassVar = [Binding("f3", "toggle_appearance", "", show=False)]

    def __init__(
        self,
        page: FormPage,
        *,
        translate: FormTranslator,
        rebuild: Callable[[Mapping[str, str]], FormPage] | None = None,
    ) -> None:
        """Initialize the standalone host for one immutable form page."""
        super().__init__()
        self._page = page
        self._translate = translate
        self._rebuild = rebuild
        self.collected: Mapping[str, str] | None = None
        """The committed values, or ``None`` when the operator left without
        committing. Callers read this rather than catching an exception,
        because abandoning is an ordinary choice."""

    def on_mount(self) -> None:
        """Install themes and push the only form screen."""
        install_cadrumo_themes(self)
        self.push_screen(
            FormScreen(self._page, translate=self._translate, rebuild=self._rebuild),
            self._finish,
        )

    def _finish(self, collected: Mapping[str, str] | None) -> None:
        """Carry the screen's answer out to the caller and close.

        The application exists only for the one screen, so its dismissal
        is the application's result: there is nothing left to show once
        the page is done with.
        """
        self.collected = collected
        self.exit(collected)

    def action_toggle_appearance(self) -> None:
        """Toggle between the registered light and dark themes."""
        toggle_appearance(self)


def run_form_tui(
    page: FormPage,
    *,
    translate: FormTranslator,
    rebuild: Callable[[Mapping[str, str]], FormPage] | None = None,
) -> Mapping[str, str] | None:
    """Run one form page and return the committed values, or ``None``.

    For a caller that has no application of its own. A caller already
    running one pushes :class:`FormScreen` instead — starting a second
    application from inside a running event loop is what this function
    cannot do.
    """
    app = FormApp(page, translate=translate, rebuild=rebuild)
    app.run()
    return app.collected


_ACTIVE_FORM_PRESENTER: ContextVar[FormPresenter | None] = ContextVar(
    "cadrumo_active_form_presenter",
    default=None,
)
"""How a form should be shown, when something has already decided.

Empty in the ordinary case, where a caller reaching a form is free to
start an application for it. A host that is already running one binds
this so the same call opens a page on the host instead.
"""


@contextmanager
def presenting_forms_through(presenter: FormPresenter) -> Iterator[None]:
    """Route form presentation through ``presenter`` for this context.

    A context variable rather than an argument because the callers that
    present a form do not take one: an action is a plain zero-argument
    callable, and several of them are deliberately kept that way — the
    censal action's parameterless signature is a pinned safety property,
    since a parameter there would be somewhere to aim the read at another
    taxpayer. The host therefore states how forms are shown for the
    duration of the call rather than threading it through every action.

    Restores the previous value on the way out, so nesting is safe and an
    action that raises cannot leave a stale presenter bound.
    """
    token = _ACTIVE_FORM_PRESENTER.set(presenter)
    try:
        yield
    finally:
        _ACTIVE_FORM_PRESENTER.reset(token)


def active_form_presenter() -> FormPresenter | None:
    """The presenter bound for this context, or ``None`` to start an application."""
    return _ACTIVE_FORM_PRESENTER.get()


__all__ = [
    "FormApp",
    "FormPresenter",
    "FormScreen",
    "FormTranslator",
    "active_form_presenter",
    "presenting_forms_through",
    "run_form_tui",
]
