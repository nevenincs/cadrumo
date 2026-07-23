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
page key; the substrate renders it verbatim and never interprets it —
the comparison judgment stays with the operator (and with the domain's
own validators).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from cadrumo.application.flows import assemble_page_copy, checkpoint_available, review, visible_sequence
from cadrumo.core.flows import PageStatus
from cadrumo.core.i18n import tr

if TYPE_CHECKING:
    from ._app import FlowTuiApp

_STATUS_GLYPHS: dict[PageStatus, str] = {
    PageStatus.ANSWERED: "✔",
    PageStatus.UNANSWERED: "○",
    PageStatus.INVALID: "✗",
    PageStatus.STALE: "⚠",
    PageStatus.DEFERRED: "…",
}


class ReviewScreen(Screen[None]):
    """Clickable summary of every question with its current and registered data."""

    BINDINGS = [
        Binding("escape", "back_to_question", tr("flows.tui.binding_return")),
        Binding("s", "submit_flow", tr("flows.tui.binding_submit")),
        Binding("ctrl+s", "save_exit", tr("flows.tui.binding_save_exit")),
        Binding("ctrl+n", "restart_flow", tr("flows.tui.binding_restart")),
    ]

    def compose(self) -> ComposeResult:
        yield Static(id="review-header")
        yield DataTable(id="review-table", cursor_type="row")
        yield Static(id="review-blocking")
        yield Static(id="review-save-note")
        yield Button(tr("flows.review.action_submit"), id="btn-submit", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#review-table", DataTable)
        table.add_columns(
            tr("flows.review.column_status"),
            tr("flows.review.column_question"),
            tr("flows.review.column_answer"),
            tr("flows.review.column_registered"),
        )
        self.render_review()

    @property
    def flow_app(self) -> FlowTuiApp:
        from ._app import require_flow_app

        return require_flow_app(self.app)

    def render_review(self) -> None:
        app = self.flow_app
        projection = review(app.definition, app.state)
        prompts = self._prompts_by_key(app)
        self.query_one("#review-header", Static).update(
            tr(
                "flows.review.header_tui",
                answered=projection.answered_count,
                remaining=projection.required_remaining,
                eligible=str(projection.submit_eligible).lower(),
            ),
        )
        table = self.query_one("#review-table", DataTable)
        table.clear()
        for row in projection.rows:
            prompt = prompts.get(row.key, "")
            if not row.jumpable:
                prompt = f"{prompt} {tr('flows.review.orphan_marker')}".strip()
            table.add_row(
                _STATUS_GLYPHS.get(row.status, "?"),
                prompt or row.key,
                self._answer_cell(app, row.key),
                app.registered_values.get(row.key, ""),
                key=row.key,
            )
        self.query_one("#review-blocking", Static).update(
            "\n".join(tr(v.message_key, **v.context) for v in projection.blocking if v.message_key),
        )
        if checkpoint_available(app.definition, app.state.mode):
            save_note = ""
        else:
            save_note = tr("flows.review.save_unavailable", mode=app.state.mode.value)
        self.query_one("#review-save-note", Static).update(save_note)
        self.query_one("#btn-submit", Button).disabled = not projection.submit_eligible
        table.focus()

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
        return answer

    def _prompts_by_key(self, app: FlowTuiApp) -> dict[str, str]:
        """Resolved prompt copy per visible page key (orphans keep their key)."""
        return {
            entry.key: assemble_page_copy(entry.page).prompt for entry in visible_sequence(app.definition, app.state)
        }

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        page_key = event.row_key.value
        if page_key is not None:
            self.flow_app.edit_from_review(page_key)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-submit":
            self.flow_app.action_submit()

    def action_back_to_question(self) -> None:
        self.flow_app.action_leave_review()

    def action_submit_flow(self) -> None:
        self.flow_app.action_submit()

    def action_save_exit(self) -> None:
        self.flow_app.action_save_exit()

    def action_restart_flow(self) -> None:
        self.flow_app.action_restart()


__all__ = ["ReviewScreen"]
