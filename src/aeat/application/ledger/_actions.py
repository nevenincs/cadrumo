"""Application services for bucket-scoped manual ledger transactions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from ...adapters.inbound.financial.providers import (
    CsvProvider,
    FinancialProvider,
    FinancialProviderError,
    OfxProvider,
    PdfN26Provider,
    ProviderValidation,
    XlsxProvider,
    detect_provider,
)
from ...adapters.inbound.pdf._utils import sha256_file
from ...adapters.persistence.storage.attachment import AttachmentStore
from ...domain.attachments import AttachmentNotFoundError, AttachmentValidationError
from ...domain.attachments._repository import AttachmentStoreProtocol as _AttachmentStoreProtocol
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
)
from ...domain.invoices import InvoiceCatalogue, InvoiceCatalogueRepository, InvoiceKind
from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ...domain.modelos._calculation_revision import CalculationRevisionState
from ...domain.modelos._repository import WorkUnitCatalogueRepository
from ...domain.transactions import (
    TX_BUCKET_NAMESPACE,
    BucketTransactionRef,
    BusinessClassification,
    ImportSummary,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    SplitLineage,
    SplitRole,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionEditLineageEntry,
    TransactionEvidenceProvenanceEntry,
    TransactionLifecycleLineageEntry,
    TransactionLifecycleState,
    TransactionNotFoundError,
    TransactionValidationError,
    derive_split_group_id,
    derive_transaction_id,
)
from ...domain.usage_ratios import (
    UsageRatioProfile,
    UsageRatioValidationError,
    load_usage_ratios,
    validate_usage_ratio_reference,
)
from ..aggregation import Period
from ..export import serialize_tabular_rows
from ..transactions import LedgerImportDiagnostic, import_ledger_with_diagnostics
from ._models import (
    LedgerCatalogueResetReport,
    LedgerExportCommand,
    LedgerExportResult,
    LedgerExportRow,
    LedgerImportDiagnosticReport,
    LedgerImportOperationResult,
    LedgerRemovalBlocker,
    LedgerReviewQuery,
    LedgerReviewQueryResult,
    LedgerReviewRow,
    LedgerSourceImportCommand,
    LedgerSourceImportResult,
    LedgerSourceValidationReport,
    LedgerSourceVerificationReport,
    LedgerStatusReport,
    LedgerTransactionRemovalReport,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
    MergeTransactionsResult,
    SplitChildCommand,
    SplitTransactionResult,
)
from ._preflight import preflight_ledger_tax_readiness

_BUCKET_EVENT_PAYLOAD_VERSION = 1
_MANUAL_PROVIDER_NAME = "manual-ledger"
DirectionResolver = Callable[[RawTransaction], TransactionDirection]
_EventSpec = tuple[BucketEventType, BucketEventObjectType, str, dict[str, str]]
_LEDGER_EXPORT_FIELDNAMES = (
    "bucket_id",
    "transaction_id",
    "lifecycle_state",
    "booked_date",
    "value_date",
    "effective_date",
    "amount",
    "currency",
    "direction",
    "counterparty",
    "description",
    "business_classification",
    "business_pct",
    "category_id",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "irpf_category",
    "usage_ratio_id",
    "prorrata_reference",
    "purchase_invoice_evidence_id",
    "attachment_ids",
    "notes",
    "created_by",
    "created_source_command",
)
_REMOVAL_BLOCKING_REVISION_STATES = frozenset(
    {
        CalculationRevisionState.VERIFIED_COMPLETE,
        CalculationRevisionState.FILED,
        CalculationRevisionState.FILED_SUPERSEDED,
    }
)


def create_manual_transaction(
    command: ManualLedgerTransactionCommand,
    *,
    transaction_repository: TransactionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    invoice_repository: InvoiceCatalogueRepository | None = None,
    attachment_store: _AttachmentStoreProtocol | None = None,
    usage_ratio_profile: UsageRatioProfile | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Persist one manual ledger transaction in the command's bucket."""

    now = _normalise_timestamp(occurred_at)
    repository = _transaction_repository(bucket_id=command.bucket_id, repository=transaction_repository)
    event_repository = bucket_event_repository or BucketEventHistoryRepository()
    transaction_base = _transaction_from_command(command, occurred_at=now)
    _verify_evidence_references(
        command,
        transaction_id=transaction_base.transaction_id,
        invoice_repository=invoice_repository,
        attachment_store=attachment_store,
    )
    _verify_usage_ratio_reference(command, usage_ratio_profile=usage_ratio_profile)
    event = _build_bucket_event(
        bucket_id=command.bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_CREATED,
        occurred_at=now,
        actor=command.actor,
        object_id=transaction_base.transaction_id,
        payload=_event_payload(command),
    )
    transaction = _transaction_from_command(command, occurred_at=now, bucket_event_id=event.event_id)
    catalogue = repository.load()
    _save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=_upsert_transaction(catalogue, transaction),
        events=(event,),
    )
    return _result(command.bucket_id, transaction, (event.event_id,))


