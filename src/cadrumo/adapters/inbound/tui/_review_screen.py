"""The review screen: every page, its status, jump-to-edit, the submit gate.

Renders the substrate's :class:`ReviewProjection` — one row per page
with its status glyph, the aggregated blocking verdicts, and the submit
affordance that exists only while the projection reports eligibility.
Selecting a visible row jumps the engine cursor there and returns to the
question screen; selecting a stale orphan offers the confirmed reset
recovery. Save-and-exit appears only where the definition declares
checkpointing for the mode; the declared no-op arm renders an explicit
unavailability line instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

from cadrumo.application.flows import checkpoint_available, review
from cadrumo.core.flows import PageStatus
from cadrumo.core.i18n import tr

if TYPE_CHECKING:
    from ._app import FlowTuiApp

_STATUS_GLYPHS: dict[PageStatus, str] = {
    PageStatus.ANSWERED: "[green]✔[/green]",
    PageStatus.UNANSWERED: "[dim]○[/dim]",
    PageStatus.INVALID: "[red]✗[/red]",
    PageStatus.STALE: "[yellow]⚠[/yellow]",
    PageStatus.DEFERRED: "[cyan]…[/cyan]",
}


class ReviewScreen(Screen[None]):
    """Summary surface with jump-to-edit and the submit gate."""

    BINDINGS = [
        ("escape", "back_to_question", "Volver"),
        ("s", "submit_flow", "Presentar"),
        ("ctrl+s", "save_exit", "Guardar y salir"),
        ("ctrl+n", "restart_flow", "Reiniciar"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(id="review-header")
        yield OptionList(id="review-rows")
        yield Static(id="review-blocking")
        yield Static(id="review-save-note")
        yield Footer()

    def on_mount(self) -> None:
        self.render_review()

    @property
    def flow_app(self) -> FlowTuiApp:
        from ._app import FlowTuiApp as _App

        app = self.app
        assert isinstance(app, _App)
        return app

    def render_review(self) -> None:
        app = self.flow_app
        projection = review(app.definition, app.state)
        self.query_one("#review-header", Static).update(
            tr(
                "flows.review.header_tui",
                answered=projection.answered_count,
                remaining=projection.required_remaining,
                eligible=str(projection.submit_eligible).lower(),
            ),
        )
        rows = self.query_one("#review-rows", OptionList)
        rows.clear_options()
        for row in projection.rows:
            glyph = _STATUS_GLYPHS[row.status]
            suffix = "" if row.jumpable else f"  {tr('flows.review.orphan_marker')}"
            rows.add_option(Option(f"{glyph}  {row.key}{suffix}", id=row.key))
        self.query_one("#review-blocking", Static).update(
            "\n".join(tr(v.message_key, **v.context) for v in projection.blocking if v.message_key),
        )
        if checkpoint_available(app.definition, app.state.mode):
            save_note = ""
        else:
            save_note = tr("flows.review.save_unavailable", mode=app.state.mode.value)
        self.query_one("#review-save-note", Static).update(save_note)
        rows.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        page_key = event.option.id
        if page_key is not None:
            self.flow_app.edit_from_review(page_key)

    def action_back_to_question(self) -> None:
        self.flow_app.action_leave_review()

    def action_submit_flow(self) -> None:
        self.flow_app.action_submit()

    def action_save_exit(self) -> None:
        self.flow_app.action_save_exit()

    def action_restart_flow(self) -> None:
        self.flow_app.action_restart()


__all__ = ["ReviewScreen"]
