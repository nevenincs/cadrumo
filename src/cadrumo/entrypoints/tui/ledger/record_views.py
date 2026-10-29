"""Canonical invoice catalogue and invoice detail flows for the Ledger workspace.

The catalogue lists the invoices the registered list operation returns, one
page at a time, and opens one invoice by its full identity. The detail screen
corrects or removes that invoice against the snapshot the operator saw: a
correction is staged and shown field by field before it is saved, and a
removal is confirmed in a dialog before anything is written.
"""

from __future__ import annotations

from typing import Final, cast, override

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Select, Static

from ....application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....domain.iva.schema import InvoiceKind
from ..components.language import localized, repaint_tables
from ..components.theme import tokenised
from ..components.widgets import ContentDataTable
from ..components.workspace_host import replace_workspace_body
from .controller import LedgerWorkspaceController
from .models import LedgerRecordDoorsV1
from .workspace_presentation import door_refusal_text, ledger_workspace_page
from .workspace_screen import LedgerWorkspaceScreen

INVOICE_PAGE_SIZE: Final = 100
"""Rows the catalogue renders at once; the rest stay behind next and previous."""

_ALL_KINDS: Final = "all"
_KIND_LOCALE_KEYS: Final = {
    InvoiceKind.ISSUED: "tui.ledger.invoice.kind.issued",
    InvoiceKind.RECEIVED: "tui.ledger.invoice.kind.received",
}


def invoice_kind_label(kind: InvoiceKind) -> str:
    """Render an invoice kind in the current language."""
    return tr(_KIND_LOCALE_KEYS[kind])


