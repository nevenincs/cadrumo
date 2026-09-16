"""Ledger evidence: the attachment review queue, local invoice documents, and adding one."""

from __future__ import annotations

from typing import Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Input, Static

from ....core.errors.hierarchy import CadrumoError
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import (
    LedgerEvidenceReviewRequested,
    LedgerWorkspaceController,
    LedgerWorkspaceScreen,
    ledger_copy,
)
from .models import LedgerEvidenceRecordRowV1, LedgerEvidenceRecordStatus
from .workspace_presentation import door_refusal_text

_RECORD_STATUS_LOCALE_KEYS: Final[dict[LedgerEvidenceRecordStatus, str]] = {
    LedgerEvidenceRecordStatus.AWAITING: "tui.ledger.evidence.record_status.awaiting",
    LedgerEvidenceRecordStatus.CONFIRMED: "tui.ledger.evidence.record_status.confirmed",
    LedgerEvidenceRecordStatus.DECLINED: "tui.ledger.evidence.record_status.declined",
    LedgerEvidenceRecordStatus.UNMEASURED: "tui.ledger.evidence.record_status.unmeasured",
}
_READING_REFUSAL_LOCALE_KEYS: Final[dict[str, str]] = {
    "ledger-evidence-extract": "tui.ledger.evidence.reading_refused.extract",
    "ledger-evidence-confirm": "tui.ledger.evidence.reading_refused.confirm",
}


