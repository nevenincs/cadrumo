"""Ledger evidence: the attachment review queue, local invoice documents, and adding one."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Input, Select, Static

from ....core.errors.hierarchy import CadrumoError
from ....domain.iva.classification import InvoiceKind
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import (
    LedgerEvidenceReviewRequested,
    LedgerWorkspaceController,
    LedgerWorkspaceScreen,
    ledger_copy,
)
from .models import (
    LedgerEvidenceConfirmationV1,
    LedgerEvidenceDraftV1,
    LedgerEvidenceRecordRowV1,
    LedgerEvidenceRecordStatus,
    LedgerReaderReadinessV1,
)
from .workspace_presentation import door_refusal_text

_RECORD_STATUS_LOCALE_KEYS: Final[dict[LedgerEvidenceRecordStatus, str]] = {
    LedgerEvidenceRecordStatus.AWAITING: "tui.ledger.evidence.record_status.awaiting",
    LedgerEvidenceRecordStatus.CONFIRMED: "tui.ledger.evidence.record_status.confirmed",
    LedgerEvidenceRecordStatus.DECLINED: "tui.ledger.evidence.record_status.declined",
    LedgerEvidenceRecordStatus.UNMEASURED: "tui.ledger.evidence.record_status.unmeasured",
}
_KIND_LOCALE_KEYS: Final[dict[InvoiceKind, str]] = {
    InvoiceKind.RECEIVED: "tui.ledger.invoice.kind.received",
    InvoiceKind.ISSUED: "tui.ledger.invoice.kind.issued",
}


def draft_lines(draft: LedgerEvidenceDraftV1) -> tuple[str, ...]:
    """Show what the reader found; a field it could not ground reads as unread, not as zero."""
    unread = ledger_copy("tui.ledger.evidence.draft.unread")

    def shown(value: str | None) -> str:
        return unread if value is None else value

    return (
        ledger_copy(
            "tui.ledger.evidence.draft.supplier",
            name=shown(draft.supplier_name),
            nif=shown(draft.supplier_tax_id),
        ),
        ledger_copy(
            "tui.ledger.evidence.draft.identity",
            number=shown(draft.invoice_number),
            date=shown(draft.invoice_date),
        ),
        ledger_copy(
            "tui.ledger.evidence.draft.amounts",
            base=shown(draft.taxable_base),
            rate=shown(draft.iva_rate),
            iva=shown(draft.iva_amount),
            total=shown(draft.grand_total),
            currency=shown(draft.currency),
        ),
        ledger_copy("tui.ledger.evidence.draft.discrepancies", count=draft.discrepancies),
    )


class LedgerEvidenceScreen(LedgerWorkspaceScreen):
    """Render safe evidence metadata without document contents or source locators."""

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain an injected canonical review queue."""
        super().__init__(controller, id="ledger-evidence-screen")
        self.selected_evidence_id: str | None = None
        self.selected_record_id: str | None = None
        self.requested_review: LedgerEvidenceReviewRequested | None = None
        self._records: tuple[LedgerEvidenceRecordRowV1, ...] | None = None
        self.draft: LedgerEvidenceDraftV1 | None = None
        self.reading = False
        """Whether a read or a confirmation is out; a second press waits for it."""

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
                yield Static("", id="ledger-evidence-draft", markup=False)
                yield Static(ledger_copy("tui.ledger.invoice.field.kind"), markup=False)
                yield Select[str](
                    tuple((ledger_copy(_KIND_LOCALE_KEYS[kind]), kind.value) for kind in InvoiceKind),
                    value=InvoiceKind.RECEIVED.value,
                    allow_blank=False,
                    id="ledger-evidence-kind",
                )
                yield Static(ledger_copy("tui.ledger.invoice.field.country_code"), markup=False)
                yield Input(value="ES", max_length=2, id="ledger-evidence-country")
                yield Static(
                    ledger_copy(
                        "tui.ledger.invoice.optional", label=ledger_copy("tui.ledger.invoice.field.counterparty_name")
                    ),
                    markup=False,
                )
                yield Input(id="ledger-evidence-counterparty")
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
            self.run_worker(self._measure_reader(), group="ledger-evidence-reader")
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

    async def _read_readiness(self) -> LedgerReaderReadinessV1 | None:
        """Ask the reader off the event loop: the probe looks for executables and calls the runtime."""
        return await asyncio.to_thread(self.controller.reader_readiness)

    async def _measure_reader(self) -> None:
        self._show_reader(await self._read_readiness())

    def _show_reader(self, readiness: LedgerReaderReadinessV1 | None) -> None:
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
        """Add, read or confirm a document; reading waits on the reader's readiness."""
        match event.button.id:
            case "ledger-evidence-add":
                self._add()
            case "ledger-evidence-extract" if self.selected_record_id is not None:
                self._start(self._extract(self.selected_record_id), "tui.ledger.evidence.reading")
            case "ledger-evidence-confirm" if self.selected_record_id is not None:
                confirmation = self._confirmation(self.selected_record_id)
                if confirmation is not None:
                    self._start(self._confirm(confirmation), "tui.ledger.evidence.confirming")
            case _:
                return

    def _start(self, work: Coroutine[object, object, None], status_key: str) -> None:
        if self.reading:
            work.close()
            return
        self.reading = True
        self.query_one("#ledger-refusal", Static).update("")
        self.query_one("#ledger-flow-status", Static).update(ledger_copy(status_key))
        self.run_worker(self._when_reader_ready(work), group="ledger-evidence-reading")

    async def _when_reader_ready(self, work: Coroutine[object, object, None]) -> None:
        """Run ``work`` only if the reader says it can; otherwise name the failed condition."""
        readiness = await self._read_readiness()
        self._show_reader(readiness)
        if readiness is not None and readiness.extraction_ready:
            await work
            return
        work.close()
        self.reading = False
        self.query_one("#ledger-flow-status", Static).update("")
        self.query_one("#ledger-refusal", Static).update(
            ledger_copy(
                "tui.ledger.evidence.reading_refused.reader",
                condition="-" if readiness is None else readiness.failed_condition_id or "-",
            )
        )

    def _confirmation(self, evidence_id: str) -> LedgerEvidenceConfirmationV1 | None:
        country = self.query_one("#ledger-evidence-country", Input).value.strip().upper()
        if len(country) != 2 or not country.isalpha():
            self.query_one("#ledger-refusal", Static).update(ledger_copy("tui.ledger.import.country_required"))
            return None
        counterparty = self.query_one("#ledger-evidence-counterparty", Input).value.strip()
        return LedgerEvidenceConfirmationV1(
            evidence_id=evidence_id,
            kind=InvoiceKind(str(cast("Select[str]", self.query_one("#ledger-evidence-kind", Select)).value)),
            country_code=country,
            counterparty_name=counterparty or None,
        )

    async def _extract(self, evidence_id: str) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        try:
            draft = await self.controller.extract_evidence(evidence_id)
        except (CadrumoError, ValidationError) as error:
            status.update(ledger_copy("tui.ledger.evidence.read_failed"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        else:
            self.draft = draft
            status.update(ledger_copy("tui.ledger.evidence.read_done"))
            self.query_one("#ledger-evidence-draft", Static).update("\n".join(draft_lines(draft)))
            if draft.suggested_kind is not None:
                self.query_one("#ledger-evidence-kind", Select).value = draft.suggested_kind.value
            counterparty = self.query_one("#ledger-evidence-counterparty", Input)
            if not counterparty.value and draft.supplier_name:
                counterparty.value = draft.supplier_name
        finally:
            self.reading = False

    async def _confirm(self, confirmation: LedgerEvidenceConfirmationV1) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        try:
            confirmed = await self.controller.confirm_evidence(confirmation)
        except (CadrumoError, ValidationError) as error:
            self.reading = False
            status.update(ledger_copy("tui.ledger.evidence.confirm_failed"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            return
        self.reading = False
        lines = [
            ledger_copy(
                "tui.ledger.evidence.confirmed" if confirmed.created else "tui.ledger.evidence.already_confirmed",
                number=confirmed.invoice_number,
                total=format(confirmed.grand_total, "f"),
                currency=confirmed.currency,
            )
        ]
        if confirmed.printed_total_disagrees:
            lines.append(ledger_copy("tui.ledger.evidence.printed_total_disagrees"))
        message = "\n".join(lines)
        status.update(message)
        self.refresh_then(lambda: self._after_reread(message))

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
            self.query_one("#ledger-evidence-path", Input).value = ""
            self._show_records()
            added = ledger_copy("tui.ledger.evidence.added", file=record.file_name)
            self.refresh_then(lambda: self._after_reread(added))
        self.query_one("#ledger-evidence-add", Button).disabled = False

    def _after_reread(self, added: str) -> None:
        """Show the re-read area counts beside the document just added."""
        navigation = cast("DataTable[str]", self.query_one("#ledger-navigation", DataTable))
        navigation.clear(columns=True)
        self.populate_navigation()
        self._show_records()
        status = self.query_one("#ledger-flow-status", Static)
        if not str(status.render()):
            status.update(added)


__all__ = ["LedgerEvidenceScreen"]