def attach_manual_transaction_evidence(
    *,
    bucket_id: str,
    transaction_id: str,
    actor: str,
    purchase_invoice_evidence_id: str | None = None,
    attachment_ids: tuple[str, ...] = (),
    source_command: str = "aeat app ledger attach",
    transaction_repository: TransactionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    invoice_repository: InvoiceCatalogueRepository | None = None,
    attachment_store: _AttachmentStoreProtocol | None = None,
    usage_ratio_profile: UsageRatioProfile | None = None,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Attach purchase evidence or supplementary attachments to one ledger transaction."""

    trimmed_actor = _require_actor(actor, operation="ledger evidence attachment")
    trimmed_source_command = _require_source_command(source_command, operation="ledger evidence attachment")
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    current = _require_transaction(repository.load(), transaction_id)
    normalized_purchase_evidence_id = purchase_invoice_evidence_id.strip() if purchase_invoice_evidence_id else None
    normalized_attachment_ids = _normalise_attachment_patch_ids(attachment_ids)
    if normalized_purchase_evidence_id is None and not normalized_attachment_ids:
        raise TransactionValidationError("ledger evidence attachment requires purchase evidence or attachment ids")
    if (
        normalized_purchase_evidence_id is not None
        and current.purchase_invoice_evidence_id is not None
        and current.purchase_invoice_evidence_id != normalized_purchase_evidence_id
    ):
        raise TransactionValidationError(
            "ledger transaction already has purchase_invoice_evidence_id; "
            "remove or replace through attachments workflow"
        )
    patch_values: dict[str, object] = {}
    if normalized_purchase_evidence_id is not None:
        patch_values["purchase_invoice_evidence_id"] = normalized_purchase_evidence_id
    if normalized_attachment_ids:
        patch_values["attachment_ids"] = _merge_identifier_tuple(current.attachment_ids, normalized_attachment_ids)
    return update_manual_transaction_fields(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        patch=ManualLedgerTransactionPatch.model_validate(patch_values),
        actor=trimmed_actor,
        source_command=trimmed_source_command,
        transaction_repository=repository,
        bucket_event_repository=bucket_event_repository,
        invoice_repository=invoice_repository,
        attachment_store=attachment_store,
        usage_ratio_profile=usage_ratio_profile,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        occurred_at=occurred_at,
    )


def import_ledger_transactions(
    *,
    bucket_id: str,
    raw_transactions: Iterable[RawTransaction],
    direction_resolver: Callable[[RawTransaction], object],
    transaction_repository: TransactionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    actor: str = "operator",
    source_command: str = "aeat app ledger import",
    occurred_at: datetime | None = None,
) -> LedgerImportOperationResult:
    """Import provider transactions into one bucket catalogue and emit events."""

    now = _normalise_timestamp(occurred_at)
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = bucket_event_repository or BucketEventHistoryRepository()
    catalogue = repository.load()
    raw_rows = tuple(raw_transactions)
    existing_ids = set(catalogue.transactions.keys())
    imported_refs: list[BucketTransactionRef] = []
    skipped_refs: list[BucketTransactionRef] = []
    imported_transactions: list[Transaction] = []
    updated_transactions = dict(catalogue.transactions)
    import_batch_id = _import_batch_id(
        bucket_id=bucket_id,
        source_command=source_command,
        imported_transaction_ids=tuple(derive_transaction_id(raw) for raw in raw_rows),
    )
    for raw in raw_rows:
        tx_id = derive_transaction_id(raw)
        ref = BucketTransactionRef(bucket_id=bucket_id, transaction_id=tx_id)
        if tx_id in existing_ids:
            skipped_refs.append(ref)
            continue
        transaction = Transaction.model_validate({"raw": raw, "direction": direction_resolver(raw)})
        updated_transactions[transaction.transaction_id] = transaction
        existing_ids.add(transaction.transaction_id)
        imported_refs.append(ref)
        imported_transactions.append(transaction)
    summary = ImportSummary(
        imported=len(imported_refs),
        skipped=len(skipped_refs),
        bucket_id=bucket_id,
        imported_refs=tuple(imported_refs),
        skipped_refs=tuple(skipped_refs),
        catalogue_path=f"db://secure_objects/{TX_BUCKET_NAMESPACE}/transaction-catalogue:{bucket_id}",
    )
    if not imported_transactions:
        return LedgerImportOperationResult(summary=summary, import_batch_id=import_batch_id)
    events = tuple(
        _build_bucket_event(
            bucket_id=bucket_id,
            event_type=BucketEventType.LEDGER_TRANSACTION_IMPORTED,
            occurred_at=now,
            actor=actor,
            object_type=BucketEventObjectType.LEDGER_TRANSACTION,
            object_id=transaction.transaction_id,
            payload={
                "source_command": source_command,
                "import_batch_id": import_batch_id,
                "provider_name": transaction.raw.provenance.provider_name,
                "source_format": transaction.raw.provenance.source_format.value,
                "source_row_index": str(transaction.raw.provenance.source_row_index),
                "imported_count": str(len(imported_transactions)),
                "skipped_count": str(len(skipped_refs)),
            },
        )
        for transaction in imported_transactions
    )
    _save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=TransactionCatalogue.model_validate({"transactions": updated_transactions}),
        events=events,
    )
    return LedgerImportOperationResult(
        summary=summary,
        import_batch_id=import_batch_id,
        bucket_event_ids=tuple(event.event_id for event in events),
    )


def import_ledger_source(
    command: LedgerSourceImportCommand,
    *,
    transaction_repository: TransactionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
) -> LedgerSourceImportResult:
    """Validate, ingest, and optionally persist one ledger source file."""

    provider = _resolve_financial_provider(command.provider, command.path)
    validation = _validate_import_source(provider, command.path)
    source_verification = _build_source_verification(source=command.source, verify=command.verify)
    try:
        raw_transactions = tuple(provider.ingest(command.path))
    except FinancialProviderError as exc:
        raise TransactionValidationError(f"The ledger file cannot be imported: {exc}") from exc
    repository = (
        _transaction_repository(bucket_id=command.bucket_id, repository=transaction_repository)
        if command.bucket_id is not None
        else transaction_repository
    )
    existing_catalogue = repository.load() if repository is not None else TransactionCatalogue()
    diagnostic_result = (
        import_ledger_with_diagnostics(
            command.path,
            raw_transactions,
            existing_catalogue,
            original_source_path=command.source,
        )
        if command.verify
        else None
    )
    diagnostics = (
        tuple(_diagnostic_report(diagnostic) for diagnostic in diagnostic_result.diagnostics)
        if diagnostic_result is not None
        else ()
    )
    if command.dry_run:
        return LedgerSourceImportResult(
            rows=len(raw_transactions),
            imported=0,
            skipped=0,
            dry_run=True,
            verify=command.verify,
            period=command.period,
            validation=_validation_report(validation),
            source=source_verification,
            diagnostics=diagnostics,
        )
    if command.bucket_id is None:
        raise TransactionValidationError("ledger source import requires a bucket_id unless dry_run is true")
    repository = _transaction_repository(bucket_id=command.bucket_id, repository=repository)
    event_repository = bucket_event_repository or BucketEventHistoryRepository()
    result = import_ledger_transactions(
        bucket_id=command.bucket_id,
        raw_transactions=raw_transactions,
        direction_resolver=_direction_from_amount,
        transaction_repository=repository,
        bucket_event_repository=event_repository,
        actor=command.actor,
        source_command=command.source_command,
    )
    summary = result.summary
    diagnostic_events = _diagnostic_events(
        bucket_id=command.bucket_id,
        import_batch_id=result.import_batch_id,
        diagnostics=diagnostic_result.diagnostics if diagnostic_result is not None else (),
        transaction_ids=tuple(derive_transaction_id(raw) for raw in raw_transactions),
        actor=command.actor,
        source_command=command.source_command,
    )
    if diagnostic_events:
        _append_bucket_events(repository=event_repository, events=diagnostic_events)
    return LedgerSourceImportResult(
        rows=len(raw_transactions),
        imported=summary.imported,
        skipped=summary.skipped,
        dry_run=False,
        verify=command.verify,
        period=command.period,
        bucket_id=summary.bucket_id,
        import_batch_id=result.import_batch_id,
        bucket_event_ids=result.bucket_event_ids + tuple(event.event_id for event in diagnostic_events),
        imported_transaction_refs=summary.imported_refs,
        skipped_transaction_refs=summary.skipped_refs,
        validation=_validation_report(validation),
        source=source_verification,
        diagnostics=diagnostics,
    )


def archive_manual_transaction(
    *,
    bucket_id: str,
    transaction_id: str,
    actor: str,
    reason: str = "",
    source_command: str = "aeat app ledger archive",
    transaction_repository: TransactionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Mark one bucket-scoped ledger transaction as archived."""

    return _transition_manual_transaction_lifecycle(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        state=TransactionLifecycleState.ARCHIVED,
        event_type=BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
        actor=actor,
        reason=reason,
        source_command=source_command,
        transaction_repository=transaction_repository,
        bucket_event_repository=bucket_event_repository,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        occurred_at=occurred_at,
    )


def stash_manual_transaction(
    *,
    bucket_id: str,
    transaction_id: str,
    actor: str,
    reason: str = "",
    source_command: str = "aeat app ledger stash",
    transaction_repository: TransactionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Mark one active bucket-scoped ledger transaction as stashed."""

    return _transition_manual_transaction_lifecycle(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        state=TransactionLifecycleState.STASHED,
        event_type=BucketEventType.LEDGER_TRANSACTION_STASHED,
        actor=actor,
        reason=reason,
        source_command=source_command,
        transaction_repository=transaction_repository,
        bucket_event_repository=bucket_event_repository,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        occurred_at=occurred_at,
    )


def remove_manual_transaction(
    *,
    bucket_id: str,
    transaction_id: str,
    actor: str,
    reason: str = "",
    dry_run: bool = False,
    source_command: str = "aeat app ledger remove",
    transaction_repository: TransactionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    invoice_repository: InvoiceCatalogueRepository | None = None,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    occurred_at: datetime | None = None,
) -> LedgerTransactionRemovalReport:
    """Remove one bucket-scoped ledger transaction after finalized-modelo checks."""

    now = _normalise_timestamp(occurred_at)
    trimmed_actor = _require_actor(actor, operation="ledger removal")
    trimmed_source_command = _require_source_command(source_command, operation="ledger removal")
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = bucket_event_repository or BucketEventHistoryRepository()
    invoices = invoice_repository or InvoiceCatalogueRepository()
    catalogue = repository.load()
    current = _require_transaction(catalogue, transaction_id)
    blockers = _blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=_transaction_modelo_source_ids(current),
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    purchase_evidence_ids, updated_invoice_catalogue = _detach_transaction_from_purchase_evidence(
        invoices.load(),
        bucket_id=bucket_id,
        transaction_id=current.transaction_id,
    )
    attachment_ids = tuple(sorted(current.attachment_ids))
    if blockers:
        if not dry_run:
            _raise_finalized_modelo_blocked(
                operation="ledger transaction removal",
                transaction_ids=_transaction_modelo_source_ids(current),
                blockers=blockers,
            )
        return LedgerTransactionRemovalReport(
            bucket_id=bucket_id,
            transaction_id=current.transaction_id,
            dry_run=dry_run,
            actor=trimmed_actor,
            reason=reason.strip(),
            cascaded_purchase_invoice_evidence_ids=purchase_evidence_ids,
            cascaded_attachment_ids=attachment_ids,
            blocking_modelo_references=blockers,
        )
    if dry_run:
        return LedgerTransactionRemovalReport(
            bucket_id=bucket_id,
            transaction_id=current.transaction_id,
            dry_run=True,
            actor=trimmed_actor,
            reason=reason.strip(),
            cascaded_purchase_invoice_evidence_ids=purchase_evidence_ids,
            cascaded_attachment_ids=attachment_ids,
        )

    events = _removal_events(
        bucket_id=bucket_id,
        transaction=current,
        actor=trimmed_actor,
        reason=reason.strip(),
        source_command=trimmed_source_command,
        purchase_evidence_ids=purchase_evidence_ids,
        attachment_ids=attachment_ids,
        occurred_at=now,
    )
    _save_transaction_catalogue_invoices_and_events(
        transaction_repository=repository,
        invoice_repository=invoices,
        event_repository=event_repository,
        transaction_catalogue=_remove_transaction(catalogue, transaction_id=current.transaction_id),
        invoice_catalogue=updated_invoice_catalogue,
        events=events,
    )
    return LedgerTransactionRemovalReport(
        bucket_id=bucket_id,
        transaction_id=current.transaction_id,
        removed=True,
        actor=trimmed_actor,
        reason=reason.strip(),
        cascaded_purchase_invoice_evidence_ids=purchase_evidence_ids,
        cascaded_attachment_ids=attachment_ids,
        bucket_event_ids=tuple(event.event_id for event in events),
    )


def reset_ledger_catalogue(
    *,
    bucket_id: str,
    actor: str,
    reason: str = "",
    dry_run: bool = False,
    source_command: str = "aeat app ledger reset",
    transaction_repository: TransactionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    invoice_repository: InvoiceCatalogueRepository | None = None,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    occurred_at: datetime | None = None,
) -> LedgerCatalogueResetReport:
    """Reset one bucket's ledger catalogue after finalized-modelo checks."""

    now = _normalise_timestamp(occurred_at)
    trimmed_actor = _require_actor(actor, operation="ledger reset")
    trimmed_source_command = _require_source_command(source_command, operation="ledger reset")
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = bucket_event_repository or BucketEventHistoryRepository()
    invoices = invoice_repository or InvoiceCatalogueRepository()
    catalogue = repository.load()
    removed_ids = tuple(sorted(catalogue.transactions))
    guard_ids = _catalogue_modelo_source_ids(catalogue)
    blockers = _blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=guard_ids,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    invoice_catalogue = invoices.load()
    purchase_evidence_ids, updated_invoice_catalogue = _detach_transactions_from_purchase_evidence(
        invoice_catalogue,
        bucket_id=bucket_id,
        transaction_ids=removed_ids,
    )
    attachment_ids = tuple(
        sorted({attachment_id for transaction in catalogue.values() for attachment_id in transaction.attachment_ids})
    )
    if blockers:
        if not dry_run:
            _raise_finalized_modelo_blocked(
                operation="ledger catalogue reset",
                transaction_ids=guard_ids,
                blockers=blockers,
            )
        return LedgerCatalogueResetReport(
            bucket_id=bucket_id,
            removed_transaction_ids=removed_ids,
            dry_run=dry_run,
            actor=trimmed_actor,
            reason=reason.strip(),
            cascaded_purchase_invoice_evidence_ids=purchase_evidence_ids,
            cascaded_attachment_ids=attachment_ids,
            blocking_modelo_references=blockers,
        )
    if dry_run:
        return LedgerCatalogueResetReport(
            bucket_id=bucket_id,
            removed_transaction_ids=removed_ids,
            dry_run=True,
            actor=trimmed_actor,
            reason=reason.strip(),
            cascaded_purchase_invoice_evidence_ids=purchase_evidence_ids,
            cascaded_attachment_ids=attachment_ids,
        )
    removal_events = tuple(
        event
        for transaction in sorted(catalogue.values(), key=lambda item: item.transaction_id)
        for event in _removal_events(
            bucket_id=bucket_id,
            transaction=transaction,
            actor=trimmed_actor,
            reason=reason.strip(),
            source_command=trimmed_source_command,
            purchase_evidence_ids=tuple(
                invoice_id
                for invoice_id, invoice in invoice_catalogue.invoices.items()
                if invoice.bucket_id == bucket_id and transaction.transaction_id in invoice.linked_transaction_ids
            ),
            attachment_ids=tuple(sorted(transaction.attachment_ids)),
            occurred_at=now,
        )
    )
    reset_event = _build_bucket_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_CATALOGUE_RESET,
        occurred_at=now,
        actor=trimmed_actor,
        object_type=BucketEventObjectType.LEDGER_CATALOGUE,
        object_id=transaction_catalogue_object_id(bucket_id),
        payload={
            "source_command": trimmed_source_command,
            "reason": reason.strip(),
            "removed_transaction_count": str(len(removed_ids)),
            "removed_transaction_ids": ",".join(removed_ids),
        },
    )
    _save_transaction_catalogue_invoices_and_events(
        transaction_repository=repository,
        invoice_repository=invoices,
        event_repository=event_repository,
        transaction_catalogue=TransactionCatalogue(),
        invoice_catalogue=updated_invoice_catalogue,
        events=(*removal_events, reset_event),
    )
    return LedgerCatalogueResetReport(
        bucket_id=bucket_id,
        removed_transaction_ids=removed_ids,
        reset=True,
        actor=trimmed_actor,
        reason=reason.strip(),
        cascaded_purchase_invoice_evidence_ids=purchase_evidence_ids,
        cascaded_attachment_ids=attachment_ids,
        bucket_event_ids=tuple(event.event_id for event in (*removal_events, reset_event)),
    )


def export_ledger_transactions(
    command: LedgerExportCommand,
    *,
    transaction_repository: TransactionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    occurred_at: datetime | None = None,
) -> LedgerExportResult:
    """Export canonical bucket-local ledger transaction rows and emit an audit event."""

    now = _normalise_timestamp(occurred_at)
    repository = _transaction_repository(bucket_id=command.bucket_id, repository=transaction_repository)
    event_repository = bucket_event_repository or BucketEventHistoryRepository()
    catalogue = repository.load()
    rows = _ledger_export_rows(catalogue, bucket_id=command.bucket_id, include_inactive=command.include_inactive)
    serialized = serialize_tabular_rows(
        tuple(row.model_dump(mode="json") for row in rows),
        fieldnames=_LEDGER_EXPORT_FIELDNAMES,
        export_format=command.export_format,
    )
    if command.output_path is not None:
        command.output_path.write_bytes(serialized.payload)
    export_id = _ledger_export_id(
        bucket_id=command.bucket_id,
        export_format=command.export_format.value,
        sha256=serialized.sha256,
        transaction_ids=tuple(row.transaction_id for row in rows),
    )
    event = _build_bucket_event(
        bucket_id=command.bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_EXPORTED,
        occurred_at=now,
        actor=command.actor,
        object_type=BucketEventObjectType.LEDGER_EXPORT,
        object_id=export_id,
        payload={
            "source_command": command.source_command,
            "export_format": command.export_format.value,
            "include_inactive": str(command.include_inactive).lower(),
            "row_count": str(serialized.row_count),
            "byte_size": str(serialized.byte_size),
            "sha256": serialized.sha256,
            "output_path": str(command.output_path) if command.output_path is not None else "",
            "transaction_ids_sha256": _transaction_ids_digest(tuple(row.transaction_id for row in rows)),
            "first_transaction_id": rows[0].transaction_id if rows else "",
            "last_transaction_id": rows[-1].transaction_id if rows else "",
        },
    )
    _save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=catalogue,
        events=(event,),
    )
    return LedgerExportResult(
        bucket_id=command.bucket_id,
        export_id=export_id,
        export_format=serialized.format,
        media_type=serialized.media_type,
        filename_extension=serialized.filename_extension,
        row_count=serialized.row_count,
        byte_size=serialized.byte_size,
        sha256=serialized.sha256,
        fieldnames=serialized.fieldnames,
        rows=rows,
        payload=serialized.payload,
        bucket_event_ids=(event.event_id,),
    )


