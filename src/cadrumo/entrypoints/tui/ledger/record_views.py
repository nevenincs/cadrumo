"""Canonical invoice catalogue and invoice detail flows for the Ledger workspace.

The catalogue lists the invoices the registered list operation returns, one
page at a time, and opens one invoice by its full identity. The detail screen
corrects or removes that invoice against the snapshot the operator saw: a
correction is staged and shown field by field before it is saved, and a
removal is confirmed in a dialog before anything is written.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Select, Static

from ....application.invoices.catalogue_lifecycle import CatalogueInvoicePatch
from ....application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot, InvoiceLineSnapshot
from ....core.aggregation import IntracomOperationType
from ....core.decimal.grammar import try_parse_canonical_decimal
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....core.parsing.dates import require_iso8601_date_unless_blank
from ....domain.invoices.enums import PaymentStatus
from ....domain.iva.schema import InvoiceKind
from ..components.dialogs import ConfirmScreen
from ..components.language import localized, repaint_tables
from ..components.theme import tokenised
from ..components.widgets import ContentDataTable
from ..components.workspace_host import replace_workspace_body
from ..operations.outcome import unknown_outcome_of
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from .models import LedgerRecordDoorsV1
from .workspace_presentation import door_refusal_text, ledger_workspace_page

INVOICE_PAGE_SIZE: Final = 100
"""Rows the catalogue renders at once; the rest stay behind next and previous."""

_ALL_KINDS: Final = "all"
_KIND_LOCALE_KEYS: Final = {
    InvoiceKind.ISSUED: "tui.ledger.invoice.kind.issued",
    InvoiceKind.RECEIVED: "tui.ledger.invoice.kind.received",
}
_PAYMENT_STATUS_LOCALE_KEYS: Final[dict[PaymentStatus, str]] = {
    PaymentStatus.PAID: "tui.ledger.records.payment_status.paid",
    PaymentStatus.PENDING: "tui.ledger.records.payment_status.pending",
    PaymentStatus.PARTIALLY_PAID: "tui.ledger.records.payment_status.partially_paid",
    PaymentStatus.OVERDUE: "tui.ledger.records.payment_status.overdue",
    PaymentStatus.CANCELLED: "tui.ledger.records.payment_status.cancelled",
}
_TEXT_FIELDS: Final = (
    "counterparty_name",
    "counterparty_country",
    "series",
    "rectifies_invoice_number",
    "operation_date",
    "retention_rate",
    "retention_amount",
    "notes",
)
"""Correctable text fields, in the order the form shows them."""
_FIELD_LABEL_KEYS: Final = {
    "counterparty_name": "tui.ledger.invoice.field.counterparty_name",
    "counterparty_country": "tui.ledger.invoice.field.country_code",
    "series": "tui.ledger.invoice.field.series",
    "rectifies_invoice_number": "tui.ledger.invoice.field.rectifies_invoice_number",
    "operation_date": "tui.ledger.invoice.field.operation_date",
    "retention_rate": "tui.ledger.invoice.field.retention_rate",
    "retention_amount": "tui.ledger.invoice.field.retention_amount",
    "notes": "tui.ledger.invoice.field.notes",
    "payment_status": "tui.ledger.records.field.payment_status",
    "operation_type": "tui.ledger.invoice.field.operation_type",
}
_EDIT_CONTROLS: Final = (
    *(f"#ledger-invoice-{name.replace('_', '-')}" for name in _TEXT_FIELDS),
    "#ledger-invoice-payment-status",
    "#ledger-invoice-operation-type",
)


def _kind_label(kind: InvoiceKind) -> str:
    return tr(_KIND_LOCALE_KEYS[kind])


def _payment_label(status: PaymentStatus) -> str:
    return tr(_PAYMENT_STATUS_LOCALE_KEYS[status])


def _line_row(index: int, line: InvoiceLineSnapshot) -> str:
    return tr(
        "tui.ledger.invoice.line.row",
        index=str(index),
        description=line.description,
        quantity=line.quantity.decimal,
        unit_price=line.unit_price.decimal,
        subtotal=line.subtotal.decimal,
        rate=line.iva_rate,
        amount=line.iva_amount.decimal,
    )


def _invoice_supplemental_rows(invoice: CatalogueInvoiceSnapshot) -> list[str]:
    rows: list[str] = []
    if invoice.operation_type is not None or invoice.operation_date is not None:
        rows.append(
            tr(
                "tui.ledger.invoice.summary.operation",
                code="-" if invoice.operation_type is None else invoice.operation_type.value,
                date="-" if invoice.operation_date is None else invoice.operation_date.isoformat(),
            )
        )
    if invoice.recargo_amount is not None:
        rows.append(
            tr("tui.ledger.invoice.summary.recargo", amount=invoice.recargo_amount.decimal, currency=invoice.currency)
        )
    if invoice.rectifies_invoice_number is not None:
        rows.append(tr("tui.ledger.invoice.summary.rectifies", number=invoice.rectifies_invoice_number))
    if invoice.retention_rate is not None or invoice.retention_amount is not None:
        rows.append(
            tr(
                "tui.ledger.invoice.summary.retention",
                rate="-" if invoice.retention_rate is None else invoice.retention_rate.decimal,
                amount="-" if invoice.retention_amount is None else invoice.retention_amount.decimal,
            )
        )
    return rows


def _invoice_detail_rows(invoice: CatalogueInvoiceSnapshot) -> list[str]:
    linked_ids = ", ".join(invoice.linked_transaction_ids) or "-"
    source = (
        f"{invoice.source_filename}:{invoice.source_row_index or '-'}" if invoice.source_filename is not None else "-"
    )
    rows = [
        f"{_kind_label(invoice.kind)} · {invoice.invoice_number} · {invoice.issued_at.isoformat()}",
        f"{invoice.counterparty_name} · {invoice.counterparty_tax_id or '-'} · {invoice.counterparty_country}",
        tr(
            "tui.ledger.records.totals",
            base=invoice.base_total.decimal,
            iva=invoice.iva_total.decimal,
            total=invoice.grand_total.decimal,
            currency=invoice.currency,
        ),
        f"{tr('tui.ledger.records.field.payment_status')}: {_payment_label(invoice.payment_status)}",
        tr("tui.ledger.records.lines"),
        *(_line_row(index, line) for index, line in enumerate(invoice.lines, start=1)),
    ]
    rows.extend(_invoice_supplemental_rows(invoice))
    rows.extend(
        (
            f"{tr('tui.ledger.records.links')}: {linked_ids}",
            f"{tr('tui.ledger.records.source')}: {source}",
            f"{tr('tui.ledger.records.identity')}: {invoice.invoice_id}",
        )
    )
    return rows


def _shown(value: object) -> str:
    """The value as the form shows it; absence is an empty field."""
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, PaymentStatus):
        return _payment_label(value)
    if isinstance(value, IntracomOperationType):
        return value.value
    decimal = getattr(value, "decimal", None)
    return decimal if isinstance(decimal, str) else str(value)


def _decimal_or_none(name: str, text: str) -> Decimal | None:
    if not text:
        return None
    parsed = try_parse_canonical_decimal(text, signed=False)
    if parsed is None:
        raise ValueError(tr("tui.ledger.records.invalid_decimal", field=tr(_FIELD_LABEL_KEYS[name])))
    return parsed


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
                    *((_kind_label(kind), kind.value) for kind in InvoiceKind),
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
                _kind_label(invoice.kind),
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
        if event.data_table.id == "ledger-invoice-catalogue" and event.row_key.value is not None:
            replace_workspace_body(
                self.app,
                LedgerInvoiceDetailScreen(self.controller, self.doors, str(event.row_key.value)),
            )


class LedgerInvoiceDetailScreen(LedgerWorkspaceScreen):
    """Read an invoice, then correct or remove it against the snapshot the operator saw."""

    DEFAULT_CSS = tokenised(
        """
        .ledger-invoice-actions { height: auto; margin-bottom: $cadrumo-stack; }
        .ledger-invoice-actions Button { margin-right: $cadrumo-space-1; }
        #ledger-invoice-staged { height: auto; text-style: bold; }
        """
    )

    def __init__(self, controller: LedgerWorkspaceController, doors: LedgerRecordDoorsV1, invoice_id: str) -> None:
        """Capture the selected invoice and doors before any navigation changes."""
        super().__init__(controller, id="ledger-invoice-detail-screen")
        self.doors = doors
        self.invoice_id = invoice_id
        self.baseline: CatalogueInvoiceSnapshot | None = None
        self.staged: CatalogueInvoicePatch | None = None
        self._busy = False

    @property
    @override
    def in_flight(self) -> bool:
        """The invoice read, its correction or its removal is out through a door."""
        return self._busy

    @override
    def compose(self) -> ComposeResult:
        yield localized(
            Static(tr("tui.ledger.records.invoice_detail"), classes="cadrumo-banner"),
            "tui.ledger.records.invoice_detail",
        )
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static("", id="ledger-record-detail", markup=False)
            yield Static("", id="ledger-invoice-staged", markup=False)
            with Horizontal(id="ledger-invoice-decision", classes="ledger-invoice-actions"):
                yield localized(
                    Button(tr("tui.ledger.records.save"), id="ledger-invoice-edit-save", variant="primary"),
                    "tui.ledger.records.save",
                )
                yield localized(
                    Button(tr("tui.ledger.records.cancel"), id="ledger-invoice-edit-cancel"),
                    "tui.ledger.records.cancel",
                )
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)
            yield localized(
                Static(tr("tui.ledger.records.correct_heading"), classes="cadrumo-heading", markup=False),
                "tui.ledger.records.correct_heading",
            )
            for name in _TEXT_FIELDS:
                yield localized(Static(tr(_FIELD_LABEL_KEYS[name]), markup=False), _FIELD_LABEL_KEYS[name])
                yield Input(id=f"ledger-invoice-{name.replace('_', '-')}", disabled=True)
            yield localized(
                Static(tr(_FIELD_LABEL_KEYS["payment_status"]), markup=False), _FIELD_LABEL_KEYS["payment_status"]
            )
            yield Select[str](
                tuple((_payment_label(status), status.value) for status in PaymentStatus),
                allow_blank=True,
                id="ledger-invoice-payment-status",
                disabled=True,
            )
            yield localized(
                Static(tr(_FIELD_LABEL_KEYS["operation_type"]), markup=False), _FIELD_LABEL_KEYS["operation_type"]
            )
            yield Select[str](
                tuple((key.value, key.value) for key in IntracomOperationType),
                prompt=tr("tui.ledger.invoice.operation_type_none"),
                allow_blank=True,
                id="ledger-invoice-operation-type",
                disabled=True,
            )
            with Horizontal(classes="ledger-invoice-actions"):
                yield localized(
                    Button(tr("tui.ledger.invoice.review"), id="ledger-invoice-edit-review", disabled=True),
                    "tui.ledger.invoice.review",
                )
                yield localized(
                    Button(tr("tui.ledger.records.remove"), id="ledger-invoice-remove", variant="error", disabled=True),
                    "tui.ledger.records.remove",
                )

    def on_mount(self) -> None:
        """Read the current canonical snapshot before enabling a change."""
        self.populate_navigation()
        self.query_one("#ledger-invoice-decision", Horizontal).display = False
        self._busy = True
        self.run_worker(self._load(), exclusive=True)

    async def _load(self) -> None:
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.records.loading"))
        try:
            invoice = await self.doors.invoice(self.invoice_id)
        except CadrumoError as error:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.records.failed"))
        else:
            self._show_invoice(invoice)
            self.query_one("#ledger-flow-status", Static).update("")
        finally:
            self._busy = False

    def _text(self, name: str) -> str:
        return self.query_one(f"#ledger-invoice-{name.replace('_', '-')}", Input).value

    def _select(self, selector: str) -> str | None:
        value = cast("Select[str]", self.query_one(selector, Select)).value
        return value if isinstance(value, str) else None

    def _changes(self, baseline: CatalogueInvoiceSnapshot) -> dict[str, object]:
        """Every field whose entered value differs from the snapshot, as the patch types it."""
        entered: dict[str, object] = {
            "counterparty_name": self._text("counterparty_name").strip(),
            "counterparty_country": self._text("counterparty_country").strip().upper(),
            "series": self._text("series").strip() or None,
            "rectifies_invoice_number": self._text("rectifies_invoice_number").strip() or None,
            "operation_date": require_iso8601_date_unless_blank(self._text("operation_date")),
            "retention_rate": _decimal_or_none("retention_rate", self._text("retention_rate").strip()),
            "retention_amount": _decimal_or_none("retention_amount", self._text("retention_amount").strip()),
            "notes": self._text("notes"),
        }
        status = self._select("#ledger-invoice-payment-status")
        if status is not None:
            entered["payment_status"] = PaymentStatus(status)
        operation_type = self._select("#ledger-invoice-operation-type")
        entered["operation_type"] = None if operation_type is None else IntracomOperationType(operation_type)
        changes: dict[str, object] = {}
        for name, value in entered.items():
            current = getattr(baseline, name)
            current_value = (
                Decimal(current.decimal) if name.startswith("retention_") and current is not None else current
            )
            if value != current_value:
                changes[name] = value
        return changes

    def _stage(self) -> None:
        baseline = self.baseline
        if baseline is None:
            return
        refusal = self.query_one("#ledger-refusal", Static)
        refusal.update("")
        try:
            changes = self._changes(baseline)
            if not changes:
                raise ValueError(tr("tui.ledger.records.no_change"))
            patch = CatalogueInvoicePatch.model_validate(changes)
        except ValidationError as error:
            refusal.update(door_refusal_text(error))
            return
        except ValueError as error:
            refusal.update(str(error))
            return
        self.staged = patch
        lines = [
            tr(
                "tui.ledger.records.change",
                field=tr(_FIELD_LABEL_KEYS[name]),
                before=_shown(getattr(baseline, name)) or "-",
                after=_shown(value) or "-",
            )
            for name, value in changes.items()
        ]
        self.query_one("#ledger-invoice-staged", Static).update(
            "\n".join((tr("tui.ledger.records.staged_heading"), *lines))
        )
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.records.reviewed"))
        self._set_staged_controls(staged=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Stage a correction, save exactly the staged correction, or ask before removing."""
        if self._busy:
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.flow.in_flight_refusal"))
            return
        if self.baseline is None:
            return
        button_id = event.button.id
        if button_id == "ledger-invoice-edit-review":
            self._stage()
        elif button_id == "ledger-invoice-edit-cancel":
            self._unstage()
        elif button_id == "ledger-invoice-edit-save" and self.staged is not None:
            self._busy = True
            self.query_one("#ledger-invoice-edit-save", Button).disabled = True
            self.query_one("#ledger-invoice-edit-cancel", Button).disabled = True
            self.run_worker(self._save(self.baseline, self.staged), exclusive=True)
        elif button_id == "ledger-invoice-remove":
            self._ask_remove(self.baseline)

    def _ask_remove(self, baseline: CatalogueInvoiceSnapshot) -> None:
        def decided(confirmed: bool | None) -> None:
            if confirmed is True and not self._busy and self.baseline == baseline:
                self._busy = True
                self.query_one("#ledger-invoice-remove", Button).disabled = True
                self.run_worker(self._remove(baseline), exclusive=True)
            else:
                self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.records.remove_cancelled"))

        self.app.push_screen(
            ConfirmScreen(
                title=lambda: tr("tui.ledger.records.remove_title"),
                message=lambda: tr(
                    "tui.ledger.records.remove_message",
                    number=baseline.invoice_number,
                    counterparty=baseline.counterparty_name,
                    total=f"{baseline.grand_total.decimal} {baseline.currency}",
                ),
                confirm_label=lambda: tr("tui.ledger.records.remove"),
                cancel_label=lambda: tr("tui.ledger.records.cancel"),
            ),
            decided,
        )

    async def _save(self, baseline: CatalogueInvoiceSnapshot, patch: CatalogueInvoicePatch) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        status.update(tr("tui.ledger.records.saving"))
        try:
            updated = await self.doors.update_invoice(baseline, patch)
        except CadrumoError as error:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            status.update(self.failed_write_status(error, "tui.ledger.records.failed"))
            self._busy = False
            if unknown_outcome_of(error) is not None:
                # The correction may be saved; offering it again could apply it twice.
                self._unstage()
                return
            self.query_one("#ledger-invoice-edit-save", Button).disabled = False
            self.query_one("#ledger-invoice-edit-cancel", Button).disabled = False
            return
        self._busy = False
        self._unstage()
        self._show_invoice(updated)
        status.update(tr("tui.ledger.records.saved"))

    async def _remove(self, baseline: CatalogueInvoiceSnapshot) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        status.update(tr("tui.ledger.records.removing"))
        try:
            removed = await self.doors.remove_invoice(baseline)
        except CadrumoError as error:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            status.update(self.failed_write_status(error, "tui.ledger.records.failed"))
            self._busy = False
            # A removal whose outcome is unknown may have removed the invoice, so it is not offered again.
            self.query_one("#ledger-invoice-remove", Button).disabled = unknown_outcome_of(error) is not None
            return
        self._busy = False
        replace_workspace_body(
            self.app,
            LedgerInvoiceCatalogueScreen(
                self.controller,
                self.doors,
                notice=tr("tui.ledger.records.removed", number=removed.invoice_number),
            ),
        )

    def _show_invoice(self, invoice: CatalogueInvoiceSnapshot) -> None:
        """Render one canonical snapshot and prefill the form with its current values."""
        self.baseline = invoice
        self.invoice_id = invoice.invoice_id
        self.query_one("#ledger-record-detail", Static).update("\n".join(_invoice_detail_rows(invoice)))
        for name in _TEXT_FIELDS:
            current = getattr(invoice, name)
            self.query_one(f"#ledger-invoice-{name.replace('_', '-')}", Input).value = (
                current.decimal if name.startswith("retention_") and current is not None else _shown(current)
            )
        cast(
            "Select[str]", self.query_one("#ledger-invoice-payment-status", Select)
        ).value = invoice.payment_status.value
        operation_type = cast("Select[str]", self.query_one("#ledger-invoice-operation-type", Select))
        if invoice.operation_type is None:
            operation_type.clear()
        else:
            operation_type.value = invoice.operation_type.value
        self._set_staged_controls(staged=False)

    def _set_staged_controls(self, *, staged: bool) -> None:
        """Freeze the form while a correction is staged, so only the reviewed patch is saved."""
        for selector in _EDIT_CONTROLS:
            self.query_one(selector).disabled = staged
        self.query_one("#ledger-invoice-edit-review", Button).disabled = staged
        self.query_one("#ledger-invoice-remove", Button).disabled = staged
        self.query_one("#ledger-invoice-edit-save", Button).disabled = not staged
        self.query_one("#ledger-invoice-edit-cancel", Button).disabled = not staged
        self.query_one("#ledger-invoice-decision", Horizontal).display = staged

    def _unstage(self) -> None:
        self.staged = None
        self.query_one("#ledger-invoice-staged", Static).update("")
        self._set_staged_controls(staged=False)

    @override
    def action_back(self) -> None:
        """Return to the catalogue on the invoice shown here; never while a write is in flight."""
        if self.refuse_leaving():
            return
        catalogue = LedgerInvoiceCatalogueScreen(self.controller, self.doors, selected_id=self.invoice_id)
        if not replace_workspace_body(self.app, catalogue):
            super().action_back()


__all__ = ["INVOICE_PAGE_SIZE", "LedgerInvoiceCatalogueScreen", "LedgerInvoiceDetailScreen"]
