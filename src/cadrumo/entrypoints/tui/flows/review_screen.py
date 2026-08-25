"""The review page: every question, its status, its data — clickable.

Renders the substrate's :class:`ReviewProjection` as a row-clickable
data table: status glyph, the resolved question prompt, the current
in-flow answer, and — when the domain flow supplied a registered-values
projection — the value the domain currently has on record, side by
side. Clicking a visible row jumps the engine cursor there; clicking a
stale orphan applies the confirmed reset recovery. The aggregated
blocking verdicts and the submit affordance render beneath the table;
save-and-exit appears only where the definition declares checkpointing
for the mode, with an explicit unavailability line on the no-op arm.

The registered-values column is domain-supplied display data keyed by
page key; the substrate renders it, masking a SECRET page's value
through the same widget-kind lookup the answer column uses. Beyond
that one interpretation the substrate does not reformat the string —
the comparison judgment stays with the operator (and with the domain's
own validators).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from textual.app import ComposeResult
from textual.binding import Binding, BindingsMap
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from ....application.flows import (
    ReviewProjection,
    ReviewRow,
    assemble_page_copy,
    assemble_section_titles,
    checkpoint_available,
    review,
    visible_sequence,
)
from ....core.flows import FlowMode, PageStatus
from ....core.i18n import tr
from .confirm_screen import confirm_restart_dialog
from .question_screen import _operator_answer, _operator_verdict

if TYPE_CHECKING:
    from .app import FlowTuiApp

_STATUS_GLYPHS: dict[PageStatus, str] = {
    PageStatus.ANSWERED: "✔",
    PageStatus.UNANSWERED: "○",
    PageStatus.INVALID: "✗",
    PageStatus.STALE: "⚠",
    PageStatus.DEFERRED: "…",
}

_SECTION_HEADING_PREFIX = "\x00section\x00"
"""Row-key prefix marking a section-heading row; never a real page key, so the
row-selection handler ignores it and it collides with no engine page."""


class ReviewScreen(Screen[None]):
    """Clickable summary of every question with its current and registered data."""

    # Keys and actions only; descriptions resolve at runtime in on_mount so
    # the footer tracks the active language, not the import-time language.
    BINDINGS = [
        Binding("escape", "back_to_question", ""),
        Binding("s", "submit_flow", ""),
        Binding("ctrl+s", "save_exit", ""),
        Binding("ctrl+n", "restart_flow", ""),
    ]

    @override
    def compose(self) -> ComposeResult:
        """Yield the review screen's widgets: header, answer table, blocking notes, and submit."""
        yield Static(id="review-header")
        yield DataTable(id="review-table", cursor_type="row")
        yield Static(id="review-blocking")
        yield Static(id="review-save-note")
        yield Button(tr("flows.review.action_submit"), id="btn-submit", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        """Configure localized table columns and render the current review."""
        self._localize_bindings()
        table = self.query_one("#review-table", DataTable)
        table.zebra_stripes = True
        table.add_columns(
            tr("flows.review.column_status"),
            tr("flows.review.column_question"),
            tr("flows.review.column_answer"),
            tr("flows.review.column_registered"),
        )
        self.render_review()

    def _localize_bindings(self) -> None:
        """Resolve footer binding descriptions under the active language."""
        self._bindings = BindingsMap(
            [
                Binding("escape", "back_to_question", tr("flows.tui.binding_return")),
                Binding("s", "submit_flow", tr("flows.tui.binding_submit")),
                Binding("ctrl+s", "save_exit", tr("flows.tui.binding_save_exit")),
                Binding("ctrl+n", "restart_flow", tr("flows.tui.binding_restart")),
            ],
        )
        self.refresh_bindings()

    @property
    def flow_app(self) -> FlowTuiApp:
        """Return the typed flow application that owns this projection."""
        from .app import require_flow_app

        return require_flow_app(self.app)

    def render_review(self) -> None:
        """Project the engine review into the table, notices, and submit control."""
        app = self.flow_app
        projection = review(app.definition, app.state)
        prompts = self._prompts_by_key(app)
        self.query_one("#review-header", Static).update(
            tr(
                "flows.review.header_tui",
                answered=projection.answered_count,
                remaining=projection.required_remaining,
                eligible=tr("flows.confirm.yes" if projection.submit_eligible else "flows.confirm.no"),
            ),
        )
        table = self.query_one("#review-table", DataTable)
        table.clear()
        self._fill_table(table, app, projection, prompts)
        choice_labels = {
            choice.value: choice.label
            for entry in visible_sequence(app.definition, app.state)
            for choice in assemble_page_copy(entry.page).choices
        }
        blocking_text = "\n".join(
            _operator_verdict(
                verdict,
                prompts=prompts,
                current_prompt=tr("flows.review.question_unavailable"),
                choices=choice_labels,
            )
            for verdict in projection.blocking
            if verdict.message_key
        )
        blocking = self.query_one("#review-blocking", Static)
        blocking.update(blocking_text)
        # The red-bordered blocking box only occupies space when it carries a
        # refusal, so a submit-eligible review is not framed by an empty box.
        blocking.display = bool(blocking_text)
        if checkpoint_available(app.definition, app.state.mode):
            save_note = ""
        else:
            mode_label = tr(
                "flows.review.mode_create" if app.state.mode is FlowMode.CREATE else "flows.review.mode_modify",
            )
            save_note = tr("flows.review.save_unavailable", mode=mode_label)
        self.query_one("#review-save-note", Static).update(save_note)
        self.query_one("#btn-submit", Button).disabled = not projection.submit_eligible
        table.focus()

    def _fill_table(
        self,
        table: DataTable[str],
        app: FlowTuiApp,
        projection: ReviewProjection,
        prompts: dict[str, str],
    ) -> None:
        """Add one row per reviewed page, opened by a section heading where useful.

        A heading row exists to distinguish one section's rows from
        another's; with exactly one section there is nothing to
        distinguish, and the heading renders whatever copy that section
        happens to be titled with -- which, for a flow whose single
        section stands in for "every page this run has" rather than a
        real named group (both live wizard entrypoints build theirs this
        way), is the flow's own multi-sentence help text landing in the
        table as if it were a question row. Multi-section flows (the
        retired setup wizard's "Identidad" / "Actividad económica" etc.)
        are untouched: every one of their headings stays exactly as
        rendered today.
        """
        section_titles = self._section_titles(app)
        multi_section = len({row.section_id for row in projection.rows}) > 1
        current_section: str | None = None
        for row in projection.rows:
            if multi_section and row.section_id != current_section:
                # Group the summary by section: a heading row opens each
                # section so review reads as a complete-profile summary, not a
                # flat per-page status list. The heading key is sentinel-scoped
                # so it never resolves to a jump target.
                current_section = row.section_id
                table.add_row(
                    "",
                    section_titles.get(row.section_id, tr("flows.review.section_unavailable")),
                    "",
                    "",
                    key=f"{_SECTION_HEADING_PREFIX}{row.section_id}",
                )
            table.add_row(
                _STATUS_GLYPHS.get(row.status, "?"),
                self._prompt_cell(row, prompts),
                self._answer_cell(app, row.key),
                self._registered_cell(app, row.key),
                key=row.key,
            )

    @staticmethod
    def _prompt_cell(row: ReviewRow, prompts: dict[str, str]) -> str:
        """The question-column cell, marked when the row is a stale orphan."""
        prompt = prompts.get(row.key)
        if prompt is None:
            return tr("flows.review.question_unavailable")
        if not row.jumpable:
            return f"{prompt} {tr('flows.review.orphan_marker')}".strip()
        return prompt

    @staticmethod
    def _answer_cell(app: FlowTuiApp, page_key: str) -> str:
        """The answer-column cell, masked when the page collects a secret.

        A SECRET page's committed value must never appear in the review
        table (or a captured session log); the masked marker renders in
        its place while the raw answer stays only in the engine state.
        """
        answer = app.state.answers.get(page_key, "")
        if answer and app.is_secret_page(page_key):
            return tr("flows.progress.current_answer_secret")
        entry = next((item for item in visible_sequence(app.definition, app.state) if item.key == page_key), None)
        return answer if entry is None else _operator_answer(entry.page, answer)

    @staticmethod
    def _registered_cell(app: FlowTuiApp, page_key: str) -> str:
        """The registered-value column cell, masked when the page collects a secret.

        Mirrors :meth:`_answer_cell` exactly: a SECRET page's on-record
        value must never appear in the review table (or a captured session
        log) any more than its in-flow answer may, so this reads the same
        ``app.is_secret_page`` widget-kind lookup rather than a second,
        independently-drifting masking authority.
        """
        registered = app.registered_values.get(page_key, "")
        if registered and app.is_secret_page(page_key):
            return tr("flows.progress.current_answer_secret")
        entry = next((item for item in visible_sequence(app.definition, app.state) if item.key == page_key), None)
        return registered if entry is None else _operator_answer(entry.page, registered)

    def _prompts_by_key(self, app: FlowTuiApp) -> dict[str, str]:
        """Resolved prompt copy per visible page key (orphans keep their key)."""
        return {
            entry.key: assemble_page_copy(entry.page).prompt for entry in visible_sequence(app.definition, app.state)
        }

    @staticmethod
    def _section_titles(app: FlowTuiApp) -> dict[str, str]:
        """Resolved section-title copy per section id, for the grouping headings."""
        return assemble_section_titles(app.definition)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Route a selectable review row to the app's edit-or-recovery intent."""
        page_key = event.row_key.value
        if page_key is None or page_key.startswith(_SECTION_HEADING_PREFIX):
            return  # a section-heading row is not a jump target
        self.flow_app.edit_from_review(page_key)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route the submit button to the owning application."""
        if event.button.id == "btn-submit":
            self.flow_app.action_submit()

    def action_back_to_question(self) -> None:
        """Route the return binding to the question projection."""
        self.flow_app.action_leave_review()

    def action_submit_flow(self) -> None:
        """Route the submit binding to the engine-backed application."""
        self.flow_app.action_submit()

    def action_save_exit(self) -> None:
        """Route the checkpoint binding to the owning application."""
        self.flow_app.action_save_exit()

    def action_restart_flow(self) -> None:
        """Ask before wiping every answer; mirrors the question screen's guard.

        The review page is where every answer is finally visible at once —
        exactly where an accidental ``ctrl+n`` is costliest, since the
        operator may have just reached the end of a long walk.
        """
        self.app.push_screen(confirm_restart_dialog(), self._apply_restart_decision)

    def _apply_restart_decision(self, confirmed: bool | None) -> None:
        if confirmed:
            self.flow_app.action_restart()


__all__ = ["ReviewScreen"]