def get_manual_transaction(
    *,
    bucket_id: str,
    transaction_id: str,
    transaction_repository: TransactionCatalogueRepository | None = None,
) -> ManualLedgerTransactionResult:
    """Return one transaction from a bucket-scoped catalogue."""

    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transaction = _require_transaction(repository.load(), transaction_id)
    return _result(bucket_id, transaction, ())


def list_manual_transactions(
    *,
    bucket_id: str,
    transaction_repository: TransactionCatalogueRepository | None = None,
) -> tuple[ManualLedgerTransactionResult, ...]:
    """Return every transaction in a bucket, sorted by effective date and id."""

    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transactions = sorted(
        repository.load().values(),
        key=lambda transaction: (
            transaction.raw.value_date or transaction.raw.booked_date,
            transaction.transaction_id,
        ),
    )
    return tuple(_result(bucket_id, transaction, ()) for transaction in transactions)


def query_ledger_review_rows(
    query: LedgerReviewQuery,
    *,
    transaction_repository: TransactionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
) -> LedgerReviewQueryResult:
    """Return review rows for bucket-local ledger transactions."""

    repository = _transaction_repository(bucket_id=query.bucket_id, repository=transaction_repository)
    rows = tuple(repository.load().values())
    if query.period is not None:
        period = Period.model_validate(query.period)
        rows = tuple(
            transaction
            for transaction in rows
            if period.contains(transaction.raw.value_date or transaction.raw.booked_date)
        )
    if query.status is not None:
        rows = tuple(
            transaction for transaction in rows if ledger_transaction_review_status(transaction) == query.status
        )
    if query.import_id is not None or query.issue is not None:
        matching_ids = _transaction_ids_for_review_event_filters(
            bucket_id=query.bucket_id,
            import_id=query.import_id,
            issue=query.issue,
            bucket_event_repository=bucket_event_repository,
        )
        rows = tuple(transaction for transaction in rows if transaction.transaction_id in matching_ids)
    if query.transaction_id is not None:
        _require_transaction(repository.load(), query.transaction_id)
        rows = tuple(transaction for transaction in rows if transaction.transaction_id == query.transaction_id)
    sorted_rows = sorted(
        rows,
        key=lambda transaction: (
            transaction.raw.value_date or transaction.raw.booked_date,
            transaction.transaction_id,
        ),
    )
    filters: list[str] = []
    if query.period is not None:
        filters.append(f"period={query.period}")
    if query.status is not None:
        filters.append(f"status={query.status}")
    if query.issue is not None:
        filters.append(f"issue={query.issue}")
    if query.import_id is not None:
        filters.append(f"import={query.import_id}")
    if query.transaction_id is not None:
        filters.append(f"id={query.transaction_id}")
    return LedgerReviewQueryResult(
        bucket_id=query.bucket_id,
        rows=tuple(
            _ledger_review_row(transaction, include_transaction=query.transaction_id is not None)
            for transaction in sorted_rows
        ),
        filters=tuple(filters),
    )


def ledger_transaction_review_status(transaction: Transaction) -> str:
    """Return the operator review status for a bucket-local transaction fact."""

    if transaction.business_classification is BusinessClassification.SKIPPED_BY_RULE:
        return "skipped"
    if transaction.business_classification in {
        BusinessClassification.BUSINESS,
        BusinessClassification.PERSONAL,
        BusinessClassification.MIXED,
    }:
        return "reviewed"
    return "pending"


def ledger_transaction_payload(transaction: Transaction) -> dict[str, object]:
    """Return the canonical CLI/API projection for one ledger transaction."""

    raw = transaction.raw
    return {
        "transaction_id": transaction.transaction_id,
        "date": (raw.value_date or raw.booked_date).isoformat(),
        "booked_date": raw.booked_date.isoformat(),
        "value_date": raw.value_date.isoformat() if raw.value_date else None,
        "amount": _display_decimal(raw.amount),
        "currency": raw.currency,
        "direction": transaction.direction.value,
        "counterparty": raw.counterparty,
        "description": raw.description,
        "business_classification": transaction.business_classification.value,
        "business_pct": _display_decimal(transaction.business_pct) if transaction.business_pct is not None else None,
        "category_id": transaction.category_id,
        "taxable_base": _display_decimal(transaction.taxable_base) if transaction.taxable_base is not None else None,
        "iva_rate": _display_decimal(transaction.iva_rate) if transaction.iva_rate is not None else None,
        "iva_amount": _display_decimal(transaction.iva_amount) if transaction.iva_amount is not None else None,
        "irpf_category": transaction.irpf_category,
        "usage_ratio_id": transaction.usage_ratio_id,
        "prorrata_reference": transaction.prorrata_reference,
        "purchase_invoice_evidence_id": transaction.purchase_invoice_evidence_id,
        "attachment_ids": list(transaction.attachment_ids),
        "notes": transaction.notes,
        "lifecycle_state": transaction.lifecycle_state.value,
    }


def ledger_transaction_review_payload(transaction: Transaction) -> dict[str, object]:
    """Return one ledger transaction projection plus derived operator review status."""

    return {
        **ledger_transaction_payload(transaction),
        "review_status": ledger_transaction_review_status(transaction),
    }


def ledger_transaction_result_payload(result: ManualLedgerTransactionResult) -> dict[str, object]:
    """Return the canonical projection for a single ledger mutation/read result."""

    return {
        "bucket_id": result.ref.bucket_id,
        "transaction_id": result.ref.transaction_id,
        "review_status": ledger_transaction_review_status(result.transaction),
        "transaction": ledger_transaction_payload(result.transaction),
    }


def ledger_transaction_tracking_payload(transaction: Transaction) -> dict[str, object]:
    """Return durable event lineage fields for one ledger transaction."""

    return {
        "transaction_id": transaction.transaction_id,
        "created_event_id": transaction.created_event_id,
        "evidence_provenance": [item.model_dump(mode="json") for item in transaction.evidence_provenance],
        "edit_lineage": [item.model_dump(mode="json") for item in transaction.edit_lineage],
        "lifecycle_state": transaction.lifecycle_state.value,
        "lifecycle_lineage": [item.model_dump(mode="json") for item in transaction.lifecycle_lineage],
    }


def _ledger_review_row(transaction: Transaction, *, include_transaction: bool) -> LedgerReviewRow:
    effective_date = (transaction.raw.value_date or transaction.raw.booked_date).isoformat()
    row: dict[str, object] = {
        "id": transaction.transaction_id,
        "date": effective_date,
        "amount": _display_decimal(transaction.raw.amount),
        "description": transaction.raw.description,
        "status": ledger_transaction_review_status(transaction),
    }
    if include_transaction:
        row["transaction"] = ledger_transaction_payload(transaction)
    return LedgerReviewRow.model_validate(row)


def summarize_manual_transactions(
    *,
    bucket_id: str,
    period: str | None = None,
    transaction_repository: TransactionCatalogueRepository | None = None,
) -> LedgerStatusReport:
    """Return a read-only status summary for one bucket's ledger transactions."""

    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transactions = tuple(repository.load().values())
    status_counts = {"pending": 0, "reviewed": 0, "skipped": 0}
    for transaction in transactions:
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        status_counts[ledger_transaction_review_status(transaction)] += 1
    checked = 0
    issue_count = 0
    ready: bool | None = None
    if period is not None:
        preflight = preflight_ledger_tax_readiness(
            bucket_id=bucket_id,
            period=period,
            transaction_repository=repository,
        )
        checked = preflight.checked_transaction_count
        issue_count = len(preflight.issues)
        ready = preflight.ready
    return LedgerStatusReport(
        bucket_id=bucket_id,
        total_count=len(transactions),
        active_count=sum(1 for item in transactions if item.lifecycle_state is TransactionLifecycleState.ACTIVE),
        archived_count=sum(1 for item in transactions if item.lifecycle_state is TransactionLifecycleState.ARCHIVED),
        stashed_count=sum(1 for item in transactions if item.lifecycle_state is TransactionLifecycleState.STASHED),
        split_count=sum(1 for item in transactions if item.lifecycle_state is TransactionLifecycleState.SPLIT),
        pending_review_count=status_counts["pending"],
        reviewed_count=status_counts["reviewed"],
        skipped_count=status_counts["skipped"],
        period=period,
        checked_transaction_count=checked,
        readiness_issue_count=issue_count,
        ready=ready,
    )


