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

from typing import TYPE_CHECKING, override

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingsMap
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    OptionList,
    ProgressBar,
    RadioButton,
    RadioSet,
    Static,
)
from textual.widgets.option_list import Option

from ....application.flows import (
    assemble_page_copy,
    assemble_section_titles,
    resolve_copy,
    validate_widget_shape,
    visible_sequence,
)
from ....core.flows import DEFER_TOKEN, FlowWidgetKind
from ....core.i18n import tr
from ....core.parsing import parse_bool
from ....entrypoints.tui.components import ContentScroll
from ._confirm_screen import confirm_restart_dialog

if TYPE_CHECKING:
    from collections.abc import Mapping

    from textual.events import Key

    from ....application.flows import ChoiceCopy, FlowPage, PageCopy, ValidationVerdict, VisiblePage
    from ._app import FlowTuiApp

_TEXTUAL_INPUT_WIDGETS = frozenset(
    {
        FlowWidgetKind.TEXT,
        FlowWidgetKind.SECRET,
        FlowWidgetKind.INTEGER,
        FlowWidgetKind.PATH,
        FlowWidgetKind.DATE,
        FlowWidgetKind.DECIMAL,
    },
)


def _operator_confirm_answer(page: FlowPage, raw: str) -> str | None:
    if page.widget is not FlowWidgetKind.CONFIRM:
        return None
    parsed = parse_bool(raw)
    if parsed is None:
        return None
    return tr("flows.confirm.yes" if parsed else "flows.confirm.no")


def _operator_choice_answer(page: FlowPage, raw: str) -> str | None:
    if page.widget in {FlowWidgetKind.SELECT, FlowWidgetKind.COMPARE_SELECT, FlowWidgetKind.CHECKBOX}:
        labels = {choice.value: choice.label for choice in assemble_page_copy(page).choices}
        tokens = raw.split(",") if page.widget is FlowWidgetKind.CHECKBOX else [raw]
        if any(token not in labels for token in tokens):
            return tr("flows.tui.choice_unavailable")
        return ", ".join(labels[token] for token in tokens)
    return None


def _operator_answer(page: FlowPage, raw: str) -> str:
    """Render a committed answer without exposing a closed-choice token."""
    if not raw:
        return ""
    confirm_answer = _operator_confirm_answer(page, raw)
    if confirm_answer is not None:
        return confirm_answer
    if page.widget is FlowWidgetKind.COMPARE_SELECT and raw == DEFER_TOKEN:
        return tr("flows.compare_select.defer_label")
    choice_answer = _operator_choice_answer(page, raw)
    if choice_answer is not None:
        return choice_answer
    return raw


