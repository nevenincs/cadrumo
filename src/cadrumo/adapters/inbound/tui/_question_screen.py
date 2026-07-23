"""The full-page question screen: one page, all its zones, live validation.

Renders the fixed zones of the full-page question model — header (flow title,
position, section), body (prompt, grounding help, required badge, format
hint, failure modes, input widget, live validation line, current-answer
echo), footer (key bindings) — for whichever page the engine's cursor
addresses. All copy comes pre-assembled from the substrate's copy
assembler; the screen resolves nothing itself.

Live validation is tier one of the three-tier model: every keystroke
runs the engine's widget-shape validation non-blockingly and renders the
outcome as a hint; the blocking commit validation runs in the app driver
when the answer is submitted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Label, RadioButton, RadioSet, SelectionList, Static
from textual.widgets.selection_list import Selection

from cadrumo.application.flows import assemble_page_copy, validate_widget_shape, visible_sequence
from cadrumo.core.flows import DEFER_TOKEN, FlowWidgetKind
from cadrumo.core.i18n import tr

if TYPE_CHECKING:
    from cadrumo.application.flows import PageCopy, VisiblePage

    from ._app import FlowTuiApp

_TEXTUAL_INPUT_WIDGETS = frozenset(
    {FlowWidgetKind.TEXT, FlowWidgetKind.SECRET, FlowWidgetKind.INTEGER, FlowWidgetKind.PATH},
)


class QuestionScreen(Screen[None]):
    """Renders the cursor page and forwards answer intents to the app driver."""

    BINDINGS = [
        ("escape", "go_back", "Anterior"),
        ("f2", "go_review", "Resumen"),
        ("ctrl+r", "reset_page", "Restablecer"),
        ("ctrl+n", "restart_flow", "Reiniciar"),
        ("ctrl+s", "save_exit", "Guardar y salir"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(id="flow-header")
        with VerticalScroll(id="page-body"):
            yield Label("", id="page-prompt")
            yield Static("", id="page-badge")
            yield Static("", id="page-help")
            yield Static("", id="page-format-hint")
            yield Static("", id="page-failure-modes")
            yield Vertical(id="widget-area")
            yield Static("", id="live-validation")
            yield Static("", id="answer-echo")
            yield Static("", id="commit-verdicts")
            with Horizontal(id="nav-buttons"):
                yield Button(tr("flows.tui.button_back"), id="btn-back")
                yield Button(tr("flows.tui.button_next"), id="btn-next", variant="primary")
                yield Button(tr("flows.tui.button_review"), id="btn-review")
        yield Footer()

    def on_mount(self) -> None:
        self.render_page()

    @property
    def flow_app(self) -> FlowTuiApp:
        # CAST-FREE: `self.app` is typed as App[Any]; the runtime object is
        # always the owning FlowTuiApp. Narrowed via assert for the checker.
        from ._app import FlowTuiApp as _App

        app = self.app
        assert isinstance(app, _App)
        return app

    def render_page(self) -> None:
        """(Re)render every zone for the page the engine cursor addresses."""
        app = self.flow_app
        entry = app.cursor_entry()
        if entry is None:
            app.action_go_review()
            return
        copy = assemble_page_copy(entry.page)
        self._render_header(app, entry)
        self._render_body(app, entry, copy)
        self._mount_widget(app, entry, copy)

    def _render_header(self, app: FlowTuiApp, entry: VisiblePage) -> None:
        sequence = visible_sequence(app.definition, app.state)
        position = next((index for index, item in enumerate(sequence) if item.key == entry.key), 0)
        self.query_one("#flow-header", Static).update(
            tr(
                "flows.tui.header",
                flow=app.definition.id,
                position=position + 1,
                total=len(sequence),
                section=entry.section_id,
            ),
        )

    def _render_body(self, app: FlowTuiApp, entry: VisiblePage, copy: PageCopy) -> None:
        self.query_one("#page-prompt", Label).update(copy.prompt)
        badge_key = "flows.progress.required" if entry.page.required else "flows.progress.optional"
        self.query_one("#page-badge", Static).update(tr(badge_key))
        self.query_one("#page-help", Static).update(copy.help or "")
        self.query_one("#page-format-hint", Static).update(
            tr("flows.progress.format_hint", hint=copy.format_hint) if copy.format_hint else "",
        )
        failure_lines = "\n".join(tr("flows.progress.failure_mode", text=text) for text in copy.failure_modes)
        self.query_one("#page-failure-modes", Static).update(failure_lines)
        current = app.state.answers.get(entry.key)
        self.query_one("#answer-echo", Static).update(
            tr("flows.progress.current_answer", value=current) if current else "",
        )
        verdicts = app.state.verdicts.get(entry.key, ())
        self.query_one("#commit-verdicts", Static).update(
            "\n".join(tr(v.message_key, **v.context) for v in verdicts if v.message_key),
        )
        self.query_one("#live-validation", Static).update("")

    def _mount_widget(self, app: FlowTuiApp, entry: VisiblePage, copy: PageCopy) -> None:
        # Dynamic widgets are mounted anonymously (no ids): removal is
        # asynchronous, and a same-id re-mount before the old widget
        # unregisters is a Textual registry collision. Handlers key on
        # widget type and RadioButton names instead.
        area = self.query_one("#widget-area", Vertical)
        area.remove_children()
        widget_kind = entry.page.widget
        current = app.state.answers.get(entry.key) or entry.page.default or ""
        if widget_kind in _TEXTUAL_INPUT_WIDGETS:
            field = Input(
                value="" if widget_kind is FlowWidgetKind.SECRET else current,
                password=widget_kind is FlowWidgetKind.SECRET,
            )
            area.mount(field)
            field.focus()
            return
        if widget_kind is FlowWidgetKind.CONFIRM:
            radio = RadioSet(
                RadioButton(tr("flows.confirm.yes"), value=current == "true", name="true"),
                RadioButton(tr("flows.confirm.no"), value=current == "false", name="false"),
            )
            area.mount(radio)
            radio.focus()
            return
        if widget_kind in {FlowWidgetKind.SELECT, FlowWidgetKind.COMPARE_SELECT}:
            buttons = []
            for choice in copy.choices:
                title = choice.label
                if choice.provenance:
                    title = tr("flows.compare_select.candidate", label=choice.label, provenance=choice.provenance)
                buttons.append(RadioButton(title, value=choice.value == current, name=choice.value))
            if widget_kind is FlowWidgetKind.COMPARE_SELECT:
                buttons.append(
                    RadioButton(
                        tr("flows.compare_select.defer_label"),
                        value=current == DEFER_TOKEN,
                        name=DEFER_TOKEN,
                    ),
                )
            radio = RadioSet(*buttons)
            area.mount(radio)
            radio.focus()
            return
        # CHECKBOX
        tokens = {token for token in current.split(",") if token}
        selection = SelectionList[str](
            *[Selection(choice.label, choice.value, choice.value in tokens) for choice in copy.choices],
        )
        area.mount(selection)
        selection.focus()

    # ── intents ─────────────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        """Tier-one live validation: non-blocking shape feedback per keystroke."""
        app = self.flow_app
        entry = app.cursor_entry()
        if entry is None:
            return
        _canonical, verdict = validate_widget_shape(entry.page, event.value)
        hint = "" if verdict.ok else tr(verdict.message_key or "", **verdict.context)
        self.query_one("#live-validation", Static).update(hint)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.flow_app.commit_answer(event.value)

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.pressed.name:
            self.flow_app.commit_answer(event.pressed.name)

    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        # CHECKBOX commits on every toggle so the echo/live zones track;
        # navigation away is the page exit, matching the engine's
        # commit-then-move contract.
        selected = ",".join(str(value) for value in event.selection_list.selected)
        self.flow_app.commit_answer(selected)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.flow_app.action_back()
        elif event.button.id == "btn-next":
            self.flow_app.action_next()
        elif event.button.id == "btn-review":
            self.flow_app.action_go_review()

    def current_input_value(self) -> str | None:
        """The uncommitted text of the mounted Input, if this page has one."""
        inputs = self.query_one("#widget-area", Vertical).query(Input)
        return inputs.first().value if inputs else None

    def action_go_back(self) -> None:
        self.flow_app.action_back()

    def action_go_review(self) -> None:
        self.flow_app.action_go_review()

    def action_reset_page(self) -> None:
        self.flow_app.action_reset_current()

    def action_restart_flow(self) -> None:
        self.flow_app.action_restart()

    def action_save_exit(self) -> None:
        self.flow_app.action_save_exit()


__all__ = ["QuestionScreen"]