class LedgerInvoiceCatalogueScreen(LedgerWorkspaceScreen):
    """List the profile's canonical invoices a page at a time and open one by its full identity."""

    DEFAULT_CSS = tokenised(
        """
        .ledger-invoice-actions { height: auto; margin-bottom: $cadrumo-stack; }
        .ledger-invoice-actions Button { margin-right: $cadrumo-space-1; }
        """
    )

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        doors: LedgerRecordDoorsV1,
        *,
        selected_id: str | None = None,
        notice: str = "",
    ) -> None:
        """Keep the injected profile-bound doors and the invoice to land on, if any."""
        super().__init__(controller, id="ledger-invoice-catalogue-screen")
        self.doors = doors
        self.selected_id = selected_id
        self.page = 0
        self.invoices: tuple[CatalogueInvoiceSnapshot, ...] = ()
        self._notice = notice
        self._kind_filter = _ALL_KINDS

    @override
    def compose(self) -> ComposeResult:
        yield localized(
            Static(tr("tui.ledger.records.invoices"), classes="cadrumo-banner"), "tui.ledger.records.invoices"
        )
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(
                Static(tr("tui.ledger.records.kind_filter"), markup=False), "tui.ledger.records.kind_filter"
            )
            yield Select[str](
                (
                    (tr("tui.ledger.records.kind_all"), _ALL_KINDS),
                    *((invoice_kind_label(kind), kind.value) for kind in InvoiceKind),
                ),
                value=_ALL_KINDS,
                allow_blank=False,
                id="ledger-invoice-kind-filter",
            )
            yield ContentDataTable[str](id="ledger-invoice-catalogue", cursor_type="row", zebra_stripes=True)
            yield Static("", id="ledger-invoice-page", markup=False)
            with Horizontal(classes="ledger-invoice-actions"):
                yield localized(
                    Button(tr("tui.ledger.records.page_previous"), id="ledger-invoice-previous", disabled=True),
                    "tui.ledger.records.page_previous",
                )
                yield localized(
                    Button(tr("tui.ledger.records.page_next"), id="ledger-invoice-next", disabled=True),
                    "tui.ledger.records.page_next",
                )
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)

    @override
    async def refresh_language(self) -> None:
        """Reword headings and rows without re-reading the catalogue."""
        await super().refresh_language()
        repaint_tables(self, self._repaint)

    def on_mount(self) -> None:
        """Show headings and load canonical invoices without blocking the UI."""
        self._repaint()
        self.run_worker(self._load(), exclusive=True)

    def _repaint(self) -> None:
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-invoice-catalogue", DataTable))
        table.add_column(tr("tui.ledger.invoice.field.invoice_number"), key="number", width=14)
        table.add_column(tr("tui.ledger.column.date"), key="date", width=10)
        table.add_column(tr("tui.ledger.invoice.field.kind"), key="kind", width=10)
        table.add_column(tr("tui.ledger.invoice.field.counterparty_name"), key="counterparty", width=18)
        table.add_column(tr("tui.ledger.column.amount"), key="amount", width=14)
        self._show_page()

    async def _load(self) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        status.update(tr("tui.ledger.records.loading"))
        try:
            invoices = await self.doors.invoices()
        except CadrumoError as error:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            status.update(tr("tui.ledger.records.failed"))
            return
        self.invoices = invoices
        visible = self._visible()
        index = next((i for i, row in enumerate(visible) if row.invoice_id == self.selected_id), None)
        self.page = 0 if index is None else index // INVOICE_PAGE_SIZE
        self._show_page()
        status.update(self._notice if visible else tr("tui.ledger.records.no_invoices"))

    def _visible(self) -> tuple[CatalogueInvoiceSnapshot, ...]:
        """The invoices the kind filter keeps, in the order the operation returned them."""
        if self._kind_filter == _ALL_KINDS:
            return self.invoices
        return tuple(row for row in self.invoices if row.kind.value == self._kind_filter)

    def _show_page(self) -> None:
        """Render only the current page and restore the chosen invoice by identity."""
        visible = self._visible()
        pages = max(1, -(-len(visible) // INVOICE_PAGE_SIZE))
        self.page = min(self.page, pages - 1)
        rows = visible[self.page * INVOICE_PAGE_SIZE : (self.page + 1) * INVOICE_PAGE_SIZE]
        table = cast("DataTable[str]", self.query_one("#ledger-invoice-catalogue", DataTable))
        table.clear()
        for invoice in rows:
            table.add_row(
                invoice.invoice_number,
                invoice.issued_at.isoformat(),
                invoice_kind_label(invoice.kind),
                invoice.counterparty_name,
                f"{invoice.grand_total.decimal} {invoice.currency}",
                key=invoice.invoice_id,
            )
        self.query_one("#ledger-invoice-page", Static).update(
            tr("tui.ledger.records.page", page=str(self.page + 1), pages=str(pages), count=str(len(visible)))
        )
        self.query_one("#ledger-invoice-previous", Button).disabled = self.page == 0
        self.query_one("#ledger-invoice-next", Button).disabled = self.page >= pages - 1
        index = next((i for i, row in enumerate(rows) if row.invoice_id == self.selected_id), None)
        if index is not None:
            table.move_cursor(row=index)
        if rows:
            table.focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Filter by invoice kind, starting again from the first page."""
        # Textual also announces the initial value, which must not move the page.
        if event.select.id == "ledger-invoice-kind-filter" and str(event.value) != self._kind_filter:
            self._kind_filter = str(event.value)
            self.page = 0
            self._show_page()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Move one page back or forward."""
        if event.button.id == "ledger-invoice-previous":
            self.page = max(0, self.page - 1)
        elif event.button.id == "ledger-invoice-next":
            self.page += 1
        else:
            return
        self._show_page()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the selected invoice by its stable catalogue identity."""
        if self.handle_navigation_selection(event):
            return
        if (
            cast("DataTable[str]", event.data_table).id == "ledger-invoice-catalogue"
            and event.row_key.value is not None
        ):
            from .invoice_detail import LedgerInvoiceDetailScreen

            replace_workspace_body(
                self.app,
                LedgerInvoiceDetailScreen(self.controller, self.doors, str(event.row_key.value)),
            )


__all__ = ["INVOICE_PAGE_SIZE", "LedgerInvoiceCatalogueScreen", "invoice_kind_label"]
