"""The profile manager: your profile as data you can edit, not steps to finish.

This is what the operator lands on after registering, and what
``config profile edit`` opens directly. It replaces the wizard's review
page, which enumerated the *questions of a setup flow* with a status
glyph each — a progress meter for a process, telling the operator where
they were in a walk but never what their profile actually held.

The page here is the profile itself: every schema section, every declared
field, and the value on record for it. A field the operator has not
filled in is a visible empty row, because "what is still blank" is the
question this page exists to answer. Selecting any row edits it in place
and writes immediately; there is no submit step, no final commit, and no
ordering. Completeness is shown as a count and a list of what filing will
eventually need — never as a gate on viewing or editing.

The screen owns no profile logic. The page content is
:func:`~cadrumo.application.user_profile.build_profile_overview`, and an
edit is :func:`~cadrumo.application.user_profile.set_active_field` — the
same door every other write path uses.

See Also:
    :class:`~cadrumo.application.user_profile.ProfileOverview`
        The typed projection this screen renders.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, override

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Input, Label, Static

from ....core.i18n import tr
from ._theme import BASE_CSS, ContentScroll, install_cadrumo_themes, toggle_appearance

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from ....application.user_profile import ProfileFieldView, ProfileOverview


@dataclass(frozen=True, slots=True)
class ManagerActionOutcome:
    """What an action did, as the page needs to know it.

    ``overview`` carries the rebuilt page when the action changed the
    record, and is ``None`` when it did not — an export writes a file and
    leaves the profile alone. The screen re-renders only when it is given
    something new, so a read-only action cannot silently redraw stale data.
    """

    message: str
    overview: ProfileOverview | None = None


@dataclass(frozen=True, slots=True)
class ManagerAction:
    """One operation offered alongside the field table.

    The screen knows a label and a callable. What "pull" or "export" mean
    is the entry point's business, which is why a censal pull and a bundle
    export can sit side by side here without this module learning what
    either of them is.
    """

    key: str
    label: str
    run: Callable[[], ManagerActionOutcome]


_PRESENT_GLYPH = "●"
"""Marks a field carrying a value. A glyph, not colour alone."""

_ABSENT_GLYPH = "○"
"""Marks a declared field the operator has not filled in yet."""

_REQUIRED_MARK = "*"
"""Marks a field filing will eventually require."""


class FieldEditScreen(ModalScreen[str | None]):
    """Edit one field's value. Dismisses with the new value, or ``None``."""

    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, field: ProfileFieldView) -> None:
        super().__init__()
        self._field = field

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="edit-dialog"):
            yield Label(self._field.label, id="edit-label")
            yield Static(self._field.path, id="edit-path")
            # A masked field starts EMPTY rather than pre-filled with the
            # placeholder: pre-filling would submit the dots back as the
            # literal new value the moment the operator pressed enter.
            yield Input(value="" if self._field.masked else (self._field.value or ""), id="edit-input")
            with Horizontal(id="edit-actions"):
                yield Button(tr("flows.manager.edit.cancel"), id="btn-edit-cancel")
                yield Button(tr("flows.manager.edit.save"), id="btn-edit-save", classes="-primary")

    def on_mount(self) -> None:
        self.query_one("#edit-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-edit-save":
            self.dismiss(self.query_one("#edit-input", Input).value)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ProfileManagerApp(App[None]):
    """Full-screen profile overview with in-place editing."""

    CSS = (
        BASE_CSS
        + """
    #manager-progress {
        dock: top;
        height: 1;
        width: 100%;
        padding: 0 2;
        background: $surface;
        color: $text-muted;
    }
    .manager-section DataTable { height: auto; width: 100%; background: $surface; }
    #manager-actions { height: auto; width: 100%; }
    #manager-actions Button { margin: 0 2 0 0; }
    #manager-action-result { margin: 1 0 0 0; color: $text-muted; }
    #edit-dialog {
        border: thick $accent;
        background: $surface;
        padding: 1 3;
        width: 60%;
        height: auto;
    }
    #edit-label { text-style: bold; }
    #edit-path { color: $text-muted; margin: 0 0 1 0; }
    #edit-dialog Input { margin: 0 0 1 0; }
    #edit-actions { height: auto; align-horizontal: right; margin: 1 0 0 0; }
    #edit-actions Button { margin: 0 0 0 2; }
    """
    )

    BINDINGS: ClassVar = [
        Binding("f3", "toggle_appearance", "", show=False),
        Binding("q", "quit", "", show=False),
        Binding("escape", "quit", "", show=False),
    ]

    def __init__(
        self,
        overview: ProfileOverview,
        *,
        persist: Callable[[str, str], ProfileOverview],
        actions: Sequence[ManagerAction] = (),
    ) -> None:
        super().__init__()
        self.overview = overview
        self._actions = tuple(actions)
        """Operations offered above the field table.

        Empty is a valid page: the manager is useful with nothing but its
        fields, and a host that cannot offer an action should show none
        rather than a button that refuses."""
        self._persist_field = persist
        """Writes one field and hands back the page as storage now holds it.

        Injected, not imported: the adapter tier renders a view-model and
        reports intents, exactly as the status page does. Returning the
        reloaded overview rather than ``None`` is what keeps the screen
        from ever displaying its own optimistic guess — whatever the store
        made of the value is what appears."""
        self._field_by_key: dict[str, ProfileFieldView] = {}

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="manager-banner", classes="cadrumo-banner")
        yield Static(id="manager-progress")
        with ContentScroll(id="manager-body", classes="cadrumo-scroll"), Vertical(classes="cadrumo-column"):
            if self._actions:
                with Vertical(id="manager-actions-panel", classes="cadrumo-panel"):
                    with Horizontal(id="manager-actions"):
                        for action in self._actions:
                            yield Button(action.label, id=f"action-{action.key}")
                    yield Static(id="manager-action-result")
            for section in self.overview.sections:
                yield Static(id=f"section-{section.key}", classes="manager-section cadrumo-panel")
        yield Footer()

    def on_mount(self) -> None:
        install_cadrumo_themes(self)
        self.query_one("#manager-banner", Static).update(
            tr("flows.manager.title", profile=self.overview.label),
        )
        if self._actions:
            self.query_one("#manager-actions-panel", Vertical).border_title = tr("flows.manager.actions.section")
        self._render()

    # ── rendering ───────────────────────────────────────────────────────

    def _render(self) -> None:
        """Rebuild the progress line and every section table from the overview."""
        self.query_one("#manager-progress", Static).update(
            tr(
                "flows.manager.progress",
                present=self.overview.present_count,
                total=self.overview.total_count,
                missing=len(self.overview.missing_required),
            ),
        )
        self._field_by_key.clear()
        for section in self.overview.sections:
            panel = self.query_one(f"#section-{section.key}", Static)
            panel.border_title = tr(
                "flows.manager.section_title",
                title=section.title,
                present=section.present_count,
                total=section.total_count,
            )
            panel.remove_children()
            table: DataTable[str] = DataTable(cursor_type="row", zebra_stripes=True)
            panel.mount(table)
            table.add_columns(
                tr("flows.manager.column.state"),
                tr("flows.manager.column.field"),
                tr("flows.manager.column.value"),
            )
            for field in section.fields:
                key = field.path
                self._field_by_key[key] = field
                label = f"{field.label}{_REQUIRED_MARK}" if field.required else field.label
                table.add_row(
                    _PRESENT_GLYPH if field.present else _ABSENT_GLYPH,
                    label,
                    field.value or "",
                    key=key,
                )

    # ── editing ─────────────────────────────────────────────────────────

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the edit dialog for the selected field."""
        key = event.row_key.value
        if key is None:
            return
        field = self._field_by_key.get(str(key))
        if field is None:
            return
        self.push_screen(FieldEditScreen(field), self._apply_edit_for(field))

    def _apply_edit_for(self, field: ProfileFieldView):
        """Build the dismissal callback that persists one field's new value."""

        def _apply(value: str | None) -> None:
            if value is None:
                return
            self._persist(field.path, value)

        return _apply

    def _persist(self, path: str, value: str) -> None:
        """Write one field through the injected door and re-render."""
        self.overview = self._persist_field(path, value)
        self._render()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Run the pressed action and report what it did.

        A refusal is reported in the same line as a success rather than
        raised: the operator is mid-page and an exception would take the
        whole screen down over, say, a missing certificate.
        """
        button_id = event.button.id or ""
        action = next((item for item in self._actions if f"action-{item.key}" == button_id), None)
        if action is None:
            return
        try:
            outcome = action.run()
        except Exception as refusal:
            self.query_one("#manager-action-result", Static).update(str(refusal))
            return
        self.query_one("#manager-action-result", Static).update(outcome.message)
        if outcome.overview is not None:
            self.overview = outcome.overview
            self._render()

    def action_toggle_appearance(self) -> None:
        toggle_appearance(self)


def run_profile_manager_tui(
    overview: ProfileOverview,
    *,
    persist: Callable[[str, str], ProfileOverview],
    actions: Sequence[ManagerAction] = (),
) -> None:
    """Run the manager to completion against an already-built overview."""
    ProfileManagerApp(overview, persist=persist, actions=actions).run()


__all__ = [
    "FieldEditScreen",
    "ManagerAction",
    "ManagerActionOutcome",
    "ProfileManagerApp",
    "run_profile_manager_tui",
]
