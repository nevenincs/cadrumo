"""Ledger evidence: the attachment review queue, local invoice documents, and adding one."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Input, Select, Static

from ....application.ledger.invoice_evidence_operation_dtos import (
    FieldProvenanceProjectionV1,
    InvoiceDraftProjectionV1,
)
from ....application.operations.public_scalar import PublicDecimal
from ....core.errors.hierarchy import CadrumoError
from ....domain.iva.classification import InvoiceKind
from ..account import AccountSessionExpiredError
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

    if draft.full_projection is None:
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

    projection = draft.full_projection
    lines = _full_draft_lines(projection, shown=shown)
    return tuple(lines)


def _full_draft_lines(
    projection: InvoiceDraftProjectionV1,
    *,
    shown: Callable[[str | None], str],
) -> list[str]:
    """Render every canonical draft fact with field labels and repeated evidence rows."""
    unread = ledger_copy("tui.ledger.evidence.draft.unread")

    def amount(value: PublicDecimal | None) -> str:
        return unread if value is None else value.decimal

    def invoice_kind(value: InvoiceKind | None) -> str:
        return unread if value is None else ledger_copy(_KIND_LOCALE_KEYS[value])

    supply_nature = unread if projection.proposed_supply_nature is None else projection.proposed_supply_nature.value
    lines = [
        ledger_copy(
            "tui.ledger.evidence.draft.party",
            role=ledger_copy("tui.ledger.evidence.draft.supplier_role"),
            name=shown(projection.supplier_name),
            tax_id=shown(projection.supplier_tax_id),
            postal_code=shown(projection.supplier_postal_code),
            country=shown(projection.supplier_country),
            country_code=shown(projection.supplier_country_code),
            stated_country_code=shown(projection.supplier_stated_country_code),
        ),
        ledger_copy(
            "tui.ledger.evidence.draft.party",
            role=ledger_copy("tui.ledger.evidence.draft.customer_role"),
            name=shown(projection.customer_name),
            tax_id=shown(projection.customer_tax_id),
            postal_code=shown(projection.customer_postal_code),
            country=shown(projection.customer_country),
            country_code=shown(projection.customer_country_code),
            stated_country_code=shown(projection.customer_stated_country_code),
        ),
        ledger_copy(
            "tui.ledger.evidence.draft.document",
            number=shown(projection.invoice_number),
            series=shown(projection.invoice_series),
            date=shown(projection.invoice_date),
            rectifies=shown(projection.rectifies_invoice_number),
            supply_nature=supply_nature,
            iva_category=shown(projection.iva_category),
            suggested_kind=invoice_kind(projection.suggested_kind),
        ),
        ledger_copy(
            "tui.ledger.evidence.draft.amounts",
            base=amount(projection.taxable_base),
            rate=amount(projection.iva_rate),
            iva=amount(projection.iva_amount),
            total=amount(projection.grand_total),
            currency=shown(projection.currency),
        ),
        ledger_copy("tui.ledger.evidence.draft.regime", value=shown(projection.regime_legend)),
        ledger_copy(
            "tui.ledger.evidence.draft.adjustments",
            recargo=amount(projection.recargo_amount),
            retention_rate=amount(projection.retencion_rate),
            retention=amount(projection.retencion_amount),
            suplidos=amount(projection.suplidos_amount),
        ),
    ]

    lines.append(ledger_copy("tui.ledger.evidence.draft.lines_heading"))
    if not projection.lines:
        lines.append(ledger_copy("tui.ledger.evidence.draft.lines_empty"))
    for index, row in enumerate(projection.lines, start=1):
        lines.append(
            ledger_copy(
                "tui.ledger.evidence.draft.line",
                index=index,
                description=shown(row.description),
                quantity=amount(row.quantity),
                unit_price=amount(row.unit_price),
                base=amount(row.taxable_base),
                rate=amount(row.iva_rate),
                iva=amount(row.iva_amount),
                recargo_rate=amount(row.recargo_rate),
                recargo=amount(row.recargo_amount),
            )
        )

    lines.append(ledger_copy("tui.ledger.evidence.draft.breakdown_heading"))
    if not projection.iva_breakdown:
        lines.append(ledger_copy("tui.ledger.evidence.draft.breakdown_empty"))
    for index, row in enumerate(projection.iva_breakdown, start=1):
        lines.append(
            ledger_copy(
                "tui.ledger.evidence.draft.breakdown",
                index=index,
                rate=amount(row.iva_rate),
                base=amount(row.taxable_base),
                iva=amount(row.iva_amount),
                recargo_rate=amount(row.recargo_rate),
                recargo=amount(row.recargo_amount),
            )
        )

    lines.append(ledger_copy("tui.ledger.evidence.draft.findings_heading"))
    if not projection.discrepancies:
        lines.append(ledger_copy("tui.ledger.evidence.draft.findings_empty"))
    for row in projection.discrepancies:
        lines.append(
            ledger_copy(
                "tui.ledger.evidence.draft.finding",
                kind=row.kind.value,
                field=shown(row.field),
                detail=shown(row.detail),
                expected=amount(row.expected),
                observed=amount(row.observed),
            )
        )

    lines.append(ledger_copy("tui.ledger.evidence.draft.provenance_heading"))
    if not projection.provenance:
        lines.append(ledger_copy("tui.ledger.evidence.draft.provenance_empty"))
    for row in projection.provenance:
        lines.extend(_provenance_lines(row, unread=unread, shown=shown))

    structured_class = projection.facturae_invoice_class
    lines.append(
        ledger_copy(
            "tui.ledger.evidence.draft.structured_class",
            source_code=unread if structured_class is None else structured_class.source_code,
            kind=unread if structured_class is None else structured_class.kind.value,
        )
    )
    lines.append(
        ledger_copy(
            "tui.ledger.evidence.draft.source_metadata",
            transcription_sha256=shown(projection.transcription_sha256),
            raw_text_length=projection.raw_text_length,
        )
    )
    return lines


def _provenance_lines(
    row: FieldProvenanceProjectionV1,
    *,
    unread: str,
    shown: Callable[[str | None], str],
) -> tuple[str, ...]:
    """Preserve every provenance axis and each ambiguity candidate in the review."""
    values = [
        ledger_copy(
            "tui.ledger.evidence.draft.provenance",
            field=row.field,
            origin=row.origin.value,
            grounding=row.grounding.value,
            anchor=shown(row.anchor),
            refused_anchor=shown(row.refused_anchor),
            self_reported=ledger_copy(
                "tui.ledger.evidence.draft.yes" if row.anchor_self_reported else "tui.ledger.evidence.draft.no"
            ),
            derived_from=", ".join(row.derived_from) if row.derived_from else unread,
            role_evidence=shown(row.role_evidence),
            unverified=ledger_copy(
                "tui.ledger.evidence.draft.yes" if row.attribution_unverified else "tui.ledger.evidence.draft.no"
            ),
            note=row.note or unread,
        )
    ]
    values.extend(
        ledger_copy(
            "tui.ledger.evidence.draft.candidate",
            field=row.field,
            value=candidate.value,
            anchor=shown(candidate.anchor),
            note=candidate.note or unread,
        )
        for candidate in row.candidates
    )
    return tuple(values)


class LedgerEvidenceScreen(LedgerWorkspaceScreen):
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
        yield Static(ledger_copy("tui.ledger.evidence.title"), classes="cadrumo-banner")
        with ContentScroll(id="ledger-page", classes="cadrumo-scroll ledger-page"):
            yield ContentDataTable[str](id="ledger-navigation", cursor_type="row", zebra_stripes=True)
            yield Static(ledger_copy("tui.ledger.evidence.safe_metadata"), markup=False)
            if self._has_attachment_review_queue:
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
        if self._has_attachment_review_queue:
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

    def _show_records(self) -> None:
        """Read the records off the event loop; listing them decrypts the whole evidence catalogue."""
        self.query_one("#ledger-evidence-record-detail", Static).update(ledger_copy("tui.ledger.evidence.loading"))
        self.run_worker(self._load_records(), group="ledger-evidence-records", exclusive=True)

    async def _load_records(self) -> None:
        try:
            loaded = await asyncio.to_thread(self.controller.evidence_records)
        except AccountSessionExpiredError as error:
            self._handle_expired_session(error)
        else:
            self._render_records(loaded)

    def _render_records(self, loaded: tuple[LedgerEvidenceRecordRowV1, ...] | None) -> None:
        records = cast("DataTable[str]", self.query_one("#ledger-evidence-records", DataTable))
        records.clear()
        self._records = loaded
        self.query_one("#ledger-evidence-record-detail", Static).update("")
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
        try:
            readiness = await self._read_readiness()
        except AccountSessionExpiredError as error:
            self._handle_expired_session(error)
        else:
            self._show_reader(readiness)

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
        if evidence_id != self.selected_record_id:
            self._clear_review()
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
        self.query_one("#ledger-evidence-confirm", Button).disabled = self._reviewed_evidence_id != evidence_id

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Add, read or confirm a document through its registered operation door."""
        match event.button.id:
            case "ledger-evidence-add":
                self._add()
            case "ledger-evidence-extract" if self.selected_record_id is not None:
                self._start(self._extract(self.selected_record_id), ledger_copy("tui.ledger.evidence.reading"))
            case "ledger-evidence-confirm" if self.selected_record_id is not None:
                if (
                    self._reviewed_evidence_id != self.selected_record_id
                    or self.draft is None
                    or self.draft.evidence_id != self.selected_record_id
                ):
                    return
                confirmation = self._confirmation(self.selected_record_id)
                if confirmation is not None:
                    self._start(self._confirm(confirmation), ledger_copy("tui.ledger.evidence.confirming"))
            case _:
                return

    def _start(self, work: Coroutine[object, object, None], status_text: str) -> None:
        if self.reading:
            work.close()
            return
        self.reading = True
        self.query_one("#ledger-refusal", Static).update("")
        self.query_one("#ledger-flow-status", Static).update(status_text)
        self.run_worker(work, group="ledger-evidence-reading")

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

    def _clear_review(self) -> None:
        """Forget the ephemeral draft and remove its confirmation eligibility."""
        self._reviewed_evidence_id = None
        self.draft = None
        self.query_one("#ledger-evidence-draft", Static).update("")
        self.query_one("#ledger-evidence-confirm", Button).disabled = True

    def _handle_expired_session(self, error: AccountSessionExpiredError) -> None:
        """Clear locally retained review and record rows when the bound session expires."""
        self._clear_review()
        self._records = None
        self.selected_record_id = None
        self.query_one("#ledger-evidence-records", DataTable).clear()
        self.query_one("#ledger-evidence-record-detail", Static).update("")
        self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))

    async def _extract(self, evidence_id: str) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        self._clear_review()
        try:
            draft = await self.controller.extract_evidence(evidence_id)
        except AccountSessionExpiredError as error:
            status.update(ledger_copy("tui.ledger.evidence.read_failed"))
            self._handle_expired_session(error)
        except (CadrumoError, ValidationError) as error:
            status.update(ledger_copy("tui.ledger.evidence.read_failed"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        else:
            status.update(ledger_copy("tui.ledger.evidence.read_done"))
            if self.selected_record_id == evidence_id and draft.evidence_id == evidence_id:
                self.draft = draft
                self._reviewed_evidence_id = evidence_id
                self.query_one("#ledger-evidence-draft", Static).update("\n".join(draft_lines(draft)))
                self.query_one("#ledger-evidence-confirm", Button).disabled = False
                if draft.suggested_kind is not None:
                    self.query_one("#ledger-evidence-kind", Select).value = draft.suggested_kind.value
                counterparty = self.query_one("#ledger-evidence-counterparty", Input)
                if not counterparty.value and draft.supplier_name:
                    counterparty.value = draft.supplier_name
        finally:
            self.reading = False

    async def _confirm(self, confirmation: LedgerEvidenceConfirmationV1) -> None:
        if (
            self._reviewed_evidence_id != confirmation.evidence_id
            or self.draft is None
            or self.draft.evidence_id != confirmation.evidence_id
        ):
            return
        self._clear_review()
        status = self.query_one("#ledger-flow-status", Static)
        try:
            confirmed = await self.controller.confirm_evidence(confirmation)
        except AccountSessionExpiredError as error:
            self.reading = False
            status.update(ledger_copy("tui.ledger.evidence.confirm_failed"))
            self._handle_expired_session(error)
            return
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
        except AccountSessionExpiredError as error:
            status.update(ledger_copy("tui.ledger.evidence.add_failed"))
            self._handle_expired_session(error)
        except (CadrumoError, ValidationError) as error:
            status.update(ledger_copy("tui.ledger.evidence.add_failed"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        else:
            self.query_one("#ledger-evidence-path", Input).value = ""
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
