"""Concrete Ledger workspace doors for an installed session: import, invoice entry, evidence.

Each door is a thin binding of one application service to the signed-in
profile. The services own every rule -- dedup, the invoice writer's checks,
evidence custody -- so nothing here decides anything a CLI invocation of the
same service would decide differently.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Final

from ...application.ledger.actions_import import (
    aggregate_ledger_import_results,
    import_ledger_source,
    plan_ledger_import_sources,
)
from ...application.ledger.models import LedgerSourceImportCommand, LedgerSourceImportResult
from ...core.errors.hierarchy import InternalInvariantError
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.transactions.errors import TransactionValidationError
from .ledger.models import (
    LedgerEvidenceConfirmationV1,
    LedgerEvidenceConfirmedV1,
    LedgerEvidenceDraftV1,
    LedgerEvidenceRecordRowV1,
    LedgerEvidenceRecordStatus,
    LedgerImportFileRefusalV1,
    LedgerImportOutcomeV1,
    LedgerImportRequestV1,
    LedgerImportRowRefusalV1,
    LedgerImportSourceKind,
    LedgerInvoiceAddResultV1,
    LedgerInvoiceClassChoice,
    LedgerInvoiceEntryV1,
    LedgerReaderReadinessV1,
)

if TYPE_CHECKING:
    from ...application.invoices.bulk_import import BulkInvoiceImportResult
    from ...application.invoices.catalogue_creation_ports import CatalogueCreationPorts
    from ...application.ledger.evidence import PurchaseInvoiceEvidence, PurchaseInvoiceEvidenceService
    from ...application.ledger.evidence_ports import LedgerEvidencePorts
    from ...application.ledger.invoice_draft_extraction_ports import InvoiceDraftExtractionPorts
    from ...application.ledger.invoice_draft_records import InvoiceDraft
    from ...application.ledger.workspace import LedgerWorkspaceProjectionV1
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.invoices.enums import InvoiceClass
    from ...domain.iva.regime_legend import RegimeLegend
    from .ledger.models import LedgerInvoiceAddDoorV1
    from .ledger.workspace_injection import LedgerWorkspaceRefreshV1

#: The audit label an import written from this surface is recorded under.
LEDGER_IMPORT_SOURCE_COMMAND: Final = "cadrumo-tui ledger import"
_INVOICE_BOOK_SUFFIXES: Final = frozenset({".csv", ".tsv", ".xlsx", ".xlsm"})
_ACTOR: Final = "operator"


def _refused(path: Path, error: Exception) -> LedgerImportFileRefusalV1:
    from ...core.errors.error_codes import resolve_error_message

    return LedgerImportFileRefusalV1(file_name=path.name, reason=resolve_error_message(error))


def _invoice_book_files(path: Path) -> tuple[Path, ...]:
    """A file is itself; a folder is its invoice books in name order.

    A folder holding none yields nothing, which the outcome reports as zero
    files read rather than as a success with rows.
    """
    if not path.is_dir():
        return (path,)
    return tuple(sorted(child for child in path.iterdir() if child.suffix.lower() in _INVOICE_BOOK_SUFFIXES))


@dataclass(frozen=True, slots=True)
class LedgerImportDoor:
    """Preview and apply bank statements and invoice books for one profile."""

    profile_id: str
    operation: PinnedAuthorityOperation

    async def preview(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        """Read without writing, off the event loop: a parser import alone can take a second."""
        return await asyncio.to_thread(self._run, request, dry_run=True)

    async def apply(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        """Write through the same services the CLI import verbs use, off the event loop."""
        return await asyncio.to_thread(self._run, request, dry_run=False)

    def _run(self, request: LedgerImportRequestV1, *, dry_run: bool) -> LedgerImportOutcomeV1:
        if request.source_kind is LedgerImportSourceKind.BANK_STATEMENT:
            return self._bank(request, dry_run=dry_run)
        return self._invoices(request, dry_run=dry_run)

    def _bank(self, request: LedgerImportRequestV1, *, dry_run: bool) -> LedgerImportOutcomeV1:
        from ...application.exchange_rate_provider import exchange_rate_provider
        from ...domain.currency.service import CurrencyNormalizationService
        from ..ledger_action_composition import compose_ledger_action_ports, compose_ledger_import_ports

        paths = plan_ledger_import_sources(request.path)
        import_ports = compose_ledger_import_ports()
        action_ports = compose_ledger_action_ports(bucket_id=self.profile_id, operation=self.operation)
        normalizer = CurrencyNormalizationService(rate_provider=exchange_rate_provider())
        results: list[LedgerSourceImportResult] = []
        refusals: list[tuple[Path, TransactionValidationError]] = []
        for path in paths:
            command = LedgerSourceImportCommand(
                bucket_id=self.profile_id,
                path=path,
                provider=request.provider.value,
                dry_run=dry_run,
                actor=_ACTOR,
                source_command=LEDGER_IMPORT_SOURCE_COMMAND,
            )
            try:
                results.append(
                    import_ledger_source(
                        command,
                        ports=import_ports,
                        transaction_repository=action_ports.transaction_repository,
                        bucket_event_repository=action_ports.bucket_event_repository,
                        currency_normalizer=normalizer,
                    )
                )
            except TransactionValidationError as error:
                refusals.append((path, error))
        if not results:
            # Nothing was read, so there is no total to report; the first
            # file's own refusal is the cause worth showing.
            raise refusals[0][1]
        result = results[0] if len(results) == 1 else aggregate_ledger_import_results(results)
        return LedgerImportOutcomeV1(
            source_kind=request.source_kind,
            dry_run=dry_run,
            files=len(results),
            rows=result.rows,
            imported=result.imported,
            skipped=result.skipped,
            likely_duplicates=result.likely_duplicates,
            diagnostics=tuple(item.message for item in result.diagnostics),
            refused_files=tuple(_refused(path, error) for path, error in refusals),
        )

    def _invoices(self, request: LedgerImportRequestV1, *, dry_run: bool) -> LedgerImportOutcomeV1:
        from ...application.invoices.bulk_import import import_invoices_from_rows, read_bulk_invoice_import_source
        from ...domain.iva.classification import InvoiceKind

        kind = (
            InvoiceKind.RECEIVED
            if request.source_kind is LedgerImportSourceKind.INVOICES_RECEIVED
            else InvoiceKind.ISSUED
        )
        files = 0
        rows = 0
        created = 0
        duplicates = 0
        refused_rows: list[LedgerImportRowRefusalV1] = []
        refused_files: list[LedgerImportFileRefusalV1] = []
        unmapped: list[str] = []
        first_error: InvoiceValidationError | None = None
        for path in _invoice_book_files(request.path):
            try:
                # No column mapper: a header the importer does not know is
                # reported as unmapped rather than sent to a language model.
                source = read_bulk_invoice_import_source(path, mapper=None)
                result = (
                    None
                    if dry_run
                    else import_invoices_from_rows(
                        source,
                        bucket_id=self.profile_id,
                        kind=kind,
                        declared_country=request.country,
                        ports=self._catalogue_ports(),
                    )
                )
            except InvoiceValidationError as error:
                first_error = first_error or error
                refused_files.append(_refused(path, error))
                continue
            files += 1
            rows += len(source.rows)
            unmapped.extend(column.header for column in source.resolution.unmapped_columns)
            if result is not None:
                created, duplicates = self._fold(result, created, duplicates, refused_rows)
        if files == 0 and first_error is not None:
            raise first_error
        return LedgerImportOutcomeV1(
            source_kind=request.source_kind,
            dry_run=dry_run,
            files=files,
            rows=rows,
            imported=None if dry_run else created,
            skipped=None if dry_run else duplicates,
            refused_files=tuple(refused_files),
            refused_rows=tuple(refused_rows),
            unmapped_columns=tuple(dict.fromkeys(unmapped)),
        )

    @staticmethod
    def _fold(
        result: BulkInvoiceImportResult,
        created: int,
        duplicates: int,
        refused_rows: list[LedgerImportRowRefusalV1],
    ) -> tuple[int, int]:
        refused_rows.extend(
            LedgerImportRowRefusalV1(row_number=item.row_number, field=item.field, reason=item.reason)
            for item in result.refused
        )
        return created + result.created, duplicates + result.skipped_duplicate

    def _catalogue_ports(self) -> CatalogueCreationPorts:
        from ...adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports

        return build_catalogue_creation_ports(bucket_id=self.profile_id)


def _invoice_class(choice: LedgerInvoiceClassChoice, on: date) -> InvoiceClass:
    from ...domain.invoices.enums import (
        invoice_class_ordinaria,
        invoice_class_rectificativa,
        invoice_class_simplificada,
    )

    resolver = {
        LedgerInvoiceClassChoice.ORDINARIA: invoice_class_ordinaria,
        LedgerInvoiceClassChoice.SIMPLIFICADA: invoice_class_simplificada,
        LedgerInvoiceClassChoice.RECTIFICATIVA: invoice_class_rectificativa,
    }[choice]
    return resolver(effective_date=on)


def ledger_invoice_add_door(profile_id: str, operation: PinnedAuthorityOperation) -> LedgerInvoiceAddDoorV1:
    """Bind the sole catalogue-invoice writer to the signed-in profile."""

    async def add(entry: LedgerInvoiceEntryV1) -> LedgerInvoiceAddResultV1:
        return await asyncio.to_thread(record, entry)

    def record(entry: LedgerInvoiceEntryV1) -> LedgerInvoiceAddResultV1:
        from ...adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
        from ...application.invoices.catalogue_creation import build_catalogue_invoice, create_catalogue_invoice
        from ...domain.calculations.registry.iva_category_catalogue import require_iva_category

        ports = build_catalogue_creation_ports(bucket_id=profile_id)
        invoice = build_catalogue_invoice(
            bucket_id=profile_id,
            kind=entry.kind,
            counterparty_name=entry.counterparty_name,
            counterparty_tax_id=entry.counterparty_nif,
            counterparty_country=entry.country_code,
            invoice_number=entry.invoice_number,
            issued_at=entry.invoice_date,
            taxable_base=entry.taxable_base,
            iva_rate=entry.iva_rate,
            iva_category=(
                require_iva_category(entry.iva_category, effective_date=entry.invoice_date, authority=operation)
                if entry.iva_category is not None
                else None
            ),
            currency=entry.currency,
            notes=entry.notes,
            retention_rate=entry.retention_rate,
            retention_amount=entry.retention_amount,
            invoice_class=_invoice_class(entry.invoice_class, entry.invoice_date),
            series=entry.series,
            rate_provider=ports.rate_provider,
            operation=operation,
        )
        recorded = create_catalogue_invoice(invoice=invoice, ports=ports, actor=_ACTOR).invoice
        return LedgerInvoiceAddResultV1(
            invoice_id=recorded.invoice_id,
            invoice_number=recorded.invoice_number,
            base_total=recorded.base_total,
            iva_total=recorded.iva_total,
            grand_total=recorded.grand_total,
            currency=recorded.currency,
        )

    return add


@dataclass(frozen=True, slots=True)
class LedgerEvidenceDoor:
    """The signed-in profile's purchase-invoice documents and the reader that reads them."""

    profile_id: str
    operation: PinnedAuthorityOperation

    def _service(self) -> PurchaseInvoiceEvidenceService:
        from ...application.ledger.evidence import PurchaseInvoiceEvidenceService
        from ..adapter_composition import build_ledger_evidence_ports

        return PurchaseInvoiceEvidenceService(ports=build_ledger_evidence_ports(bucket_id=self.profile_id))

    def _settled(self) -> tuple[frozenset[str], frozenset[str]] | None:
        """Return confirmed and declined evidence ids, or ``None`` when unreadable."""
        from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
        from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
        from ...application.ledger.confirmation_record import load_confirmation_records
        from ...domain.buckets.event import BucketEventType

        try:
            confirmations = load_confirmation_records(self.profile_id)
        except InternalInvariantError:
            return None
        events = BucketEventHistoryRepository(objects=secure_object_repository_for_bucket(self.profile_id)).load()
        declined = frozenset(
            event.object_id
            for event in events.events.values()
            if event.event_type is BucketEventType.PURCHASE_INVOICE_EVIDENCE_DRAFT_DECLINED
        )
        return frozenset(record.evidence_reference for record in confirmations.records), declined

    @staticmethod
    def _row(
        record: PurchaseInvoiceEvidence, settled: tuple[frozenset[str], frozenset[str]] | None
    ) -> LedgerEvidenceRecordRowV1:
        if settled is None:
            status = LedgerEvidenceRecordStatus.UNMEASURED
        elif record.evidence_id in settled[0]:
            status = LedgerEvidenceRecordStatus.CONFIRMED
        elif record.evidence_id in settled[1]:
            status = LedgerEvidenceRecordStatus.DECLINED
        else:
            status = LedgerEvidenceRecordStatus.AWAITING
        return LedgerEvidenceRecordRowV1(
            evidence_id=record.evidence_id,
            media_kind=record.media_kind.value,
            file_name=Path(record.source_path).name,
            supplier=record.supplier,
            invoice_number=record.invoice_number,
            created_at=record.created_at.date().isoformat(),
            status=status,
        )

    def list_records(self) -> tuple[LedgerEvidenceRecordRowV1, ...]:
        """Read every registered document with its confirmation state."""
        records = self._service().list_all(bucket_id=self.profile_id)
        settled = self._settled() if records else (frozenset(), frozenset())
        return tuple(self._row(record, settled) for record in records)

    def _add(self, source_path: str) -> LedgerEvidenceRecordRowV1:
        result = self._service().add(bucket_id=self.profile_id, source_path=source_path, actor=_ACTOR)
        return self._row(result.record, self._settled())

    async def add(self, source_path: str) -> LedgerEvidenceRecordRowV1:
        """Register one document off the event loop; its bytes go to secure storage, never a path reference."""
        return await asyncio.to_thread(self._add, source_path)

    def _reading(self) -> tuple[LedgerEvidencePorts, InvoiceDraftExtractionPorts, tuple[RegimeLegend, ...]]:
        """Compose what one on-host read needs, exactly as the CLI evidence verbs do."""
        from ...application.ledger.invoice_extraction_authority import default_invoice_extraction_period
        from ...domain.iva.regime_legend import resolve_regime_legends
        from ..adapter_composition import build_ledger_evidence_ports
        from ..ledger_evidence_extraction_composition import invoice_draft_extraction_ports

        evidence_ports = build_ledger_evidence_ports(bucket_id=self.profile_id)
        period = default_invoice_extraction_period()
        legends = resolve_regime_legends(operation=self.operation, effective_date=period.end_date)
        return evidence_ports, invoice_draft_extraction_ports(evidence_ports=evidence_ports), legends

    def _extract(self, evidence_id: str) -> LedgerEvidenceDraftV1:
        from ...application.ledger.invoice_draft_extraction import extract_invoice_draft_from_evidence

        _evidence_ports, extraction_ports, legends = self._reading()
        draft = extract_invoice_draft_from_evidence(
            bucket_id=self.profile_id,
            evidence_id=evidence_id,
            ports=extraction_ports,
            operation=self.operation,
            legends=legends,
        )
        return _draft_row(evidence_id, draft)

    async def extract(self, evidence_id: str) -> LedgerEvidenceDraftV1:
        """Read one stored document on this machine, off the event loop; nothing is recorded."""
        return await asyncio.to_thread(self._extract, evidence_id)

    def _confirm(self, confirmation: LedgerEvidenceConfirmationV1) -> LedgerEvidenceConfirmedV1:
        from ...adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
        from ...adapters.persistence.profile.counterparty_establishment import (
            build_counterparty_establishment_repository,
        )
        from ...adapters.persistence.profile.invoice_confirmation import build_invoice_confirmation_ports
        from ...application.ledger.invoice_confirmation import confirm_invoice_draft_from_evidence

        evidence_ports, extraction_ports, legends = self._reading()
        result = confirm_invoice_draft_from_evidence(
            bucket_id=self.profile_id,
            kind=confirmation.kind,
            counterparty_country=confirmation.country_code,
            evidence_id=confirmation.evidence_id,
            counterparty_name=confirmation.counterparty_name,
            confirmed_by=_ACTOR,
            catalogue_creation_ports=build_catalogue_creation_ports(bucket_id=self.profile_id),
            invoice_confirmation_ports=build_invoice_confirmation_ports(bucket_id=self.profile_id),
            counterparty_establishment_repository=build_counterparty_establishment_repository(
                bucket_id=self.profile_id
            ),
            evidence_ports=evidence_ports,
            extraction_ports=extraction_ports,
            operation=self.operation,
            legends=legends,
        )
        invoice = result.invoice
        return LedgerEvidenceConfirmedV1(
            invoice_id=invoice.invoice_id,
            invoice_number=invoice.invoice_number,
            grand_total=invoice.grand_total,
            currency=invoice.currency,
            created=result.created,
            printed_total_disagrees=result.total_discrepancy is not None,
        )

    async def confirm(self, confirmation: LedgerEvidenceConfirmationV1) -> LedgerEvidenceConfirmedV1:
        """Re-read the document and record it as an invoice, off the event loop."""
        return await asyncio.to_thread(self._confirm, confirmation)

    def reader_readiness(self) -> LedgerReaderReadinessV1:
        """Ask the reader for its one readiness claim; nothing is started or loaded."""
        from ...application.local_reader import EXTRACTION_READER_ROLES, read_local_reader_status

        status = read_local_reader_status(roles=EXTRACTION_READER_ROLES, assess_load=False)
        failed = next((row.failed_condition_id for row in status.roles if row.failed_condition_id), None)
        if failed is None and status.host.precondition_verdict is not None:
            failed = status.host.precondition_verdict.failed_condition_id
        return LedgerReaderReadinessV1(
            extraction_ready=status.extraction_ready,
            failed_condition_id=None if status.extraction_ready else failed,
        )