class LedgerEvidenceScreen(LedgerWorkspaceScreen):
    """Render safe evidence metadata without document contents or source locators."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain an injected canonical review queue."""
        super().__init__(controller, id="ledger-evidence-screen")
        self.selected_evidence_id: str | None = None
        self.selected_record_id: str | None = None
        self.requested_review: LedgerEvidenceReviewRequested | None = None
        self._records: tuple[LedgerEvidenceRecordRowV1, ...] | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.evidence.title"), classes="cadrumo-banner")
        with ContentScroll(id="ledger-page", classes="cadrumo-scroll ledger-page"):
            yield ContentDataTable[str](id="ledger-navigation", cursor_type="row", zebra_stripes=True)
            yield Static(ledger_copy("tui.ledger.evidence.safe_metadata"), markup=False)
            yield Static(ledger_copy("tui.ledger.evidence.queue_heading"), classes="cadrumo-heading", markup=False)
            yield ContentDataTable[str](id="ledger-evidence", cursor_type="row", zebra_stripes=True)
            yield Static("", id="ledger-evidence-detail", markup=False)
            if self.controller.evidence_door is not None:
                yield Static(
                    ledger_copy("tui.ledger.evidence.records_heading"), classes="cadrumo-heading", markup=False
                )
                yield Static("", id="ledger-evidence-reader", markup=False)
                yield ContentDataTable[str](id="ledger-evidence-records", cursor_type="row", zebra_stripes=True)
                yield Static("", id="ledger-evidence-record-detail", markup=False)
                yield Button(ledger_copy("tui.ledger.evidence.extract"), id="ledger-evidence-extract", disabled=True)
                yield Button(ledger_copy("tui.ledger.evidence.confirm"), id="ledger-evidence-confirm", disabled=True)
                yield Static(ledger_copy("tui.ledger.evidence.add_label"), markup=False)
                yield Input(placeholder=ledger_copy("tui.ledger.evidence.path_placeholder"), id="ledger-evidence-path")
                yield Button(ledger_copy("tui.ledger.evidence.add"), id="ledger-evidence-add", variant="primary")
                yield Static("", id="ledger-flow-status", markup=False)
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate application-supplied safe metadata with semantic row keys."""
        self.populate_navigation()
        table = cast("DataTable[str]", self.query_one("#ledger-evidence", DataTable))
        table.add_column(ledger_copy("tui.ledger.column.entry"))
        table.add_column(ledger_copy("tui.ledger.evidence.column.type"))
        table.add_column(ledger_copy("tui.ledger.evidence.column.status"))
        rows = self.controller.evidence_rows()
        for position, row in enumerate(rows, start=1):
            status_key = "tui.ledger.evidence.pending" if row.pending_review else "tui.ledger.evidence.reviewed"
            table.add_row(str(position), row.mime_type, ledger_copy(status_key), key=row.attachment_id)
        if not rows:
            self.query_one("#ledger-evidence-detail", Static).update(ledger_copy("tui.ledger.evidence.empty"))
        restored = self.controller.restored_evidence_id()
        if restored is not None:
            index = next(index for index, row in enumerate(table.ordered_rows) if row.key.value == restored)
            table.move_cursor(row=index)
        if self.controller.evidence_door is not None:
            records = cast("DataTable[str]", self.query_one("#ledger-evidence-records", DataTable))
            records.add_column(ledger_copy("tui.ledger.column.entry"), key="position")
            records.add_column(ledger_copy("tui.ledger.evidence.column.file"), key="file")
            records.add_column(ledger_copy("tui.ledger.evidence.column.invoice"), key="invoice")
            records.add_column(ledger_copy("tui.ledger.evidence.column.status"), key="status")
            self._show_records()
            self._show_reader()
        table.focus()

    def _show_records(self) -> None:
        records = cast("DataTable[str]", self.query_one("#ledger-evidence-records", DataTable))
        records.clear()
        self._records = self.controller.evidence_records()
        for position, record in enumerate(self._records or (), start=1):
            records.add_row(
                str(position),
                record.file_name,
                record.invoice_number or "-",
                ledger_copy(_RECORD_STATUS_LOCALE_KEYS[record.status]),
                key=record.evidence_id,
            )
        if not self._records:
            self.query_one("#ledger-evidence-record-detail", Static).update(
                ledger_copy("tui.ledger.evidence.records_empty")
            )

    def _show_reader(self) -> None:
        readiness = self.controller.reader_readiness()
        line = self.query_one("#ledger-evidence-reader", Static)
        if readiness is None:
            line.update("")
        elif readiness.extraction_ready:
            line.update(ledger_copy("tui.ledger.evidence.reader_ready"))
        else:
            line.update(
                ledger_copy(
                    "tui.ledger.evidence.reader_not_ready",
                    condition=readiness.failed_condition_id or "-",
                )
            )

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
            ledger_copy(
                "tui.ledger.evidence.detail",
                size=row.bytes_size,
                captured=row.captured_at,
            )
        )

    def _select_record(self, evidence_id: str) -> None:
        record = next(item for item in self._records or () if item.evidence_id == evidence_id)
        self.selected_record_id = evidence_id
        self.query_one("#ledger-evidence-record-detail", Static).update(
            ledger_copy(
                "tui.ledger.evidence.record_detail",
                kind=record.media_kind,
                supplier=record.supplier or "-",
                added=record.created_at,
                status=ledger_copy(_RECORD_STATUS_LOCALE_KEYS[record.status]),
            )
        )
        self.query_one("#ledger-evidence-extract", Button).disabled = False
        self.query_one("#ledger-evidence-confirm", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Add a document, or explain why reading one cannot start here."""
        match event.button.id:
            case "ledger-evidence-add":
                self._add()
            case "ledger-evidence-extract" | "ledger-evidence-confirm" if self.selected_record_id is not None:
                self._refuse_reading(event.button.id)
            case _:
                return

    def _refuse_reading(self, button_id: str) -> None:
        """Gate reading on the reader's own readiness claim, and say what to do next."""
        readiness = self.controller.reader_readiness()
        notice = self.query_one("#ledger-refusal", Static)
        self._show_reader()
        if readiness is None or not readiness.extraction_ready:
            notice.update(
                ledger_copy(
                    "tui.ledger.evidence.reading_refused.reader",
                    condition="-" if readiness is None else readiness.failed_condition_id or "-",
                )
            )
            return
        notice.update(ledger_copy(_READING_REFUSAL_LOCALE_KEYS[button_id], evidence_id=self.selected_record_id))

    def _add(self) -> None:
        raw = self.query_one("#ledger-evidence-path", Input).value.strip()
        notice = self.query_one("#ledger-refusal", Static)
        if not raw:
            notice.update(ledger_copy("tui.ledger.import.path_required"))
            return
        notice.update("")
        self.query_one("#ledger-evidence-add", Button).disabled = True
        self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.evidence.adding"))
        self.run_worker(self._submit_add(raw), exclusive=True)

    async def _submit_add(self, source_path: str) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        try:
            record = await self.controller.add_evidence(source_path)
        except (CadrumoError, ValidationError) as error:
            status.update(ledger_copy("tui.ledger.evidence.add_failed"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        else:
            status.update(ledger_copy("tui.ledger.evidence.added", file=record.file_name))
            self.query_one("#ledger-evidence-path", Input).value = ""
            self._reread()
        self.query_one("#ledger-evidence-add", Button).disabled = False

    def _reread(self) -> None:
        """Re-read the workspace so the area counts include the new document."""
        if self.controller.can_refresh():
            try:
                self.controller = self.controller.refreshed()
            except CadrumoError:
                self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.flow.refresh_failed"))
            else:
                navigation = cast("DataTable[str]", self.query_one("#ledger-navigation", DataTable))
                navigation.clear(columns=True)
                self.populate_navigation()
        self._show_records()


__all__ = ["LedgerEvidenceScreen"]
