"""Data-quality-first Ledger overview over an injected workspace projection."""

from __future__ import annotations

from typing import ClassVar, cast, override

from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Static

from ....application.ledger.workspace import LedgerWorkspaceArea
from ....core.i18n.render import tr
from ..components.widgets import ContentDataTable, ContentScroll
from ..components.workspace_host import replace_workspace_body
from .actividad_asset import ActivityAssetScreen
from .controller import (
    LedgerInvoiceCatalogueRequested,
    LedgerInvoiceEntryRequested,
    LedgerWorkspaceController,
    LedgerWorkspaceScreen,
    area_label,
    item_count_label,
    status_label,
)
from .own_accounts import LedgerOwnAccountsScreen


class LedgerOverviewScreen(LedgerWorkspaceScreen):
    """Lead with unresolved work and affected declarations, never financial totals."""

    IS_WORKSPACE_OVERVIEW: ClassVar[bool] = True
    AUTO_FOCUS: ClassVar[str | None] = ""
    """No compose-time focus: it centres the table before layout and scrolls a tall page past its heading."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain the injected read-only workspace controller."""
        super().__init__(controller, id="ledger-overview-screen")

    @override
    def compose(self) -> ComposeResult:
        yield Static(tr("tui.ledger.overview.title"), classes="cadrumo-banner")
        with ContentScroll(id="ledger-page", classes="cadrumo-scroll ledger-page"):
            yield Static(
                tr("tui.ledger.overview.areas"),
                classes="cadrumo-heading cadrumo-heading-lead",
                markup=False,
            )
            yield ContentDataTable[str](id="ledger-navigation", cursor_type="row", zebra_stripes=True)
            yield Static(tr("tui.ledger.overview.quality"), classes="cadrumo-heading", markup=False)
            yield ContentDataTable[str](id="ledger-quality", cursor_type="row", zebra_stripes=True)
            if self.controller.can_add_invoices():
                yield Button(tr("tui.ledger.invoice.open"), id="ledger-add-invoice")
            if self.controller.record_doors is not None:
                yield Button(tr("tui.ledger.records.open_invoices"), id="ledger-open-invoices")
            if self.controller.own_account_door is not None:
                yield Button(tr("tui.ledger.own_accounts.open"), id="ledger-own-accounts-open")
            if self.controller.can_manage_activity_assets():
                yield Button("Activos amortizables", id="ledger-activity-assets")
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate the complete navigation and quality-first summary."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-quality", DataTable))
        table.add_column(tr("tui.ledger.column.area"), key="area")
        table.add_column(tr("tui.ledger.column.status"), key="status")
        table.add_column(tr("tui.ledger.column.items"), key="items")
        for area in (
            LedgerWorkspaceArea.REVIEW,
            LedgerWorkspaceArea.CLASSIFICATION,
            LedgerWorkspaceArea.EVIDENCE,
            LedgerWorkspaceArea.RECONCILIATION,
        ):
            state = self.controller.state_for(area)
            status = status_label(state.status)
            table.add_row(area_label(area), status, item_count_label(state), key=area.value)
        affected = len(self.controller.projection.affected_declarations)
        table.add_row(
            tr("tui.ledger.overview.affected_declarations"),
            (tr("tui.ledger.status.needs_attention") if affected else tr("tui.ledger.status.empty")),
            str(affected),
            key="affected-declarations",
        )
        # The table is the page's first control; scrolling to it on focus would land a
        # page taller than the terminal past its opening heading.
        self.query_one("#ledger-navigation", DataTable).focus(scroll_visible=False)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Route an Enter press on the one-stop destination table."""
        self.handle_navigation_selection(event)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Open the invoice entry form."""
        if event.button.id == "ledger-add-invoice":
            self.post_message(LedgerInvoiceEntryRequested())
        elif event.button.id == "ledger-open-invoices":
            self.post_message(LedgerInvoiceCatalogueRequested())
        elif event.button.id == "ledger-own-accounts-open" and self.controller.own_account_door is not None:
            replace_workspace_body(self.app, LedgerOwnAccountsScreen(self.controller, self.controller.own_account_door))
        elif event.button.id == "ledger-activity-assets":
            self.app.push_screen(ActivityAssetScreen(self.controller))


__all__ = ["LedgerOverviewScreen"]
