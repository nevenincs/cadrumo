"""Ledger evidence: the attachment review queue, local invoice documents, and adding one."""

from __future__ import annotations

from typing import Final, cast, override

from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Input, Select, Static

from ....core.i18n.render import tr
from ....domain.iva.classification import InvoiceKind
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import LedgerEvidenceReviewRequested, LedgerWorkspaceController
from .evidence_records import LedgerEvidenceRecordActions
from .models import (
    LedgerEvidenceDraftV1,
    LedgerEvidenceRecordRowV1,
)

_KIND_LOCALE_KEYS: Final[dict[InvoiceKind, str]] = {
    InvoiceKind.RECEIVED: "tui.ledger.invoice.kind.received",
    InvoiceKind.ISSUED: "tui.ledger.invoice.kind.issued",
}


class LedgerEvidenceScreen(LedgerEvidenceRecordActions):
    """Render safe evidence metadata without document contents or source locators."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain an injected canonical review queue."""
        super().__init__(controller, id="ledger-evidence-screen")
        self.selected_evidence_id: str | None = None
        self.selected_record_id: str | None = None
        self._reviewed_evidence_id: str | None = None
        self.requested_review: LedgerEvidenceReviewRequested | None = None
        self._records: tuple[LedgerEvidenceRecordRowV1, ...] | None = None
        self.draft: LedgerEvidenceDraftV1 | None = None
        self.reading = False
        """Whether a read or a confirmation is out; a second press waits for it."""

    @override
    def compose(self) -> ComposeResult:
        yield Static(tr("tui.ledger.evidence.title"), classes="cadrumo-banner")
        with ContentScroll(id="ledger-page", classes="cadrumo-scroll ledger-page"):
            yield ContentDataTable[str](id="ledger-navigation", cursor_type="row", zebra_stripes=True)
            yield Static(tr("tui.ledger.evidence.safe_metadata"), markup=False)
            if self._has_attachment_review_queue:
                yield Static(tr("tui.ledger.evidence.queue_heading"), classes="cadrumo-heading", markup=False)
                yield ContentDataTable[str](id="ledger-evidence", cursor_type="row", zebra_stripes=True)
                yield Static("", id="ledger-evidence-detail", markup=False)
            if self.controller.evidence_door is not None:
                yield Static(tr("tui.ledger.evidence.records_heading"), classes="cadrumo-heading", markup=False)
                yield Static("", id="ledger-evidence-reader", markup=False)
                yield ContentDataTable[str](id="ledger-evidence-records", cursor_type="row", zebra_stripes=True)
                yield Static("", id="ledger-evidence-record-detail", markup=False)
                yield Button(tr("tui.ledger.evidence.extract"), id="ledger-evidence-extract", disabled=True)
                yield Static("", id="ledger-evidence-draft", markup=False)
                yield Static(tr("tui.ledger.invoice.field.kind"), markup=False)
                yield Select[str](
                    tuple((tr(_KIND_LOCALE_KEYS[kind]), kind.value) for kind in InvoiceKind),
                    value=InvoiceKind.RECEIVED.value,
                    allow_blank=False,
                    id="ledger-evidence-kind",
                )
                yield Static(tr("tui.ledger.invoice.field.country_code"), markup=False)
                yield Input(value="ES", max_length=2, id="ledger-evidence-country")
                yield Static(
                    tr("tui.ledger.invoice.optional", label=tr("tui.ledger.invoice.field.counterparty_name")),
                    markup=False,
                )
                yield Input(id="ledger-evidence-counterparty")
                yield Button(tr("tui.ledger.evidence.confirm"), id="ledger-evidence-confirm", disabled=True)
                yield Static(tr("tui.ledger.evidence.add_label"), markup=False)
                yield Input(placeholder=tr("tui.ledger.evidence.path_placeholder"), id="ledger-evidence-path")
                yield Button(tr("tui.ledger.evidence.add"), id="ledger-evidence-add", variant="primary")
                yield Static("", id="ledger-flow-status", markup=False)
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate application-supplied safe metadata with semantic row keys."""
        self.populate_navigation()
        if self._has_attachment_review_queue:
            self._mount_attachment_review_queue()
        if self.controller.evidence_door is not None:
            self._mount_evidence_records()
        self._focus_initial_table()

    def _mount_attachment_review_queue(self) -> None:
        table = cast("DataTable[str]", self.query_one("#ledger-evidence", DataTable))
        table.add_column(tr("tui.ledger.column.entry"))
        table.add_column(tr("tui.ledger.evidence.column.type"))
        table.add_column(tr("tui.ledger.evidence.column.status"))
        rows = self.controller.evidence_rows()
        for position, row in enumerate(rows, start=1):
            status_key = "tui.ledger.evidence.pending" if row.pending_review else "tui.ledger.evidence.reviewed"
            table.add_row(str(position), row.mime_type, tr(status_key), key=row.attachment_id)
        if not rows:
            self.query_one("#ledger-evidence-detail", Static).update(tr("tui.ledger.evidence.empty"))
        restored = self.controller.restored_evidence_id()
        if restored is not None:
            index = next(index for index, row in enumerate(table.ordered_rows) if row.key.value == restored)
            table.move_cursor(row=index)

    def _mount_evidence_records(self) -> None:
        records = cast("DataTable[str]", self.query_one("#ledger-evidence-records", DataTable))
        records.add_column(tr("tui.ledger.column.entry"), key="position")
        records.add_column(tr("tui.ledger.evidence.column.file"), key="file")
        records.add_column(tr("tui.ledger.evidence.column.invoice"), key="invoice")
        records.add_column(tr("tui.ledger.evidence.column.status"), key="status")
        self._show_records()
        self.run_worker(self._measure_reader(), group="ledger-evidence-reader")

    def _focus_initial_table(self) -> None:
        if self._has_attachment_review_queue:
            self.query_one("#ledger-evidence", DataTable).focus()
        elif self.controller.evidence_door is not None:
            self.query_one("#ledger-evidence-records", DataTable).focus()
        else:
            self.query_one("#ledger-navigation", DataTable).focus()

    @property
    def _has_attachment_review_queue(self) -> bool:
        """Show attachment review only when its independent query supplied rows."""
        return self.controller.evidence_action is not None and self.controller.evidence_items is not None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Show safe detail for the selected evidence identity."""
        if self.handle_navigation_selection(event):
            return
        table = cast("DataTable[str]", event.data_table)
        if event.row_key.value is None:
            return
        if table.id == "ledger-evidence-records":
            self._select_record(str(event.row_key.value))
            return
        if table.id != "ledger-evidence":
            return
        evidence_id = str(event.row_key.value)
        row = next(item for item in self.controller.evidence_rows() if item.attachment_id == evidence_id)
        self.selected_evidence_id = evidence_id
        request = LedgerEvidenceReviewRequested(attachment_id=evidence_id, action=row.action)
        self.requested_review = request
        self.post_message(request)
        self.query_one("#ledger-evidence-detail", Static).update(
            tr(
                "tui.ledger.evidence.detail",
                size=row.bytes_size,
                captured=row.captured_at,
            )
        )


__all__ = ["LedgerEvidenceScreen"]
