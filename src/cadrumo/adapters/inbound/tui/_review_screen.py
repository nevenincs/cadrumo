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
    assemble_page_copy,
    assemble_section_titles,
    checkpoint_available,
    review,
    visible_sequence,
)
from ....core.flows import PageStatus
from ....core.i18n import tr

if TYPE_CHECKING:
    from ._app import FlowTuiApp

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
        section_titles = self._section_titles(app)
        current_section: str | None = None
        for row in projection.rows:
            if row.section_id != current_section:
                # Group the summary by section: a heading row opens each
                # section so review reads as a complete-profile summary, not a
                # flat per-page status list. The heading key is sentinel-scoped
                # so it never resolves to a jump target.
                current_section = row.section_id
                table.add_row(
                    "",
                    section_titles.get(row.section_id, row.section_id),
                    "",
                    "",
                    key=f"{_SECTION_HEADING_PREFIX}{row.section_id}",
                )
            prompt = prompts.get(row.key, "")
            if not row.jumpable:
                prompt = f"{prompt} {tr('flows.review.orphan_marker')}".strip()
            table.add_row(
                _STATUS_GLYPHS.get(row.status, "?"),
                prompt or row.key,
                self._answer_cell(app, row.key),
                self._registered_cell(app, row.key),
                key=row.key,
            )
        blocking_text = "\n".join(tr(v.message_key, **v.context) for v in projection.blocking if v.message_key)
        blocking = self.query_one("#review-blocking", Static)
        blocking.update(blocking_text)
        # The red-bordered blocking box only occupies space when it carries a
        # refusal, so a submit-eligible review is not framed by an empty box.
        blocking.display = bool(blocking_text)
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
        return registered

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
        page_key = event.row_key.value
        if page_key is None or page_key.startswith(_SECTION_HEADING_PREFIX):
            return  # a section-heading row is not a jump target
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