def update_manual_transaction(
    *,
    transaction_id: str,
    command: ManualLedgerTransactionCommand,
    transaction_repository: TransactionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    invoice_repository: InvoiceCatalogueRepository | None = None,
    attachment_store: _AttachmentStoreProtocol | None = None,
    usage_ratio_profile: UsageRatioProfile | None = None,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Replace one manual ledger transaction with a validated command payload."""

    now = _normalise_timestamp(occurred_at)
    repository = _transaction_repository(bucket_id=command.bucket_id, repository=transaction_repository)
    event_repository = bucket_event_repository or BucketEventHistoryRepository()
    catalogue = repository.load()
    current = _require_transaction(catalogue, transaction_id)
    if current.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        raise TransactionValidationError(
            "only active ledger transactions can be edited; archived, stashed, and split-parent rows are immutable",
            context={
                "transaction_id": transaction_id,
                "lifecycle_state": current.lifecycle_state.value,
            },
        )
    blockers = _blocking_modelo_references(
        bucket_id=command.bucket_id,
        transaction_ids=_transaction_modelo_source_ids(current),
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    if blockers:
        _raise_finalized_modelo_blocked(
            operation="ledger transaction update",
            transaction_ids=_transaction_modelo_source_ids(current),
            blockers=blockers,
        )
    replacement = _transaction_from_command(
        command,
        occurred_at=now,
        provider_transaction_id=current.raw.transaction_id if command.idempotency_key is None else None,
        created_by=current.created_by,
        created_source_command=current.source_command,
        created_event_id=current.created_event_id,
        existing_evidence_provenance=current.evidence_provenance,
        existing_edit_lineage=current.edit_lineage,
        lifecycle_state=current.lifecycle_state,
        lifecycle_lineage=current.lifecycle_lineage,
    )
    if _mutation_signature(current) == _mutation_signature(replacement):
        raise TransactionValidationError(
            "manual ledger update must change at least one ledger field",
            context={"transaction_id": transaction_id},
        )
    _verify_evidence_references(
        command,
        transaction_id=replacement.transaction_id,
        invoice_repository=invoice_repository,
        attachment_store=attachment_store,
    )
    _verify_usage_ratio_reference(command, usage_ratio_profile=usage_ratio_profile)
    event_specs = _update_event_specs(
        current=current,
        replacement=replacement,
        command=command,
        previous_transaction_id=transaction_id,
    )
    events = tuple(
        _build_bucket_event(
            bucket_id=command.bucket_id,
            event_type=event_type,
            occurred_at=now,
            actor=command.actor,
            object_type=object_type,
            object_id=object_id,
            payload=payload,
        )
        for event_type, object_type, object_id, payload in event_specs
    )
    primary_event_id = _primary_lineage_event_id(events)
    evidence_event_ids = _evidence_event_ids(events)
    replacement = _transaction_from_command(
        command,
        occurred_at=now,
        provider_transaction_id=current.raw.transaction_id if command.idempotency_key is None else None,
        created_by=current.created_by,
        created_source_command=current.source_command,
        created_event_id=current.created_event_id,
        existing_evidence_provenance=current.evidence_provenance,
        existing_edit_lineage=current.edit_lineage,
        lifecycle_state=current.lifecycle_state,
        lifecycle_lineage=current.lifecycle_lineage,
        edit_lineage_entry=TransactionEditLineageEntry(
            previous_transaction_id=transaction_id,
            actor=command.actor,
            source_command=command.source_command,
            edited_at=now,
            bucket_event_id=primary_event_id,
        ),
        bucket_event_id=primary_event_id,
        evidence_event_ids=evidence_event_ids,
    )
    _save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=_replace_transaction(catalogue, old_transaction_id=transaction_id, replacement=replacement),
        events=events,
    )
    return _result(command.bucket_id, replacement, tuple(event.event_id for event in events))


def update_manual_transaction_fields(
    *,
    bucket_id: str,
    transaction_id: str,
    patch: ManualLedgerTransactionPatch,
    actor: str,
    source_command: str,
    transaction_repository: TransactionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    invoice_repository: InvoiceCatalogueRepository | None = None,
    attachment_store: _AttachmentStoreProtocol | None = None,
    usage_ratio_profile: UsageRatioProfile | None = None,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Apply a typed field patch to one active bucket-scoped ledger transaction."""

    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    current = _require_transaction(repository.load(), transaction_id)
    command = _command_from_patch(
        bucket_id=bucket_id,
        current=current,
        patch=patch,
        actor=actor,
        source_command=source_command,
    )
    return update_manual_transaction(
        transaction_id=transaction_id,
        command=command,
        transaction_repository=repository,
        bucket_event_repository=bucket_event_repository,
        invoice_repository=invoice_repository,
        attachment_store=attachment_store,
        usage_ratio_profile=usage_ratio_profile,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        occurred_at=occurred_at,
    )


def split_transaction(
    *,
    bucket_id: str,
    transaction_id: str,
    children: tuple[SplitChildCommand, ...],
    actor: str,
    source_command: str = "aeat app ledger split",
    reason: str = "",
    transaction_repository: TransactionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    occurred_at: datetime | None = None,
) -> SplitTransactionResult:
    """Redistribute one parent transaction into N child transactions.

    Pre-conditions:
    - Parent must be in ACTIVE lifecycle state.
    - Parent must not be referenced by a finalized modelo calculation.
    - At least two children must be supplied.
    - Sum of child amounts equals the parent amount exactly (no rounding).
    - Every child amount carries the same sign as the parent amount.

    Effect:
    - Parent transitions ACTIVE -> SPLIT and gains
      ``split_lineage`` with role=PARENT and the child ids as siblings.
    - Each child is persisted as ACTIVE with
      ``split_lineage`` role=CHILD and (parent + other-child) ids as siblings.
    - Children inherit currency, direction, and (by default)
      counterparty / booked_date / value_date from the parent.
    - Children default to ``BusinessClassification.NOT_YET_PROCESSED``
      to force conscious tax treatment per row; classification, evidence,
      and attachment links are NOT auto-cloned.
    - A single ``LEDGER_TRANSACTION_SPLIT`` event is emitted, anchored on
      the parent transaction id so ``for_object(parent_id)`` returns the
      whole lineage chain in chronological order.
    - Catalogue + event are persisted atomically.
    """

    now = _normalise_timestamp(occurred_at)
    trimmed_actor = _require_actor(actor, operation="ledger split")
    trimmed_source_command = _require_source_command(source_command, operation="ledger split")
    if len(children) < 2:
        raise TransactionValidationError(
            "ledger split requires at least two children",
            context={"bucket_id": bucket_id, "transaction_id": transaction_id, "child_count": len(children)},
        )
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = bucket_event_repository or BucketEventHistoryRepository()
    catalogue = repository.load()
    parent = _require_transaction(catalogue, transaction_id)
    if parent.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        raise TransactionValidationError(
            "only active ledger transactions can be split",
            context={
                "bucket_id": bucket_id,
                "transaction_id": transaction_id,
                "lifecycle_state": parent.lifecycle_state.value,
            },
        )
    blockers = _blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=_transaction_modelo_source_ids(parent),
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    if blockers:
        _raise_finalized_modelo_blocked(
            operation="ledger split",
            transaction_ids=_transaction_modelo_source_ids(parent),
            blockers=blockers,
        )

    parent_amount = parent.raw.amount
    child_sum = sum((child.amount for child in children), start=Decimal("0"))
    if child_sum != parent_amount:
        raise TransactionValidationError(
            "ledger split child amounts must sum to the parent amount exactly",
            context={
                "parent_amount": str(parent_amount),
                "child_sum": str(child_sum),
                "child_amounts": tuple(str(child.amount) for child in children),
            },
        )
    parent_negative = parent_amount < Decimal("0")
    for index, child in enumerate(children):
        if child.amount == Decimal("0"):
            raise TransactionValidationError(
                "ledger split child amount must not be zero",
                context={"child_index": index},
            )
        child_negative = child.amount < Decimal("0")
        if child_negative != parent_negative:
            raise TransactionValidationError(
                "ledger split child amounts must share the parent's sign",
                context={
                    "parent_amount": str(parent_amount),
                    "child_index": index,
                    "child_amount": str(child.amount),
                },
            )

    child_amounts = tuple(child.amount for child in children)
    child_narratives = tuple(child.description for child in children)
    split_group_id = derive_split_group_id(
        parent_transaction_id=parent.transaction_id,
        child_amounts=child_amounts,
        child_narratives=child_narratives,
    )

    child_transactions_initial = tuple(
        _build_split_child_transaction(
            parent=parent,
            child=child,
            index=index,
            occurred_at=now,
            actor=trimmed_actor,
            source_command=trimmed_source_command,
        )
        for index, child in enumerate(children)
    )
    child_ids = tuple(transaction.transaction_id for transaction in child_transactions_initial)
    if len(set(child_ids)) != len(child_ids):
        raise TransactionValidationError(
            "ledger split produced duplicate child transaction ids; "
            "vary amount, description, value_date, or counterparty between siblings",
            context={"child_ids": child_ids},
        )

    parent_lineage = SplitLineage(
        split_group_id=split_group_id,
        role=SplitRole.PARENT,
        sibling_transaction_ids=child_ids,
    )
    parent_transition = TransactionLifecycleLineageEntry(
        previous_state=parent.lifecycle_state,
        state=TransactionLifecycleState.SPLIT,
        actor=trimmed_actor,
        source_command=trimmed_source_command,
        changed_at=now,
        reason=reason.strip() or "split",
    )
    parent_after = parent.model_copy(
        update={
            "lifecycle_state": TransactionLifecycleState.SPLIT,
            "lifecycle_lineage": (*parent.lifecycle_lineage, parent_transition),
            "split_lineage": parent_lineage,
        }
    )

    final_children = tuple(
        transaction.model_copy(
            update={
                "split_lineage": SplitLineage(
                    split_group_id=split_group_id,
                    role=SplitRole.CHILD,
                    sibling_transaction_ids=(
                        parent.transaction_id,
                        *(other for other in child_ids if other != transaction.transaction_id),
                    ),
                ),
            }
        )
        for transaction in child_transactions_initial
    )

    event = _build_bucket_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_SPLIT,
        occurred_at=now,
        actor=trimmed_actor,
        object_id=parent.transaction_id,
        payload={
            "source_command": trimmed_source_command,
            "reason": reason.strip(),
            "split_group_id": split_group_id,
            "parent_transaction_id": parent.transaction_id,
            "child_transaction_ids": ",".join(child_ids),
            "child_count": str(len(child_ids)),
        },
    )

    updated_transactions = dict(catalogue.transactions)
    updated_transactions[parent_after.transaction_id] = parent_after
    for child_transaction in final_children:
        updated_transactions[child_transaction.transaction_id] = child_transaction
    new_catalogue = TransactionCatalogue.model_validate({"transactions": updated_transactions})

    _save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=new_catalogue,
        events=(event,),
    )

    return SplitTransactionResult(
        bucket_id=bucket_id,
        parent_transaction_id=parent.transaction_id,
        split_group_id=split_group_id,
        child_transaction_ids=child_ids,
        parent_transaction=parent_after,
        child_transactions=final_children,
        bucket_event_id=event.event_id,
    )


def _build_split_child_transaction(
    *,
    parent: Transaction,
    child: SplitChildCommand,
    index: int,
    occurred_at: datetime,
    actor: str,
    source_command: str,
) -> Transaction:
    """Build one child Transaction. ``split_lineage`` is filled in by the caller
    once all child ids are known so siblings can reference each other."""
    parent_raw = parent.raw
    provider_transaction_id = f"split:{parent.transaction_id}:{index:04d}"
    raw_child = RawTransaction(
        transaction_id=provider_transaction_id,
        booked_date=child.booked_date or parent_raw.booked_date,
        value_date=child.value_date if child.value_date is not None else parent_raw.value_date,
        amount=child.amount,
        currency=parent_raw.currency,
        counterparty=child.counterparty if child.counterparty is not None else parent_raw.counterparty,
        description=child.description,
        provenance=RawProvenance(
            source_path=Path.cwd() / ".aeat-ledger-split",
            source_sha256=hashlib.sha256(f"split:{parent.transaction_id}:{index}".encode()).hexdigest(),
            source_row_index=index + 1,
            source_format=SourceFormat.MANUAL,
            ingested_at=occurred_at,
            provider_name="ledger-split",
        ),
        raw_fields={"parent_transaction_id": parent.transaction_id, "split_index": str(index)},
    )
    return Transaction.model_validate(
        {
            "raw": raw_child,
            "direction": parent.direction,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "created_by": actor,
            "source_command": source_command,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "notes": "",
        }
    )