def _text(value: object) -> str | None:
    return None if value is None else str(value)


def _draft_row(evidence_id: str, draft: InvoiceDraft) -> LedgerEvidenceDraftV1:
    return LedgerEvidenceDraftV1(
        evidence_id=evidence_id,
        supplier_name=draft.supplier_name,
        supplier_tax_id=_text(draft.supplier_tax_id),
        invoice_number=draft.invoice_number,
        invoice_date=_text(draft.invoice_date),
        taxable_base=_text(draft.taxable_base),
        iva_rate=_text(draft.iva_rate),
        iva_amount=_text(draft.iva_amount),
        grand_total=_text(draft.grand_total),
        currency=_text(draft.currency),
        suggested_kind=draft.suggested_kind,
        discrepancies=len(draft.discrepancies),
    )


def ledger_workspace_refresh(
    profile_id: str,
    capture_ledger: Callable[[], LedgerWorkspaceProjectionV1],
) -> Callable[[], LedgerWorkspaceRefreshV1]:
    """Bind a re-read of the Ledger projection and the attachment queue to a fresh capture."""

    def refresh() -> LedgerWorkspaceRefreshV1:
        from ...adapters.persistence.storage.attachment import AttachmentStore
        from ...application.ledger.attachment_review import list_attachment_review_queue
        from .ledger.workspace_injection import LedgerWorkspaceRefreshV1

        return LedgerWorkspaceRefreshV1(
            projection=capture_ledger(),
            evidence_items=list_attachment_review_queue(AttachmentStore(bucket_id=profile_id)),
        )

    return refresh


__all__ = [
    "LEDGER_IMPORT_SOURCE_COMMAND",
    "LedgerEvidenceDoor",
    "LedgerImportDoor",
    "ledger_invoice_add_door",
    "ledger_workspace_refresh",
]
