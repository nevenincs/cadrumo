"""Invoice evidence record reads, review actions, and their runtime-backed lifecycle."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Final, cast

from pydantic import ValidationError
from textual.widgets import Button, DataTable, Input, Select, Static

from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....domain.iva.classification import InvoiceKind
from ..account import AccountSessionExpiredError
from .controller import LedgerWorkspaceScreen
from .evidence_draft import draft_lines
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


class LedgerEvidenceRecordActions(LedgerWorkspaceScreen):
    """Own the document-record side of the evidence screen."""

    selected_record_id: str | None
    _reviewed_evidence_id: str | None
    _records: tuple[LedgerEvidenceRecordRowV1, ...] | None
    draft: LedgerEvidenceDraftV1 | None
    reading: bool

    def _show_records(self) -> None:
        """Read the records off the event loop; listing them decrypts the whole evidence catalogue."""
        self.query_one("#ledger-evidence-record-detail", Static).update(tr("tui.ledger.evidence.loading"))
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
                tr(_RECORD_STATUS_LOCALE_KEYS[record.status]),
                key=record.evidence_id,
            )
        if not self._records:
            self.query_one("#ledger-evidence-record-detail", Static).update(tr("tui.ledger.evidence.records_empty"))

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
            line.update(tr("tui.ledger.evidence.reader_ready"))
        else:
            line.update(
                tr(
                    "tui.ledger.evidence.reader_not_ready",
                    condition=readiness.failed_condition_id or "-",
                )
            )

    def _select_record(self, evidence_id: str) -> None:
        record = next(item for item in self._records or () if item.evidence_id == evidence_id)
        if evidence_id != self.selected_record_id:
            self._clear_review()
        self.selected_record_id = evidence_id
        self.query_one("#ledger-evidence-record-detail", Static).update(
            tr(
                "tui.ledger.evidence.record_detail",
                kind=record.media_kind,
                supplier=record.supplier or "-",
                added=record.created_at,
                status=tr(_RECORD_STATUS_LOCALE_KEYS[record.status]),
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
                self._start(self._extract(self.selected_record_id), tr("tui.ledger.evidence.reading"))
            case "ledger-evidence-confirm" if self.selected_record_id is not None:
                if (
                    self._reviewed_evidence_id != self.selected_record_id
                    or self.draft is None
                    or self.draft.evidence_id != self.selected_record_id
                ):
                    return
                confirmation = self._confirmation(self.selected_record_id)
                if confirmation is not None:
                    self._start(self._confirm(confirmation), tr("tui.ledger.evidence.confirming"))
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
            self.query_one("#ledger-refusal", Static).update(tr("tui.ledger.import.country_required"))
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
            status.update(tr("tui.ledger.evidence.read_failed"))
            self._handle_expired_session(error)
        except (CadrumoError, ValidationError) as error:
            status.update(tr("tui.ledger.evidence.read_failed"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        else:
            status.update(tr("tui.ledger.evidence.read_done"))
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
            status.update(tr("tui.ledger.evidence.confirm_failed"))
            self._handle_expired_session(error)
            return
        except (CadrumoError, ValidationError) as error:
            self.reading = False
            status.update(tr("tui.ledger.evidence.confirm_failed"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
            return
        self.reading = False
        lines = [
            tr(
                "tui.ledger.evidence.confirmed" if confirmed.created else "tui.ledger.evidence.already_confirmed",
                number=confirmed.invoice_number,
                total=format(confirmed.grand_total, "f"),
                currency=confirmed.currency,
            )
        ]
        if confirmed.printed_total_disagrees:
            lines.append(tr("tui.ledger.evidence.printed_total_disagrees"))
        message = "\n".join(lines)
        status.update(message)
        self.refresh_then(lambda: self._after_reread(message))

    def _add(self) -> None:
        raw = self.query_one("#ledger-evidence-path", Input).value.strip()
        notice = self.query_one("#ledger-refusal", Static)
        if not raw:
            notice.update(tr("tui.ledger.import.path_required"))
            return
        notice.update("")
        self.query_one("#ledger-evidence-add", Button).disabled = True
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.evidence.adding"))
        self.run_worker(self._submit_add(raw), exclusive=True)

    async def _submit_add(self, source_path: str) -> None:
        status = self.query_one("#ledger-flow-status", Static)
        try:
            record = await self.controller.add_evidence(source_path)
        except AccountSessionExpiredError as error:
            status.update(tr("tui.ledger.evidence.add_failed"))
            self._handle_expired_session(error)
        except (CadrumoError, ValidationError) as error:
            status.update(tr("tui.ledger.evidence.add_failed"))
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        else:
            self.query_one("#ledger-evidence-path", Input).value = ""
            added = tr("tui.ledger.evidence.added", file=record.file_name)
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


__all__ = ["LedgerEvidenceRecordActions"]