def merge_transactions(
    *,
    bucket_id: str,
    child_transaction_ids: tuple[str, ...],
    actor: str,
    source_command: str = "aeat app ledger merge",
    reason: str = "",
    transaction_repository: TransactionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    occurred_at: datetime | None = None,
) -> MergeTransactionsResult:
    """Re-merge a complete cohort of split children into a fresh transaction.

    Pre-conditions:
    - At least two child ids supplied.
    - All children exist in the catalogue.
    - All children share the same ``split_group_id``.
    - All children are currently ACTIVE.
    - The parent recorded in each child's lineage is in SPLIT state.
    - The cohort is complete — the children supplied must equal the
      parent's recorded sibling set (no partial re-merge).
    - Neither the parent nor any child is referenced by a finalized
      modelo calculation.

    Effect:
    - Children transition ACTIVE -> ARCHIVED with a lifecycle lineage
      entry recording the merge.
    - Parent transitions SPLIT -> ARCHIVED with its lifecycle lineage
      extended; the parent's split_lineage role=PARENT is preserved
      for audit so the chain is reconstructable.
    - A fresh transaction is persisted with a content-addressed id
      derived from a synthesized ``merged:{split_group_id}`` provider
      key plus the parent's amount / narrative / value_date, and
      ``split_lineage`` role=MERGED carrying the merged child ids.
    - One ``LEDGER_TRANSACTION_MERGED`` event is emitted, anchored on
      the parent transaction id so ``for_object(parent_id)`` returns
      the entire split + merge chain in chronological order.
    - Catalogue + event are persisted atomically.
    """

    now = _normalise_timestamp(occurred_at)
    trimmed_actor = _require_actor(actor, operation="ledger merge")
    trimmed_source_command = _require_source_command(source_command, operation="ledger merge")
    if len(child_transaction_ids) < 2:
        raise TransactionValidationError(
            "ledger merge requires at least two child transactions",
            context={"bucket_id": bucket_id, "child_count": len(child_transaction_ids)},
        )
    if len(set(child_transaction_ids)) != len(child_transaction_ids):
        raise TransactionValidationError(
            "ledger merge child ids must be unique",
            context={"bucket_id": bucket_id, "child_transaction_ids": tuple(child_transaction_ids)},
        )

    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = bucket_event_repository or BucketEventHistoryRepository()
    catalogue = repository.load()

    children = tuple(_require_transaction(catalogue, child_id) for child_id in child_transaction_ids)
    split_group_id = _resolve_merge_split_group(
        children=children,
        bucket_id=bucket_id,
        child_transaction_ids=child_transaction_ids,
    )
    parent = _resolve_merge_parent(
        catalogue=catalogue,
        bucket_id=bucket_id,
        split_group_id=split_group_id,
        child_transaction_ids=child_transaction_ids,
    )

    # Finalized-modelo blocker — parent + every child.
    transaction_ids_under_check = (parent.transaction_id, *child_transaction_ids)
    blocking_pool: list[str] = []
    for member_id in transaction_ids_under_check:
        member = _require_transaction(catalogue, member_id)
        blocking_pool.extend(_transaction_modelo_source_ids(member))
    blockers = _blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=tuple(blocking_pool),
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    if blockers:
        _raise_finalized_modelo_blocked(
            operation="ledger merge",
            transaction_ids=tuple(blocking_pool),
            blockers=blockers,
        )

    # Build the merged transaction. Its content-addressed id varies from
    # the parent's because the synthesized provider_id is unique.
    sorted_child_ids = tuple(sorted(child_transaction_ids))
    parent_raw = parent.raw
    merged_provider_id = f"merged:{split_group_id}"
    merged_raw = RawTransaction(
        transaction_id=merged_provider_id,
        booked_date=parent_raw.booked_date,
        value_date=parent_raw.value_date,
        amount=parent_raw.amount,
        currency=parent_raw.currency,
        counterparty=parent_raw.counterparty,
        description=parent_raw.description,
        provenance=RawProvenance(
            source_path=Path.cwd() / ".aeat-ledger-merge",
            source_sha256=hashlib.sha256(merged_provider_id.encode("utf-8")).hexdigest(),
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=now,
            provider_name="ledger-merge",
        ),
        raw_fields={
            "parent_transaction_id": parent.transaction_id,
            "split_group_id": split_group_id,
            "merged_child_count": str(len(sorted_child_ids)),
        },
    )
    merged_transaction = Transaction.model_validate(
        {
            "raw": merged_raw,
            "direction": parent.direction,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "created_by": trimmed_actor,
            "source_command": trimmed_source_command,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "split_lineage": SplitLineage(
                split_group_id=split_group_id,
                role=SplitRole.MERGED,
                sibling_transaction_ids=sorted_child_ids,
            ),
            "notes": "",
        }
    )
    if merged_transaction.transaction_id in catalogue.transactions:
        raise TransactionValidationError(
            "ledger merge produced an id that already exists in the catalogue",
            context={"merged_transaction_id": merged_transaction.transaction_id},
        )

    # Archive every child.
    archived_children: list[Transaction] = []
    for child in children:
        transition = TransactionLifecycleLineageEntry(
            previous_state=child.lifecycle_state,
            state=TransactionLifecycleState.ARCHIVED,
            actor=trimmed_actor,
            source_command=trimmed_source_command,
            changed_at=now,
            reason=(reason.strip() or "merge"),
        )
        archived_children.append(
            child.model_copy(
                update={
                    "lifecycle_state": TransactionLifecycleState.ARCHIVED,
                    "lifecycle_lineage": (*child.lifecycle_lineage, transition),
                }
            )
        )

    # Archive the parent (preserves SplitLineage role=PARENT for audit).
    parent_transition = TransactionLifecycleLineageEntry(
        previous_state=parent.lifecycle_state,
        state=TransactionLifecycleState.ARCHIVED,
        actor=trimmed_actor,
        source_command=trimmed_source_command,
        changed_at=now,
        reason=(reason.strip() or "merge"),
    )
    parent_after = parent.model_copy(
        update={
            "lifecycle_state": TransactionLifecycleState.ARCHIVED,
            "lifecycle_lineage": (*parent.lifecycle_lineage, parent_transition),
        }
    )

    event = _build_bucket_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_MERGED,
        occurred_at=now,
        actor=trimmed_actor,
        object_id=parent.transaction_id,
        payload={
            "source_command": trimmed_source_command,
            "reason": reason.strip(),
            "split_group_id": split_group_id,
            "parent_transaction_id": parent.transaction_id,
            "merged_transaction_id": merged_transaction.transaction_id,
            "source_child_ids": ",".join(sorted_child_ids),
            "child_count": str(len(sorted_child_ids)),
        },
    )

    updated_transactions = dict(catalogue.transactions)
    updated_transactions[parent_after.transaction_id] = parent_after
    for archived_child in archived_children:
        updated_transactions[archived_child.transaction_id] = archived_child
    updated_transactions[merged_transaction.transaction_id] = merged_transaction
    new_catalogue = TransactionCatalogue.model_validate({"transactions": updated_transactions})

    _save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=new_catalogue,
        events=(event,),
    )

    return MergeTransactionsResult(
        bucket_id=bucket_id,
        split_group_id=split_group_id,
        parent_transaction_id=parent.transaction_id,
        merged_transaction_id=merged_transaction.transaction_id,
        source_child_ids=sorted_child_ids,
        merged_transaction=merged_transaction,
        parent_transaction=parent_after,
        bucket_event_id=event.event_id,
    )


def _resolve_merge_split_group(
    *,
    children: tuple[Transaction, ...],
    bucket_id: str,
    child_transaction_ids: tuple[str, ...],
) -> str:
    """Validate child shape and return the shared ``split_group_id``.

    Rejects: any child without a split_lineage, any disagreement on
    split_group_id across the cohort, any child not in ACTIVE state,
    and any child not carrying split_lineage role=CHILD.
    """
    split_group_ids = {
        child.split_lineage.split_group_id if child.split_lineage is not None else None for child in children
    }
    if None in split_group_ids or len(split_group_ids) != 1:
        raise TransactionValidationError(
            "ledger merge children must all share one split_group_id",
            context={"bucket_id": bucket_id, "child_transaction_ids": tuple(child_transaction_ids)},
        )
    split_group_id = next(iter(split_group_ids))
    assert split_group_id is not None  # narrowed: None excluded by the guard above
    for child in children:
        _require_child_active_and_role(child)
    return split_group_id


def _require_child_active_and_role(child: Transaction) -> None:
    if child.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        raise TransactionValidationError(
            "ledger merge children must all be active",
            context={
                "child_transaction_id": child.transaction_id,
                "lifecycle_state": child.lifecycle_state.value,
            },
        )
    if child.split_lineage is None or child.split_lineage.role is not SplitRole.CHILD:
        raise TransactionValidationError(
            "ledger merge children must carry split_lineage role=CHILD",
            context={"child_transaction_id": child.transaction_id},
        )


def _resolve_merge_parent(
    *,
    catalogue: TransactionCatalogue,
    bucket_id: str,
    split_group_id: str,
    child_transaction_ids: tuple[str, ...],
) -> Transaction:
    """Find the unique split-parent for ``split_group_id`` and verify the cohort.

    Rejects: zero / multiple parent candidates, parent not in SPLIT
    state, parent not carrying split_lineage role=PARENT, or supplied
    children not matching the parent's recorded sibling set.
    """
    parent_candidates = tuple(
        transaction
        for transaction in catalogue.transactions.values()
        if transaction.split_lineage is not None
        and transaction.split_lineage.role is SplitRole.PARENT
        and transaction.split_lineage.split_group_id == split_group_id
    )
    if len(parent_candidates) != 1:
        raise TransactionValidationError(
            "ledger merge could not resolve a unique parent for the split_group_id",
            context={
                "bucket_id": bucket_id,
                "split_group_id": split_group_id,
                "candidate_count": len(parent_candidates),
            },
        )
    parent = parent_candidates[0]
    if parent.lifecycle_state is not TransactionLifecycleState.SPLIT:
        raise TransactionValidationError(
            "ledger merge parent must be in SPLIT state",
            context={"parent_transaction_id": parent.transaction_id, "lifecycle_state": parent.lifecycle_state.value},
        )
    if parent.split_lineage is None or parent.split_lineage.role is not SplitRole.PARENT:
        raise TransactionValidationError(
            "ledger merge parent must carry split_lineage role=PARENT",
            context={"parent_transaction_id": parent.transaction_id},
        )
    expected_children = set(parent.split_lineage.sibling_transaction_ids)
    if expected_children != set(child_transaction_ids):
        raise TransactionValidationError(
            "ledger merge cohort is incomplete; every child of the split_group must be supplied",
            context={
                "parent_transaction_id": parent.transaction_id,
                "expected_children": tuple(sorted(expected_children)),
                "supplied": tuple(sorted(child_transaction_ids)),
            },
        )
    return parent


