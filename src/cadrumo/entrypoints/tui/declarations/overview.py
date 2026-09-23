"""Declarations landing over safe natural coordinates."""

from __future__ import annotations

import asyncio
from typing import ClassVar, cast, override

from textual.app import App, ComposeResult
from textual.widgets import Button, DataTable, Input, Static

from ....core.errors.hierarchy import CadrumoError
from ....core.filing_year import FILING_YEAR_MAX, FILING_YEAR_MIN
from ....core.period import Period, PeriodError
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import (
    DeclarationsWorkspaceController,
    DeclarationsWorkspaceScreen,
    declarations_copy,
    natural_address,
    work_create_refusal_message,
    work_state_label,
)
from .models import ModeloWorkCreateHandoffV1


class DeclarationsOverviewScreen(DeclarationsWorkspaceScreen):
    """List local declaration facts without implying filing or AEAT state."""

    IS_WORKSPACE_OVERVIEW: ClassVar[bool] = True

    def __init__(
        self,
        controller: DeclarationsWorkspaceController,
        *,
        id: str = "declarations-overview-screen",
    ) -> None:
        """Retain injected state and semantic selection."""
        super().__init__(controller, id=id)
        self.selected_work_unit_id: str | None = None
        self._work_create_in_flight = False

    @override
    def compose(self) -> ComposeResult:
        yield Static(declarations_copy("tui.declarations.overview.title"), classes="cadrumo-banner", markup=False)
        with ContentScroll(id="declarations-page", classes="cadrumo-scroll declarations-page"):
            yield Static(
                declarations_copy("tui.declarations.overview.areas"),
                classes="cadrumo-heading cadrumo-heading-lead",
                markup=False,
            )
            yield ContentDataTable[str](id="declarations-navigation", cursor_type="row", zebra_stripes=True)
            yield Static(
                declarations_copy("tui.declarations.work_create.title"),
                classes="cadrumo-heading",
                markup=False,
            )
            yield Static(declarations_copy("tui.declarations.work_create.modelo"), markup=False)
            yield Input(placeholder="111", id="declarations-work-modelo", max_length=8)
            yield Static(declarations_copy("tui.declarations.work_create.year"), markup=False)
            yield Input(placeholder="2025", id="declarations-work-year", max_length=4)
            yield Static(declarations_copy("tui.declarations.work_create.period"), markup=False)
            yield Input(placeholder="1T / 0A", id="declarations-work-period", max_length=12)
            yield Button(declarations_copy("tui.declarations.work_create.submit"), id="declarations-work-create")
            yield Static(id="declarations-work-create-notice", classes="declarations-refusal", markup=False)
            yield Static(
                declarations_copy("tui.declarations.overview.declarations"),
                classes="cadrumo-heading",
                markup=False,
            )
            yield ContentDataTable[str](id="declarations-list", cursor_type="row", zebra_stripes=True)
            yield Static(id="declarations-empty", classes="declarations-empty", markup=False)
            yield Static(id="declarations-refusal", classes="declarations-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate safe natural-coordinate declaration rows."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#declarations-list", DataTable))
        table.add_column(declarations_copy("tui.declarations.column.declaration"), key="declaration")
        table.add_column(declarations_copy("tui.declarations.column.local_state"), key="state")
        table.add_column(declarations_copy("tui.declarations.column.calculation"), key="calculation")
        table.add_column(declarations_copy("tui.declarations.column.result"), key="result")
        for row in self.controller.projection.declarations:
            table.add_row(
                natural_address(row.modelo, row.filing_year, row.period),
                work_state_label(row.state),
                declarations_copy(
                    "tui.declarations.value.available" if row.has_current_calculation else "tui.declarations.value.none"
                ),
                # An unknown result is WORDED, never left blank. A blank cell
                # in a money column reads as zero, and the projection reaches
                # `None` from several distinct unknowns -- an unmodelled
                # settlement chain, no calculation yet, a cell not computed --
                # none of which is a figure.
                row.settled_result or declarations_copy("tui.declarations.value.result_unknown"),
                key=row.work_unit_id,
            )
        if not table.row_count:
            self.show_empty()
        restored = self.controller.restored_id("declarations.work")
        row_index = next((i for i, item in enumerate(table.ordered_rows) if item.key.value == restored), None)
        if row_index is None:
            self.query_one("#declarations-navigation", DataTable).focus()
        else:
            table.move_cursor(row=row_index)
            table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Route a navigation row or invoke the injected declaration handoff."""
        if self.handle_navigation(event):
            return
        table = cast("DataTable[str]", event.data_table)
        if table.id != "declarations-list" or event.row_key.value is None:
            return
        row = next(item for item in self.controller.projection.declarations if item.work_unit_id == event.row_key.value)
        self.selected_work_unit_id = row.work_unit_id
        factory = self.controller.modelo_workspace_factory
        if factory is None:
            self.refuse_handoff()
        else:
            child = factory(row)
            cast("App[None]", self.app).push_screen(child, self._restore_declaration_focus)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Create only the explicit natural address the operator supplied."""
        if event.button.id != "declarations-work-create":
            return
        handoff = self.controller.work_create_handoff
        if handoff is None:
            self.refuse_handoff()
            return
        if self._work_create_in_flight:
            return
        modelo = self.query_one("#declarations-work-modelo", Input).value.strip()
        year_text = self.query_one("#declarations-work-year", Input).value.strip()
        period_text = self.query_one("#declarations-work-period", Input).value.strip()
        notice = self.query_one("#declarations-work-create-notice", Static)
        if not modelo:
            notice.update(declarations_copy("tui.declarations.work_create.refusal.modelo"))
            return
        if not year_text.isascii() or not year_text.isdecimal():
            notice.update(declarations_copy("tui.declarations.work_create.refusal.year"))
            return
        filing_year = int(year_text)
        if not FILING_YEAR_MIN <= filing_year <= FILING_YEAR_MAX:
            notice.update(declarations_copy("tui.declarations.work_create.refusal.year"))
            return
        try:
            period = Period.from_year_and_code(filing_year, period_text)
        except PeriodError:
            notice.update(declarations_copy("tui.declarations.work_create.refusal.period"))
            return
        # The write runs on a worker thread that cancelling cannot stop, so a
        # second press waits for the first instead of replacing it: its result
        # would otherwise land unreported under fields that now name another
        # declaration.
        self._work_create_in_flight = True
        notice.update(declarations_copy("tui.declarations.work_create.progress"))
        self.run_worker(
            self._submit_work_create(handoff, modelo, filing_year, period),
            group="declarations-work-create",
        )

    async def _submit_work_create(
        self, handoff: ModeloWorkCreateHandoffV1, modelo: str, filing_year: int, period: Period
    ) -> None:
        """Run the storage-backed application command off Textual's event loop."""
        notice = self.query_one("#declarations-work-create-notice", Static)
        try:
            result = await asyncio.to_thread(handoff, modelo, filing_year, period)
        except CadrumoError as refusal:
            notice.update(work_create_refusal_message(refusal))
            return
        finally:
            self._work_create_in_flight = False
        message_key = "tui.declarations.work_create.reused" if result.reused else "tui.declarations.work_create.created"
        notice.update(declarations_copy(message_key, address=natural_address(modelo, filing_year, period)))

    def _restore_declaration_focus(self, _: None) -> None:
        """Restore the semantic declaration table after its child dismisses."""
        table = cast("DataTable[str]", self.query_one("#declarations-list", DataTable))
        row_index = next(
            (
                index
                for index, table_row in enumerate(table.ordered_rows)
                if table_row.key.value == self.selected_work_unit_id
            ),
            None,
        )
        if row_index is not None:
            table.move_cursor(row=row_index)
        table.focus()


class DeclarationsModeloWorkspaceLauncherScreen(DeclarationsOverviewScreen):
    """Select a declaration and open its injected existing Modelo workspace."""

    # It shares the overview's mechanics but is an area, so Back returns there.
    IS_WORKSPACE_OVERVIEW: ClassVar[bool] = False

    def __init__(self, controller: DeclarationsWorkspaceController) -> None:
        """Use the landing selection mechanics under a distinct route identity."""
        super().__init__(controller, id="declarations-modelo-workspace-launcher-screen")


__all__ = ["DeclarationsModeloWorkspaceLauncherScreen", "DeclarationsOverviewScreen"]