def _operator_verdict(
    verdict: ValidationVerdict,
    *,
    prompts: Mapping[str, str],
    current_prompt: str,
    choices: Mapping[str, str],
) -> str:
    """Resolve one verdict after replacing machine identifiers with copy."""
    context = dict(verdict.context)
    for key in ("page_id", "page_key", "page"):
        if key in context:
            context[key] = prompts.get(str(context[key]), current_prompt)
    if "fields" in context and isinstance(context["fields"], list):
        context["fields"] = [
            prompts.get(str(value), tr("flows.review.question_unavailable")) for value in context["fields"]
        ]
    if "choices" in context and isinstance(context["choices"], list):
        context["choices"] = [
            choices.get(str(value), tr("flows.tui.choice_unavailable")) for value in context["choices"]
        ]
    return tr(verdict.message_key or "", **context)


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

    @override
    def compose(self) -> ComposeResult:
        """Yield the question screen's widgets: header, progress, prompt, and answer input.

        The body follows the shared three-part scaffold every other
        full-screen surface uses: one ``ContentScroll`` host (``height:
        1fr``, so it is the single thing that scrolls), the fluid centred
        column, then the bordered panel (``height: auto``). Collapsing the
        host and the panel into one auto-height scroll container makes that
        container unable to scroll and pushes the overflow onto the Screen.
        """
        with Vertical(id="flow-top"):
            yield Static(id="flow-header")
            yield ProgressBar(id="flow-progress", show_eta=False)
        with (
            ContentScroll(id="page-scroll", classes="cadrumo-scroll"),
            Vertical(classes="cadrumo-column"),
            Vertical(id="page-body", classes="cadrumo-panel"),
        ):
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
        # The section id is an internal slug; the operator-facing title is the
        # section's resolved copy, so both the header and the panel below read
        # in the active profile's language.
        section_title = assemble_section_titles(app.definition).get(entry.section_id)
        if section_title is None:
            section_title = tr("flows.tui.section_unavailable")
        flow_title = resolve_copy(app.definition.title)
        if section_title == flow_title:
            header = tr(
                "flows.tui.header_single_section",
                flow=flow_title,
                position=position + 1,
                total=len(sequence),
            )
        else:
            header = tr(
                "flows.tui.header",
                flow=flow_title,
                position=position + 1,
                total=len(sequence),
                section=section_title,
            )
        self.query_one("#flow-header", Static).update(header)
        self.query_one("#flow-progress", ProgressBar).update(total=len(sequence), progress=position + 1)
        # The bordered question panel carries the section as its title so the
        # operator always sees which part of the flow they are in.
        self.query_one("#page-body", Vertical).border_title = section_title

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
            else tr("flows.progress.current_answer", value=_operator_answer(entry.page, current))
        )
        return f"✓ {marker}"

    @staticmethod
    def _commit_verdicts_text(app: FlowTuiApp, entry: VisiblePage) -> str:
        verdicts = app.state.verdicts.get(entry.key, ())
        copy = assemble_page_copy(entry.page)
        prompts = {
            visible.key: assemble_page_copy(visible.page).prompt
            for visible in visible_sequence(app.definition, app.state)
        }
        choices = {choice.value: choice.label for choice in copy.choices}
        return "\n".join(
            _operator_verdict(
                verdict,
                prompts=prompts,
                current_prompt=copy.prompt,
                choices=choices,
            )
            for verdict in verdicts
            if verdict.message_key
        )

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
                RadioButton(tr("flows.confirm.yes"), value=parse_bool(current) is True, name="true"),
                RadioButton(tr("flows.confirm.no"), value=parse_bool(current) is False, name="false"),
            )
            area.mount(radio)
            radio.focus()
            return
        # SELECT / COMPARE_SELECT / CHECKBOX all render as one conventional
        # numbered list — full-width rows, one option per line, never a
        # horizontal rail. The kind only changes the glyph ([ ]/[x] vs
        # ( )/(•)) and whether a choice stages or commits-and-advances.
        option_list = OptionList(*self._choice_options(copy, widget_kind, current))
        area.mount(option_list)
        option_list.focus()

    def _choice_options(self, copy: PageCopy, widget_kind: FlowWidgetKind, current: str) -> list[Option]:
        selected = {token for token in current.split(",") if token} if widget_kind is FlowWidgetKind.CHECKBOX else None
        options: list[Option] = []
        for index, choice in enumerate(copy.choices, start=1):
            is_selected = choice.value in selected if selected is not None else choice.value == current
            options.append(Option(self._option_prompt(index, choice, widget_kind, chosen=is_selected), id=choice.value))
        if widget_kind is FlowWidgetKind.COMPARE_SELECT:
            options.append(
                Option(
                    self._defer_prompt(len(copy.choices) + 1, chosen=current == DEFER_TOKEN),
                    id=DEFER_TOKEN,
                ),
            )
        return options

    @staticmethod
    def _glyph(widget_kind: FlowWidgetKind, *, chosen: bool) -> str:
        if widget_kind is FlowWidgetKind.CHECKBOX:
            return "[x]" if chosen else "[ ]"
        return "(•)" if chosen else "( )"

    def _option_prompt(self, number: int, choice: ChoiceCopy, widget_kind: FlowWidgetKind, *, chosen: bool) -> Text:
        """A two-line option: numbered glyph + label, then a muted detail line.

        Line two carries the provenance (COMPARE_SELECT — the reason that
        widget exists) and the description when present, indented under the
        label. It is always emitted (blank when empty) so the row height is
        reserved and an incoming domain description never reflows the list.
        """
        text = Text(f"{number}. {self._glyph(widget_kind, chosen=chosen)} {choice.label}")
        details = [detail for detail in (choice.provenance, choice.description) if detail]
        text.append("\n   ")
        text.append(" · ".join(details) if details else " ", style="dim")
        return text

    def _defer_prompt(self, number: int, *, chosen: bool) -> Text:
        glyph = "(•)" if chosen else "( )"
        text = Text(f"{number}. {glyph} {tr('flows.compare_select.defer_label')}")
        text.append("\n   ")
        text.append(" ", style="dim")
        return text

    # ── intents ─────────────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        """Tier-one live validation: non-blocking shape feedback per keystroke."""
        app = self.flow_app
        entry = app.cursor_entry()
        if entry is None:
            return
        _canonical, verdict = validate_widget_shape(entry.page, event.value)
        copy = assemble_page_copy(entry.page)
        hint = (
            ""
            if verdict.ok
            else "✗ "
            + _operator_verdict(
                verdict,
                prompts={entry.key: copy.prompt},
                current_prompt=copy.prompt,
                choices={},
            )
        )
        self.query_one("#live-validation", Static).update(hint)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.flow_app.commit_answer(event.value)

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        # Only the CONFIRM page still mounts a RadioSet (yes / no).
        if event.pressed.name:
            self.flow_app.commit_answer(event.pressed.name)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Enter on the highlighted row toggles (CHECKBOX) or chooses (SELECT)."""
        if event.option.id is not None:
            self._activate_choice(event.option.id)

    def on_key(self, event: Key) -> None:
        """Digit keys 1-9 toggle/choose the numbered row of a choice list."""
        if not event.key.isdigit() or event.key == "0":
            return
        option_lists = self.query_one("#widget-area", Vertical).query(OptionList)
        if not option_lists:
            return
        option_list = option_lists.first()
        index = int(event.key) - 1
        if 0 <= index < option_list.option_count:
            event.stop()
            option_id = option_list.get_option_at_index(index).id
            if option_id is not None:
                self._activate_choice(option_id)

    def _activate_choice(self, value: str) -> None:
        entry = self.flow_app.cursor_entry()
        if entry is None:
            return
        if entry.page.widget is FlowWidgetKind.CHECKBOX:
            # Toggle in the current selection, keep choice order, and STAGE
            # (commit without advancing) so a second selection is not cut off
            # by an immediate page exit; the hook fires per toggle and the
            # glyph updates in place without re-mounting the list.
            copy = assemble_page_copy(entry.page)
            selected = {token for token in self.flow_app.state.answers.get(entry.key, "").split(",") if token}
            selected.symmetric_difference_update({value})
            ordered = ",".join(choice.value for choice in copy.choices if choice.value in selected)
            self.flow_app.commit_answer(ordered, advance=False)
            self._refresh_checkbox_glyphs(entry, copy)
            return
        # SELECT / COMPARE_SELECT: a choice commits and advances.
        self.flow_app.commit_answer(value)

    def _refresh_checkbox_glyphs(self, entry: VisiblePage, copy: PageCopy) -> None:
        """Repaint each row's glyph after a toggle, preserving focus/highlight."""
        option_list = self.query_one("#widget-area", Vertical).query_one(OptionList)
        selected = {token for token in self.flow_app.state.answers.get(entry.key, "").split(",") if token}
        for index, choice in enumerate(copy.choices, start=1):
            option_list.replace_option_prompt_at_index(
                index - 1,
                self._option_prompt(index, choice, FlowWidgetKind.CHECKBOX, chosen=choice.value in selected),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.flow_app.navigate_back()
        elif event.button.id == "btn-next":
            self.flow_app.action_next()
        elif event.button.id == "btn-review":
            self.flow_app.action_go_review()

    def current_input_value(self) -> str | None:
        """The uncommitted text of the mounted Input, if this page has one."""
        inputs = self.query_one("#widget-area", Vertical).query(Input)
        return inputs.first().value if inputs else None

    def action_go_back(self) -> None:
        self.flow_app.navigate_back()

    def action_go_review(self) -> None:
        self.flow_app.action_go_review()

    def action_reset_page(self) -> None:
        self.flow_app.action_reset_current()

    def action_restart_flow(self) -> None:
        """Ask before wiping every answer; the engine transition itself is unconditional.

        ``ctrl+r`` above resets one page and is left unguarded — its blast
        radius is a single answer the operator just gave and can re-enter in
        seconds. ``restart_flow`` wipes the whole walk, which on a long
        setup flow can be dozens of committed pages, so it is the one
        transition here that must not fire on a single, easily mis-struck
        key chord with no way back.
        """
        self.app.push_screen(confirm_restart_dialog(), self._apply_restart_decision)

    def _apply_restart_decision(self, confirmed: bool | None) -> None:
        if confirmed:
            self.flow_app.action_restart()

    def action_save_exit(self) -> None:
        self.flow_app.action_save_exit()


__all__ = ["QuestionScreen"]
