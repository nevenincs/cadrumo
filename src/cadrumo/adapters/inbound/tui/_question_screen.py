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
from textual.binding import Binding, BindingsMap
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    ProgressBar,
    RadioButton,
    RadioSet,
    SelectionList,
    Static,
)
from textual.widgets.selection_list import Selection

from cadrumo.application.flows import assemble_page_copy, validate_widget_shape, visible_sequence
from cadrumo.core.flows import DEFER_TOKEN, FlowWidgetKind
from cadrumo.core.i18n import tr

if TYPE_CHECKING:
    from cadrumo.application.flows import ChoiceCopy, PageCopy, VisiblePage

    from ._app import FlowTuiApp

_TEXTUAL_INPUT_WIDGETS = frozenset(
    {FlowWidgetKind.TEXT, FlowWidgetKind.SECRET, FlowWidgetKind.INTEGER, FlowWidgetKind.PATH},
)


class QuestionScreen(Screen[None]):
    """Renders the cursor page and forwards answer intents to the app driver."""

    # Keys and actions only: descriptions are resolved at runtime in
    # ``on_mount`` (``_localize_bindings``), never here — a ``tr`` call at
    # class-definition time would freeze the footer to the import-time
    # language, wrong for a mid-walk language switch or consecutive runs
    # under different profile languages in one process.
    BINDINGS = [
        Binding("escape", "go_back", ""),
        Binding("f2", "go_review", ""),
        Binding("ctrl+r", "reset_page", ""),
        Binding("ctrl+n", "restart_flow", ""),
        Binding("ctrl+s", "save_exit", ""),
    ]

    def compose(self) -> ComposeResult:
        yield Static(id="flow-header")
        yield ProgressBar(id="flow-progress", show_eta=False)
        with VerticalScroll(id="page-body"):
            yield Label("", id="page-prompt")
            yield Static("", id="page-badge")
            yield Static("", id="page-help")
            yield Static("", id="page-format-hint")
            yield Static("", id="page-failure-modes")
            yield Static("", id="page-legal-zone")
            yield Vertical(id="widget-area")
            yield Static("", id="live-validation")
            yield Static("", id="answer-echo")
            yield Static("", id="commit-verdicts")
            with Horizontal(id="nav-buttons"):
                yield Button(tr("flows.tui.button_back"), id="btn-back")
                yield Button(tr("flows.tui.button_next"), id="btn-next", variant="primary")
                # The review affordance is made loud: a key hint on the label
                # and a distinct variant so the operator finds the path to the
                # summary and submit, not only the footer binding.
                yield Button(f"{tr('flows.tui.button_review')} (F2)", id="btn-review", variant="warning")
        yield Footer()

    def on_mount(self) -> None:
        self._localize_bindings()
        self.render_page()

    def _localize_bindings(self) -> None:
        """Resolve the footer binding descriptions under the active language.

        Rebuilt at mount (and re-run on a locale rebuild, which re-pushes a
        fresh screen) so the footer tracks the runtime language rather than
        the language active when this module was imported.
        """
        self._bindings = BindingsMap(
            [
                Binding("escape", "go_back", tr("flows.tui.binding_back")),
                Binding("f2", "go_review", tr("flows.tui.binding_review")),
                Binding("ctrl+r", "reset_page", tr("flows.tui.binding_reset")),
                Binding("ctrl+n", "restart_flow", tr("flows.tui.binding_restart")),
                Binding("ctrl+s", "save_exit", tr("flows.tui.binding_save_exit")),
            ],
        )
        self.refresh_bindings()

    @property
    def flow_app(self) -> FlowTuiApp:
        # `self.app` is typed as App[Any]; the runtime object is always the
        # owning FlowTuiApp. The typed accessor narrows for the checker and,
        # unlike a bare assert, keeps a loud typed refusal under ``python -O``.
        from ._app import require_flow_app

        return require_flow_app(self.app)

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
        self.query_one("#flow-progress", ProgressBar).update(total=len(sequence), progress=position + 1)
        # The bordered question panel carries the section as its title so the
        # operator always sees which part of the flow they are in.
        self.query_one("#page-body", VerticalScroll).border_title = entry.section_id

    def _render_body(self, app: FlowTuiApp, entry: VisiblePage, copy: PageCopy) -> None:
        self.query_one("#page-prompt", Label).update(copy.prompt)
        badge_key = "flows.progress.required" if entry.page.required else "flows.progress.optional"
        self.query_one("#page-badge", Static).update(tr(badge_key))
        # Every optional zone collapses (display off) when its content is
        # absent, so an unpopulated page shows no labelled void or reserved
        # blank row; the zone reappears the moment the domain supplies copy.
        self._set_zone("#page-help", copy.help or "")
        self._set_zone(
            "#page-format-hint",
            f"▸ {tr('flows.progress.format_hint', hint=copy.format_hint)}" if copy.format_hint else "",
        )
        self._set_zone(
            "#page-failure-modes",
            "\n".join(tr("flows.progress.failure_mode", text=text) for text in copy.failure_modes),
        )
        self._set_zone(
            "#page-legal-zone",
            "\n".join(f"{ref.ref} — {ref.label}" if ref.label else ref.ref for ref in copy.legal_zone),
        )
        self.query_one("#answer-echo", Static).update(self._answer_echo_text(app, entry))
        self.query_one("#commit-verdicts", Static).update(self._commit_verdicts_text(app, entry))
        self.query_one("#live-validation", Static).update("")

    def _set_zone(self, selector: str, content: str) -> None:
        """Update a collapsible zone, hiding it entirely when its content is empty."""
        zone = self.query_one(selector, Static)
        zone.update(content)
        zone.display = bool(content)

    @staticmethod
    def _answer_echo_text(app: FlowTuiApp, entry: VisiblePage) -> str:
        """The current-answer echo line, masked when the page is a secret.

        A SECRET page's committed value must never reach a rendered zone
        (or a captured session log): the echo renders a fixed masked
        marker instead of the raw answer, even though the answer itself
        lives in the engine state.
        """
        current = app.state.answers.get(entry.key)
        if not current:
            return ""
        marker = (
            tr("flows.progress.current_answer_secret")
            if entry.page.widget is FlowWidgetKind.SECRET
            else tr("flows.progress.current_answer", value=current)
        )
        return f"✓ {marker}"

    @staticmethod
    def _commit_verdicts_text(app: FlowTuiApp, entry: VisiblePage) -> str:
        verdicts = app.state.verdicts.get(entry.key, ())
        return "\n".join(tr(v.message_key, **v.context) for v in verdicts if v.message_key)

    def refresh_answer_zones(self) -> None:
        """Refresh the echo and verdict zones without re-mounting the widget.

        A staging CHECKBOX toggle commits through the engine but must keep
        the live SelectionList mounted and focused so the next selection
        lands; only the derived echo/verdict/live zones are recomputed.
        """
        app = self.flow_app
        entry = app.cursor_entry()
        if entry is None:
            return
        self.query_one("#answer-echo", Static).update(self._answer_echo_text(app, entry))
        self.query_one("#commit-verdicts", Static).update(self._commit_verdicts_text(app, entry))
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
            buttons = [
                RadioButton(self._choice_label(choice), value=choice.value == current, name=choice.value)
                for choice in copy.choices
            ]
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
            *[Selection(self._choice_label(choice), choice.value, choice.value in tokens) for choice in copy.choices],
        )
        area.mount(selection)
        selection.focus()

    @staticmethod
    def _choice_label(choice: ChoiceCopy) -> str:
        """The rendered label for one choice: title, provenance, and description.

        A COMPARE_SELECT candidate frames its provenance (where the value came
        from — the reason that widget exists); every widget kind renders the
        choice's description as a muted second line when the domain supplied
        one, so a described option no longer shows only its bare label.
        """
        title = choice.label
        if choice.provenance:
            title = tr("flows.compare_select.candidate", label=choice.label, provenance=choice.provenance)
        if choice.description:
            # Beside the label, muted — kept on one line so it survives the
            # single-line RadioButton/Selection label rendering.
            title = f"{title}  [dim]{choice.description}[/dim]"
        return title

    # ── intents ─────────────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        """Tier-one live validation: non-blocking shape feedback per keystroke."""
        app = self.flow_app
        entry = app.cursor_entry()
        if entry is None:
            return
        _canonical, verdict = validate_widget_shape(entry.page, event.value)
        hint = "" if verdict.ok else f"✗ {tr(verdict.message_key or '', **verdict.context)}"
        self.query_one("#live-validation", Static).update(hint)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.flow_app.commit_answer(event.value)

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.pressed.name:
            self.flow_app.commit_answer(event.pressed.name)

    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        # CHECKBOX stages every toggle (commit without advancing) so a
        # second selection is not cut off by an immediate page exit; the
        # page advances only on an explicit Next / escape / review intent,
        # matching the module comment's "navigation away is the page exit".
        selected = ",".join(str(value) for value in event.selection_list.selected)
        self.flow_app.commit_answer(selected, advance=False)

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