def _transaction_repository(
    *,
    bucket_id: str,
    repository: TransactionCatalogueRepository | None,
) -> TransactionCatalogueRepository:
    if repository is None:
        return TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise TransactionValidationError(
            "transaction repository bucket_id does not match the manual ledger command bucket",
            context={"command_bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    return repository


def _direction_from_amount(raw: RawTransaction) -> TransactionDirection:
    return TransactionDirection.OUTGOING if raw.amount < 0 else TransactionDirection.INCOMING


def _resolve_financial_provider(provider: str, path: Path) -> FinancialProvider:
    provider_id = provider.strip().lower()
    if provider_id == "auto":
        detected = detect_provider(path)
        if detected is None:
            raise TransactionValidationError(f"auto-detection of ledger format failed for {path}")
        return detected
    if provider_id == "csv":
        return CsvProvider()
    if provider_id in {"ofx", "qfx"}:
        return OfxProvider()
    if provider_id in {"xlsx", "excel"}:
        return XlsxProvider()
    if provider_id == "n26":
        detected = detect_provider(path)
        if detected is None:
            raise TransactionValidationError(f"auto-detection of N26 format failed for {path}")
        return detected
    if provider_id in {"pdf", "pdf-n26"}:
        return PdfN26Provider()
    raise TransactionValidationError(f"unknown ledger provider: {provider}")


def _validate_import_source(provider: FinancialProvider, path: Path) -> ProviderValidation:
    validation = provider.validate_source(path)
    if not validation.is_valid:
        reason = "; ".join(validation.warnings) or "invalid source"
        raise TransactionValidationError(f"The ledger file cannot be imported: {reason}")
    return validation


def _build_source_verification(*, source: Path | None, verify: bool) -> LedgerSourceVerificationReport:
    if not verify:
        return LedgerSourceVerificationReport(requested=False)
    if source is None:
        return LedgerSourceVerificationReport(requested=True)
    resolved = source.resolve()
    if not resolved.exists() or not resolved.is_file():
        raise TransactionValidationError(f"source file not found: {source}")
    return LedgerSourceVerificationReport(requested=True, path=str(resolved), sha256=sha256_file(resolved))


def _validation_report(validation: ProviderValidation) -> LedgerSourceValidationReport:
    return LedgerSourceValidationReport(
        valid=validation.is_valid,
        warnings=tuple(validation.warnings),
        encoding=validation.detected_encoding,
        dialect=validation.detected_dialect,
    )


def _diagnostic_report(diagnostic: LedgerImportDiagnostic) -> LedgerImportDiagnosticReport:
    return LedgerImportDiagnosticReport(
        kind=diagnostic.kind.value,
        severity=diagnostic.severity.value,
        message=str(diagnostic.message),
        source_path=str(diagnostic.source_path) if diagnostic.source_path is not None else None,
        source_locator=diagnostic.source_locator,
        affected_transaction_ids=diagnostic.affected_transaction_ids,
    )


def _diagnostic_events(
    *,
    bucket_id: str,
    import_batch_id: str | None,
    diagnostics: tuple[LedgerImportDiagnostic, ...],
    transaction_ids: tuple[str, ...],
    actor: str,
    source_command: str,
) -> tuple[BucketEvent, ...]:
    if import_batch_id is None:
        return ()
    now = _normalise_timestamp(None)
    events: list[BucketEvent] = []
    for diagnostic in diagnostics:
        object_ids = diagnostic.affected_transaction_ids or transaction_ids or (import_batch_id,)
        for object_id in object_ids:
            object_type = (
                BucketEventObjectType.LEDGER_TRANSACTION
                if object_id != import_batch_id
                else BucketEventObjectType.LEDGER_IMPORT_BATCH
            )
            events.append(
                _build_bucket_event(
                    bucket_id=bucket_id,
                    event_type=BucketEventType.LEDGER_IMPORT_DIAGNOSTIC_RECORDED,
                    occurred_at=now,
                    actor=actor,
                    object_type=object_type,
                    object_id=object_id,
                    payload={
                        "source_command": source_command,
                        "import_batch_id": import_batch_id,
                        "diagnostic_kind": diagnostic.kind.value,
                        "diagnostic_severity": diagnostic.severity.value,
                        "message": str(diagnostic.message),
                    },
                )
            )
    return tuple(events)


def _transaction_ids_for_review_event_filters(
    *,
    bucket_id: str,
    import_id: str | None,
    issue: str | None,
    bucket_event_repository: BucketEventHistoryRepository | None,
) -> frozenset[str]:
    event_repository = bucket_event_repository or BucketEventHistoryRepository()
    events = event_repository.load().for_bucket(
        bucket_id,
        event_types=(
            BucketEventType.LEDGER_TRANSACTION_IMPORTED,
            BucketEventType.LEDGER_IMPORT_DIAGNOSTIC_RECORDED,
        ),
    )
    matching: set[str] = set()
    for event in events:
        if event.object_type is not BucketEventObjectType.LEDGER_TRANSACTION:
            continue
        if import_id is not None and event.payload.get("import_batch_id") != import_id:
            continue
        if issue is not None and event.payload.get("diagnostic_kind") != issue:
            continue
        matching.add(event.object_id)
    return frozenset(matching)


def _require_actor(value: str, *, operation: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise TransactionValidationError(f"{operation} actor must not be blank")
    return trimmed


def _require_source_command(value: str, *, operation: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise TransactionValidationError(f"{operation} source_command must not be blank")
    return trimmed


def _normalise_attachment_patch_ids(attachment_ids: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(item.strip() for item in attachment_ids if item.strip())
    if len(set(normalized)) != len(normalized):
        raise TransactionValidationError("ledger evidence attachment ids must not contain duplicates")
    return normalized


def _merge_identifier_tuple(existing: tuple[str, ...], incoming: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = list(existing)
    for item in incoming:
        if item not in merged:
            merged.append(item)
    return tuple(merged)


def _required_patched[T](
    patch: ManualLedgerTransactionPatch,
    patch_fields: set[str],
    field: str,
    fallback: T,
) -> T:
    """Return ``patch.<field>`` when in patch_fields and non-null; otherwise the fallback.

    Raises ``TransactionValidationError`` when the field is set on the
    patch but explicitly nulled — the patch contract forbids resetting a
    required value to None. Generic in ``T`` so the caller's field type
    flows through to the assignment site (type checkers see the concrete
    type at the use point, not ``object``).
    """
    if field not in patch_fields:
        return fallback
    value = getattr(patch, field)
    if value is None:
        raise TransactionValidationError(f"manual ledger patch {field} must not be null")
    return value  # type: ignore[no-any-return]  # bounded by caller's T via fallback


def _optional_patched[T](
    patch: ManualLedgerTransactionPatch,
    patch_fields: set[str],
    field: str,
    fallback: T,
) -> T:
    """Return ``patch.<field>`` when in patch_fields (None allowed); otherwise the fallback.

    Generic in ``T`` for the same reason as :func:`_required_patched`.
    """
    if field not in patch_fields:
        return fallback
    return getattr(patch, field)  # type: ignore[no-any-return]  # bounded by caller's T via fallback


def _command_from_patch(
    *,
    bucket_id: str,
    current: Transaction,
    patch: ManualLedgerTransactionPatch,
    actor: str,
    source_command: str,
) -> ManualLedgerTransactionCommand:
    raw = current.raw
    patch_fields = patch.model_fields_set
    booked_date = _required_patched(patch, patch_fields, "booked_date", raw.booked_date)
    amount = _required_patched(patch, patch_fields, "amount", raw.amount)
    currency = _required_patched(patch, patch_fields, "currency", raw.currency)
    direction = _required_patched(patch, patch_fields, "direction", current.direction)
    description = _required_patched(patch, patch_fields, "description", raw.description)
    business_classification = _required_patched(
        patch, patch_fields, "business_classification", current.business_classification
    )
    business_pct = _optional_patched(patch, patch_fields, "business_pct", current.business_pct)
    category_id = _optional_patched(patch, patch_fields, "category_id", current.category_id)
    taxable_base = _optional_patched(patch, patch_fields, "taxable_base", current.taxable_base)
    iva_rate = _optional_patched(patch, patch_fields, "iva_rate", current.iva_rate)
    iva_amount = _optional_patched(patch, patch_fields, "iva_amount", current.iva_amount)
    irpf_category = _optional_patched(patch, patch_fields, "irpf_category", current.irpf_category)
    usage_ratio_id = _optional_patched(patch, patch_fields, "usage_ratio_id", current.usage_ratio_id)
    prorrata_reference = _optional_patched(patch, patch_fields, "prorrata_reference", current.prorrata_reference)
    if "business_classification" in patch_fields and business_classification is not BusinessClassification.MIXED:
        business_pct = None
        usage_ratio_id = None
    if "business_classification" in patch_fields and business_classification not in {
        BusinessClassification.BUSINESS,
        BusinessClassification.MIXED,
    }:
        category_id = None
        taxable_base = None
        iva_rate = None
        iva_amount = None
        irpf_category = None
        prorrata_reference = None
    notes = _required_patched(patch, patch_fields, "notes", current.notes)
    attachment_ids = _required_patched(patch, patch_fields, "attachment_ids", current.attachment_ids)
    return ManualLedgerTransactionCommand(
        bucket_id=bucket_id,
        booked_date=booked_date,
        value_date=patch.value_date if "value_date" in patch_fields else raw.value_date,
        amount=amount,
        currency=currency,
        direction=direction,
        counterparty=patch.counterparty if "counterparty" in patch_fields else raw.counterparty,
        description=description,
        business_classification=business_classification,
        business_pct=business_pct,
        category_id=category_id,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
        irpf_category=irpf_category,
        usage_ratio_id=usage_ratio_id,
        prorrata_reference=prorrata_reference,
        purchase_invoice_evidence_id=(
            patch.purchase_invoice_evidence_id
            if "purchase_invoice_evidence_id" in patch_fields
            else current.purchase_invoice_evidence_id
        ),
        attachment_ids=attachment_ids,
        notes=notes,
        actor=actor,
        source_command=source_command,
    )


def _transition_manual_transaction_lifecycle(
    *,
    bucket_id: str,
    transaction_id: str,
    state: TransactionLifecycleState,
    event_type: BucketEventType,
    actor: str,
    reason: str,
    source_command: str,
    transaction_repository: TransactionCatalogueRepository | None,
    bucket_event_repository: BucketEventHistoryRepository | None,
    work_unit_repository: WorkUnitCatalogueRepository | None,
    calculation_repository: CalculationRevisionCatalogueRepository | None,
    occurred_at: datetime | None,
) -> ManualLedgerTransactionResult:
    now = _normalise_timestamp(occurred_at)
    trimmed_actor = _require_actor(actor, operation="ledger lifecycle")
    trimmed_source_command = _require_source_command(source_command, operation="ledger lifecycle")
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = bucket_event_repository or BucketEventHistoryRepository()
    catalogue = repository.load()
    current = _require_transaction(catalogue, transaction_id)
    if current.lifecycle_state is state:
        raise TransactionValidationError(
            f"ledger transaction is already {state.value.lower()}",
            context={"bucket_id": bucket_id, "transaction_id": transaction_id, "state": state.value},
        )
    if current.lifecycle_state is TransactionLifecycleState.ARCHIVED and state is TransactionLifecycleState.STASHED:
        raise TransactionValidationError(
            "archived ledger transactions cannot be stashed",
            context={"bucket_id": bucket_id, "transaction_id": transaction_id},
        )
    if current.lifecycle_state is TransactionLifecycleState.SPLIT or state is TransactionLifecycleState.SPLIT:
        raise TransactionValidationError(
            "split-lineage transitions are only available through split_transaction / merge_transactions",
            context={
                "bucket_id": bucket_id,
                "transaction_id": transaction_id,
                "current_state": current.lifecycle_state.value,
                "requested_state": state.value,
            },
        )
    blockers = _blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=_transaction_modelo_source_ids(current),
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    if blockers:
        _raise_finalized_modelo_blocked(
            operation="ledger transaction lifecycle transition",
            transaction_ids=_transaction_modelo_source_ids(current),
            blockers=blockers,
        )
    event = _build_bucket_event(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=now,
        actor=trimmed_actor,
        object_id=current.transaction_id,
        payload={
            "source_command": trimmed_source_command,
            "previous_lifecycle_state": current.lifecycle_state.value,
            "lifecycle_state": state.value,
            "reason": reason.strip(),
        },
    )
    lifecycle_entry = TransactionLifecycleLineageEntry(
        previous_state=current.lifecycle_state,
        state=state,
        actor=trimmed_actor,
        source_command=trimmed_source_command,
        changed_at=now,
        reason=reason,
        bucket_event_id=event.event_id,
    )
    replacement = current.model_copy(
        update={
            "lifecycle_state": state,
            "lifecycle_lineage": (*current.lifecycle_lineage, lifecycle_entry),
        }
    )
    updated = _replace_transaction(catalogue, old_transaction_id=current.transaction_id, replacement=replacement)
    _save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=updated,
        events=(event,),
    )
    return _result(bucket_id, replacement, (event.event_id,))


def _blocking_modelo_references(
    *,
    bucket_id: str,
    transaction_ids: tuple[str, ...],
    work_unit_repository: WorkUnitCatalogueRepository | None,
    calculation_repository: CalculationRevisionCatalogueRepository | None,
) -> tuple[LedgerRemovalBlocker, ...]:
    if not transaction_ids:
        return ()
    wanted = set(transaction_ids)
    work_units = (work_unit_repository or WorkUnitCatalogueRepository()).load()
    revisions = (calculation_repository or CalculationRevisionCatalogueRepository()).load()
    blockers: list[LedgerRemovalBlocker] = []
    for revision in revisions.values():
        if revision.state not in _REMOVAL_BLOCKING_REVISION_STATES:
            continue
        if not wanted.intersection(revision.source_transaction_ids):
            continue
        work_unit = work_units.get(revision.work_unit_id)
        if work_unit is None or work_unit.bucket_id != bucket_id:
            continue
        blockers.append(
            LedgerRemovalBlocker(
                work_unit_id=work_unit.work_unit_id,
                calculation_revision_id=revision.calculation_revision_id,
                revision_state=revision.state.value,
                modelo=work_unit.modelo,
                filing_year=work_unit.filing_year,
                period=work_unit.period,
            )
        )
    return tuple(
        sorted(
            blockers,
            key=lambda blocker: (
                blocker.modelo,
                blocker.filing_year,
                blocker.period,
                blocker.calculation_revision_id,
            ),
        )
    )


def _transaction_modelo_source_ids(transaction: Transaction) -> tuple[str, ...]:
    return tuple(
        sorted({transaction.transaction_id, *(entry.previous_transaction_id for entry in transaction.edit_lineage)})
    )


def _catalogue_modelo_source_ids(catalogue: TransactionCatalogue) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                source_id
                for transaction in catalogue.values()
                for source_id in _transaction_modelo_source_ids(transaction)
            }
        )
    )


def _ledger_export_rows(
    catalogue: TransactionCatalogue,
    *,
    bucket_id: str,
    include_inactive: bool,
) -> tuple[LedgerExportRow, ...]:
    transactions = tuple(
        transaction
        for transaction in catalogue.values()
        if include_inactive or transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
    )
    return tuple(
        _ledger_export_row(bucket_id=bucket_id, transaction=transaction)
        for transaction in sorted(
            transactions,
            key=lambda item: (
                item.raw.value_date or item.raw.booked_date,
                item.transaction_id,
            ),
        )
    )


def _ledger_export_row(*, bucket_id: str, transaction: Transaction) -> LedgerExportRow:
    raw = transaction.raw
    effective_date = raw.value_date or raw.booked_date
    return LedgerExportRow(
        bucket_id=bucket_id,
        transaction_id=transaction.transaction_id,
        lifecycle_state=transaction.lifecycle_state.value,
        booked_date=raw.booked_date.isoformat(),
        value_date="" if raw.value_date is None else raw.value_date.isoformat(),
        effective_date=effective_date.isoformat(),
        amount=_decimal_to_string(raw.amount),
        currency=raw.currency,
        direction=transaction.direction.value,
        counterparty=raw.counterparty or "",
        description=raw.description,
        business_classification=transaction.business_classification.value,
        business_pct=_optional_decimal(transaction.business_pct),
        category_id=transaction.category_id or "",
        taxable_base=_optional_decimal(transaction.taxable_base),
        iva_rate=_optional_decimal(transaction.iva_rate),
        iva_amount=_optional_decimal(transaction.iva_amount),
        irpf_category=transaction.irpf_category or "",
        usage_ratio_id=transaction.usage_ratio_id or "",
        prorrata_reference=transaction.prorrata_reference or "",
        purchase_invoice_evidence_id=transaction.purchase_invoice_evidence_id or "",
        attachment_ids=",".join(transaction.attachment_ids),
        notes=transaction.notes,
        created_by=transaction.created_by or "",
        created_source_command=transaction.source_command or "",
    )


def _ledger_export_id(
    *,
    bucket_id: str,
    export_format: str,
    sha256: str,
    transaction_ids: tuple[str, ...],
) -> str:
    payload = json.dumps(
        {
            "bucket_id": bucket_id,
            "export_format": export_format,
            "sha256": sha256,
            "transaction_ids": transaction_ids,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _transaction_ids_digest(transaction_ids: tuple[str, ...]) -> str:
    encoded = json.dumps(transaction_ids, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _raise_finalized_modelo_blocked(
    *,
    operation: str,
    transaction_ids: tuple[str, ...],
    blockers: tuple[LedgerRemovalBlocker, ...],
) -> None:
    first = blockers[0]
    raise TransactionValidationError(
        f"{operation} refused because finalized modelo revisions cite the transaction",
        context={
            "transaction_ids": ",".join(transaction_ids),
            "calculation_revision_id": first.calculation_revision_id,
            "work_unit_id": first.work_unit_id,
            "modelo": first.modelo,
            "filing_year": str(first.filing_year),
            "period": first.period,
            "blocking_reference_count": str(len(blockers)),
        },
    )


def _detach_transaction_from_purchase_evidence(
    catalogue: InvoiceCatalogue,
    *,
    bucket_id: str,
    transaction_id: str,
) -> tuple[tuple[str, ...], InvoiceCatalogue]:
    return _detach_transactions_from_purchase_evidence(
        catalogue,
        bucket_id=bucket_id,
        transaction_ids=(transaction_id,),
    )


def _detach_transactions_from_purchase_evidence(
    catalogue: InvoiceCatalogue,
    *,
    bucket_id: str,
    transaction_ids: tuple[str, ...],
) -> tuple[tuple[str, ...], InvoiceCatalogue]:
    detached_ids: list[str] = []
    wanted = set(transaction_ids)
    updated_invoices = dict(catalogue.invoices)
    for invoice_id, invoice in catalogue.invoices.items():
        if invoice.bucket_id != bucket_id or not wanted.intersection(invoice.linked_transaction_ids):
            continue
        remaining_links = tuple(item for item in invoice.linked_transaction_ids if item not in wanted)
        updated_invoices[invoice_id] = invoice.model_copy(update={"linked_transaction_ids": remaining_links})
        detached_ids.append(invoice_id)
    return tuple(sorted(detached_ids)), InvoiceCatalogue.model_validate({"invoices": updated_invoices})


def _removal_events(
    *,
    bucket_id: str,
    transaction: Transaction,
    actor: str,
    reason: str,
    source_command: str,
    purchase_evidence_ids: tuple[str, ...],
    attachment_ids: tuple[str, ...],
    occurred_at: datetime,
) -> tuple[BucketEvent, ...]:
    events: list[BucketEvent] = []
    for evidence_id in purchase_evidence_ids:
        events.append(
            _build_bucket_event(
                bucket_id=bucket_id,
                event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
                occurred_at=occurred_at,
                actor=actor,
                object_type=BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
                object_id=evidence_id,
                payload={
                    "source_command": source_command,
                    "transaction_id": transaction.transaction_id,
                    "reason": reason,
                    "mutation_kind": "ledger_transaction_removed",
                },
            )
        )
    for attachment_id in attachment_ids:
        events.append(
            _build_bucket_event(
                bucket_id=bucket_id,
                event_type=BucketEventType.ATTACHMENT_REMOVED,
                occurred_at=occurred_at,
                actor=actor,
                object_type=BucketEventObjectType.ATTACHMENT,
                object_id=attachment_id,
                payload={
                    "source_command": source_command,
                    "transaction_id": transaction.transaction_id,
                    "reason": reason,
                    "mutation_kind": "ledger_transaction_removed",
                },
            )
        )
    events.append(
        _build_bucket_event(
            bucket_id=bucket_id,
            event_type=BucketEventType.LEDGER_TRANSACTION_REMOVED,
            occurred_at=occurred_at,
            actor=actor,
            object_type=BucketEventObjectType.LEDGER_TRANSACTION,
            object_id=transaction.transaction_id,
            payload={
                "source_command": source_command,
                "reason": reason,
                "purchase_invoice_evidence_ids": ",".join(purchase_evidence_ids),
                "attachment_ids": ",".join(attachment_ids),
                "cascade_count": str(len(purchase_evidence_ids) + len(attachment_ids)),
            },
        )
    )
    return tuple(events)


def transaction_catalogue_object_id(bucket_id: str) -> str:
    return f"transaction-catalogue:{bucket_id.strip()}"


def _verify_evidence_references(
    command: ManualLedgerTransactionCommand,
    *,
    transaction_id: str,
    invoice_repository: InvoiceCatalogueRepository | None,
    attachment_store: _AttachmentStoreProtocol | None,
) -> None:
    if command.purchase_invoice_evidence_id is not None:
        invoices = (invoice_repository or InvoiceCatalogueRepository()).load()
        invoice = invoices.get(command.purchase_invoice_evidence_id)
        if invoice is None:
            raise TransactionValidationError(
                "purchase_invoice_evidence_id must reference an existing purchase invoice evidence record",
                context={"purchase_invoice_evidence_id": command.purchase_invoice_evidence_id},
            )
        if invoice.bucket_id != command.bucket_id:
            raise TransactionValidationError(
                "purchase_invoice_evidence_id must belong to the manual ledger command bucket",
                context={
                    "purchase_invoice_evidence_id": command.purchase_invoice_evidence_id,
                    "command_bucket_id": command.bucket_id,
                    "evidence_bucket_id": invoice.bucket_id or "",
                },
            )
        if invoice.kind is not InvoiceKind.RECEIVED:
            raise TransactionValidationError(
                "purchase_invoice_evidence_id must reference a received purchase invoice evidence record",
                context={
                    "purchase_invoice_evidence_id": command.purchase_invoice_evidence_id,
                    "invoice_kind": invoice.kind.value,
                },
            )
    if command.attachment_ids:
        store = attachment_store or AttachmentStore()
        for attachment_id in command.attachment_ids:
            try:
                attachment = store.load_manifest(attachment_id)
                store.verify_blob(attachment_id)
            except (AttachmentNotFoundError, AttachmentValidationError) as exc:
                raise TransactionValidationError(
                    "attachment_ids must reference existing secure attachment manifests and blobs",
                    context={"attachment_id": attachment_id},
                ) from exc
            if attachment.bucket_id != command.bucket_id:
                raise TransactionValidationError(
                    "attachment_ids must belong to the manual ledger command bucket",
                    context={
                        "attachment_id": attachment_id,
                        "command_bucket_id": command.bucket_id,
                        "attachment_bucket_id": attachment.bucket_id or "",
                    },
                )
            if attachment.linked_transaction_ids and transaction_id not in attachment.linked_transaction_ids:
                raise TransactionValidationError(
                    "attachment_id is linked to different ledger transactions",
                    context={"attachment_id": attachment_id, "transaction_id": transaction_id},
                )


def _verify_usage_ratio_reference(
    command: ManualLedgerTransactionCommand,
    *,
    usage_ratio_profile: UsageRatioProfile | None,
) -> None:
    if command.usage_ratio_id is None:
        return
    profile = usage_ratio_profile or load_usage_ratios(bucket_id=command.bucket_id)
    try:
        validate_usage_ratio_reference(
            profile,
            category_id=command.category_id,
            usage_ratio_id=command.usage_ratio_id,
            business_pct=command.business_pct,
        )
    except UsageRatioValidationError as exc:
        raise TransactionValidationError(
            str(exc),
            context={
                "bucket_id": command.bucket_id,
                "category_id": command.category_id or "",
                "usage_ratio_id": command.usage_ratio_id,
            },
        ) from exc


def _event_payload(command: ManualLedgerTransactionCommand) -> dict[str, str]:
    payload = {
        "source_command": command.source_command,
        "direction": command.direction.value,
        "amount": _decimal_to_string(command.amount),
        "currency": command.currency,
    }
    if command.business_pct is not None:
        payload["business_pct"] = _decimal_to_string(command.business_pct)
    if command.usage_ratio_id is not None:
        payload["usage_ratio_id"] = command.usage_ratio_id
    return payload


def _update_event_specs(
    *,
    current: Transaction,
    replacement: Transaction,
    command: ManualLedgerTransactionCommand,
    previous_transaction_id: str,
) -> tuple[_EventSpec, ...]:
    common_payload = {
        **_event_payload(command),
        "previous_transaction_id": previous_transaction_id,
    }
    specs: list[_EventSpec] = []
    if _core_edit_changed(current, replacement):
        specs.append(
            (
                BucketEventType.LEDGER_TRANSACTION_UPDATED,
                BucketEventObjectType.LEDGER_TRANSACTION,
                replacement.transaction_id,
                {**common_payload, "mutation_kind": "edit"},
            )
        )
    if _classification_changed(current, replacement):
        specs.append(
            (
                BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
                BucketEventObjectType.LEDGER_TRANSACTION,
                replacement.transaction_id,
                {
                    **common_payload,
                    "classification": replacement.business_classification.value,
                    "category_id": replacement.category_id or "",
                    "mutation_kind": "classification",
                },
            )
        )
    if _allocation_changed(current, replacement):
        specs.append(
            (
                BucketEventType.LEDGER_TRANSACTION_ALLOCATED,
                BucketEventObjectType.LEDGER_TRANSACTION,
                replacement.transaction_id,
                {
                    **common_payload,
                    "business_pct": _optional_decimal(replacement.business_pct),
                    "usage_ratio_id": replacement.usage_ratio_id or "",
                    "prorrata_reference": replacement.prorrata_reference or "",
                    "mutation_kind": "allocation",
                },
            )
        )
    specs.extend(_evidence_event_specs(current=current, replacement=replacement, common_payload=common_payload))
    if not specs:
        specs.append(
            (
                BucketEventType.LEDGER_TRANSACTION_UPDATED,
                BucketEventObjectType.LEDGER_TRANSACTION,
                replacement.transaction_id,
                {**common_payload, "mutation_kind": "correction"},
            )
        )
    return tuple(specs)


def _core_edit_changed(current: Transaction, replacement: Transaction) -> bool:
    return any(
        getattr(current.raw, field) != getattr(replacement.raw, field)
        for field in ("booked_date", "value_date", "amount", "currency", "counterparty", "description")
    ) or any(
        getattr(current, field) != getattr(replacement, field)
        for field in ("direction", "taxable_base", "iva_rate", "iva_amount", "irpf_category", "notes")
    )


def _classification_changed(current: Transaction, replacement: Transaction) -> bool:
    return any(
        getattr(current, field) != getattr(replacement, field)
        for field in ("business_classification", "category_id", "classification_reason")
    )


def _allocation_changed(current: Transaction, replacement: Transaction) -> bool:
    return any(
        getattr(current, field) != getattr(replacement, field)
        for field in ("business_pct", "usage_ratio_id", "prorrata_reference")
    )


def _evidence_event_specs(
    *,
    current: Transaction,
    replacement: Transaction,
    common_payload: Mapping[str, str],
) -> tuple[_EventSpec, ...]:
    specs: list[_EventSpec] = []
    if current.purchase_invoice_evidence_id != replacement.purchase_invoice_evidence_id:
        if current.purchase_invoice_evidence_id is not None:
            specs.append(
                (
                    BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
                    BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
                    current.purchase_invoice_evidence_id,
                    {
                        **common_payload,
                        "transaction_id": replacement.transaction_id,
                        "mutation_kind": "purchase_invoice_evidence_detached",
                    },
                )
            )
        if replacement.purchase_invoice_evidence_id is not None:
            specs.append(
                (
                    (
                        BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED
                        if current.purchase_invoice_evidence_id is not None
                        else BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED
                    ),
                    BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
                    replacement.purchase_invoice_evidence_id,
                    {
                        **common_payload,
                        "transaction_id": replacement.transaction_id,
                        "mutation_kind": "purchase_invoice_evidence_attached",
                    },
                )
            )
    current_attachments = set(current.attachment_ids)
    replacement_attachments = set(replacement.attachment_ids)
    for attachment_id in sorted(replacement_attachments - current_attachments):
        specs.append(
            (
                BucketEventType.ATTACHMENT_LINKED,
                BucketEventObjectType.ATTACHMENT,
                attachment_id,
                {
                    **common_payload,
                    "transaction_id": replacement.transaction_id,
                    "linked": "true",
                    "mutation_kind": "attachment_linked",
                },
            )
        )
    for attachment_id in sorted(current_attachments - replacement_attachments):
        specs.append(
            (
                BucketEventType.ATTACHMENT_REMOVED,
                BucketEventObjectType.ATTACHMENT,
                attachment_id,
                {
                    **common_payload,
                    "transaction_id": replacement.transaction_id,
                    "linked": "false",
                    "mutation_kind": "attachment_removed",
                },
            )
        )
    return tuple(specs)


def _transaction_from_command(
    command: ManualLedgerTransactionCommand,
    *,
    occurred_at: datetime,
    provider_transaction_id: str | None = None,
    bucket_event_id: str | None = None,
    created_by: str | None = None,
    created_source_command: str | None = None,
    created_event_id: str | None = None,
    existing_evidence_provenance: tuple[TransactionEvidenceProvenanceEntry, ...] = (),
    existing_edit_lineage: tuple[TransactionEditLineageEntry, ...] = (),
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
    lifecycle_lineage: tuple[TransactionLifecycleLineageEntry, ...] = (),
    edit_lineage_entry: TransactionEditLineageEntry | None = None,
    evidence_event_ids: Mapping[tuple[str, str], str] | None = None,
) -> Transaction:
    raw = RawTransaction(
        transaction_id=provider_transaction_id or _provider_transaction_id(command, occurred_at=occurred_at),
        booked_date=command.booked_date,
        value_date=command.value_date,
        amount=command.amount,
        currency=command.currency,
        counterparty=command.counterparty,
        description=command.description,
        provenance=RawProvenance(
            source_path=Path.cwd() / ".aeat-manual-ledger",
            source_sha256=_source_sha256(command, occurred_at=occurred_at),
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=occurred_at,
            provider_name=_MANUAL_PROVIDER_NAME,
        ),
        raw_fields=_raw_fields(command),
    )
    payload: dict[str, object] = {
        "raw": raw,
        "direction": command.direction,
        "business_classification": command.business_classification,
        "business_pct": command.business_pct,
        "category_id": command.category_id,
        "taxable_base": command.taxable_base,
        "iva_rate": command.iva_rate,
        "iva_amount": command.iva_amount,
        "irpf_category": command.irpf_category,
        "usage_ratio_id": command.usage_ratio_id,
        "prorrata_reference": command.prorrata_reference,
        "purchase_invoice_evidence_id": command.purchase_invoice_evidence_id,
        "attachment_ids": command.attachment_ids,
        "created_by": created_by or command.actor,
        "source_command": created_source_command or command.source_command,
        "created_event_id": created_event_id or bucket_event_id,
        "lifecycle_state": lifecycle_state,
        "lifecycle_lineage": lifecycle_lineage,
        "evidence_provenance": _evidence_provenance(
            command,
            occurred_at=occurred_at,
            bucket_event_id=bucket_event_id,
            existing=existing_evidence_provenance,
            evidence_event_ids=evidence_event_ids or {},
        ),
        "edit_lineage": (
            (*existing_edit_lineage, edit_lineage_entry) if edit_lineage_entry is not None else existing_edit_lineage
        ),
        "notes": command.notes,
    }
    if command.business_classification is not BusinessClassification.NOT_YET_PROCESSED:
        payload.update(
            {
                "classified_at": occurred_at,
                "classified_by": "manual",
                "classification_reason": command.source_command,
                "classification_confidence": Decimal("1"),
            }
        )
    return Transaction.model_validate(payload)


def _evidence_provenance(
    command: ManualLedgerTransactionCommand,
    *,
    occurred_at: datetime,
    bucket_event_id: str | None,
    existing: tuple[TransactionEvidenceProvenanceEntry, ...],
    evidence_event_ids: Mapping[tuple[str, str], str],
) -> tuple[TransactionEvidenceProvenanceEntry, ...]:
    wanted = (
        {("purchase_invoice_evidence", command.purchase_invoice_evidence_id)}
        if command.purchase_invoice_evidence_id is not None
        else set()
    ) | {("attachment", attachment_id) for attachment_id in command.attachment_ids}
    retained = tuple(entry for entry in existing if (entry.evidence_kind, entry.evidence_id) in wanted)
    seen = {(entry.evidence_kind, entry.evidence_id) for entry in retained}
    created: list[TransactionEvidenceProvenanceEntry] = []
    for evidence_kind, evidence_id in sorted(wanted - seen):
        typed_kind: Literal["purchase_invoice_evidence", "attachment"] = (
            "purchase_invoice_evidence" if evidence_kind == "purchase_invoice_evidence" else "attachment"
        )
        evidence_event_id = evidence_event_ids.get((typed_kind, evidence_id), bucket_event_id)
        created.append(
            TransactionEvidenceProvenanceEntry(
                evidence_kind=typed_kind,
                evidence_id=evidence_id,
                actor=command.actor,
                source_command=command.source_command,
                linked_at=occurred_at,
                bucket_event_id=evidence_event_id,
            )
        )
    return (*retained, *created)


def _provider_transaction_id(command: ManualLedgerTransactionCommand, *, occurred_at: datetime) -> str:
    if command.idempotency_key is not None:
        return f"manual:{command.bucket_id}:{command.idempotency_key}"
    return f"manual:{command.bucket_id}:{occurred_at.isoformat()}:{_source_sha256(command, occurred_at=occurred_at)}"


def _source_sha256(command: ManualLedgerTransactionCommand, *, occurred_at: datetime) -> str:
    payload = command.model_dump(mode="json")
    payload["occurred_at"] = occurred_at.isoformat()
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _raw_fields(command: ManualLedgerTransactionCommand) -> Mapping[str, str]:
    values = {
        "source_kind": "ledger_transaction",
        "source_command": command.source_command,
        "actor": command.actor,
        "business_classification": command.business_classification.value,
        "direction": command.direction.value,
        "taxable_base": _optional_decimal(command.taxable_base),
        "iva_rate": _optional_decimal(command.iva_rate),
        "iva_amount": _optional_decimal(command.iva_amount),
        "irpf_category": command.irpf_category or "",
        "usage_ratio_id": command.usage_ratio_id or "",
        "prorrata_reference": command.prorrata_reference or "",
        "purchase_invoice_evidence_id": command.purchase_invoice_evidence_id or "",
        "attachment_ids": ",".join(command.attachment_ids),
    }
    if command.business_pct is not None:
        values["business_pct"] = _decimal_to_string(command.business_pct)
    if command.category_id is not None:
        values["category_id"] = command.category_id
    if command.idempotency_key is not None:
        values["idempotency_key"] = command.idempotency_key
    return values


def _optional_decimal(value: Decimal | None) -> str:
    return "" if value is None else _decimal_to_string(value)


def _display_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _decimal_to_string(value: Decimal) -> str:
    return format(value, "f")


def _normalise_timestamp(value: datetime | None) -> datetime:
    timestamp = value or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _upsert_transaction(catalogue: TransactionCatalogue, transaction: Transaction) -> TransactionCatalogue:
    updated = dict(catalogue.transactions)
    updated[transaction.transaction_id] = transaction
    return TransactionCatalogue.model_validate({"transactions": updated})


def _replace_transaction(
    catalogue: TransactionCatalogue,
    *,
    old_transaction_id: str,
    replacement: Transaction,
) -> TransactionCatalogue:
    updated = dict(catalogue.transactions)
    updated.pop(old_transaction_id, None)
    updated[replacement.transaction_id] = replacement
    return TransactionCatalogue.model_validate({"transactions": updated})


def _remove_transaction(catalogue: TransactionCatalogue, *, transaction_id: str) -> TransactionCatalogue:
    updated = dict(catalogue.transactions)
    updated.pop(transaction_id, None)
    return TransactionCatalogue.model_validate({"transactions": updated})


def _require_transaction(catalogue: TransactionCatalogue, transaction_id: str) -> Transaction:
    transaction = catalogue.get(transaction_id)
    if transaction is None:
        raise TransactionNotFoundError(
            f"transaction not found: {transaction_id}",
            context={"namespace": TX_BUCKET_NAMESPACE, "transaction_id": transaction_id},
        )
    return transaction


def _mutation_signature(transaction: Transaction) -> tuple[object, ...]:
    raw = transaction.raw
    return (
        raw.booked_date,
        raw.value_date,
        raw.amount,
        raw.currency,
        raw.counterparty,
        raw.description,
        transaction.direction,
        transaction.business_classification,
        transaction.business_pct,
        transaction.category_id,
        transaction.taxable_base,
        transaction.iva_rate,
        transaction.iva_amount,
        transaction.irpf_category,
        transaction.usage_ratio_id,
        transaction.prorrata_reference,
        transaction.purchase_invoice_evidence_id,
        transaction.attachment_ids,
        transaction.notes,
    )


def _build_bucket_event(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
    object_id: str,
    payload: Mapping[str, str],
    object_type: BucketEventObjectType = BucketEventObjectType.LEDGER_TRANSACTION,
) -> BucketEvent:
    event = BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor=actor,
            object_type=object_type,
            object_id=object_id,
            payload=payload,
        ),
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        payload_version=_BUCKET_EVENT_PAYLOAD_VERSION,
        payload=dict(payload),
    )
    return event


def _append_bucket_event(*, repository: BucketEventHistoryRepository, event: BucketEvent) -> None:
    repository.save(append_bucket_event(repository.load(), event))


def _append_bucket_events(*, repository: BucketEventHistoryRepository, events: tuple[BucketEvent, ...]) -> None:
    catalogue = repository.load()
    for event in events:
        catalogue = append_bucket_event(catalogue, event)
    repository.save(catalogue)


def _save_transaction_catalogue_and_events(
    *,
    transaction_repository: TransactionCatalogueRepository,
    event_repository: BucketEventHistoryRepository,
    catalogue: TransactionCatalogue,
    events: tuple[BucketEvent, ...],
) -> None:
    event_catalogue = event_repository.load()
    for event in events:
        event_catalogue = append_bucket_event(event_catalogue, event)
    transaction_repository.save_with_secure_object_writes(
        catalogue,
        (event_repository.to_secure_object_write(event_catalogue),),
    )


def _save_transaction_catalogue_invoices_and_events(
    *,
    transaction_repository: TransactionCatalogueRepository,
    invoice_repository: InvoiceCatalogueRepository,
    event_repository: BucketEventHistoryRepository,
    transaction_catalogue: TransactionCatalogue,
    invoice_catalogue: InvoiceCatalogue,
    events: tuple[BucketEvent, ...],
) -> None:
    event_catalogue = event_repository.load()
    for event in events:
        event_catalogue = append_bucket_event(event_catalogue, event)
    transaction_repository.save_with_secure_object_writes(
        transaction_catalogue,
        (
            invoice_repository.to_secure_object_write(invoice_catalogue),
            event_repository.to_secure_object_write(event_catalogue),
        ),
    )


def _primary_lineage_event_id(events: tuple[BucketEvent, ...]) -> str:
    for event in events:
        if event.object_type is BucketEventObjectType.LEDGER_TRANSACTION:
            return event.event_id
    return events[0].event_id


def _evidence_event_ids(events: tuple[BucketEvent, ...]) -> dict[tuple[str, str], str]:
    mapping: dict[tuple[str, str], str] = {}
    for event in events:
        if event.event_type in {
            BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
            BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED,
        }:
            mapping[("purchase_invoice_evidence", event.object_id)] = event.event_id
        if event.event_type is BucketEventType.ATTACHMENT_LINKED:
            mapping[("attachment", event.object_id)] = event.event_id
    return mapping


def _import_batch_id(
    *,
    bucket_id: str,
    source_command: str,
    imported_transaction_ids: tuple[str, ...],
) -> str:
    encoded = json.dumps(
        {
            "bucket_id": bucket_id,
            "source_command": source_command,
            "imported_transaction_ids": imported_transaction_ids,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _result(
    bucket_id: str,
    transaction: Transaction,
    bucket_event_ids: tuple[str, ...],
) -> ManualLedgerTransactionResult:
    return ManualLedgerTransactionResult(
        ref=BucketTransactionRef(bucket_id=bucket_id, transaction_id=transaction.transaction_id),
        transaction=transaction,
        bucket_event_ids=bucket_event_ids,
    )
