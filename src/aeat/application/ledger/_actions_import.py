"""Application services for bucket-scoped manual ledger transactions.

Services operate over a :class:`TransactionCatalogueRepository` for ledger
state, a :class:`BucketEventHistoryRepository` for durable audit events, and
an optional :class:`InvoiceCatalogueRepository` for purchase-invoice evidence
cascade on removal. The inner functions accept a :class:`TransactionCatalogue`
or :class:`InvoiceCatalogue` directly when the caller supplies pre-loaded data.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from ...adapters.inbound.financial.providers import ParsedLedgerRow, ProviderValidation

from ...core.errors import resolve_error_message
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.hashing import sha256_file
from ...core.i18n import tr
from ...domain.buckets import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.currency import (
    CurrencyNormalizationService,
    CurrencyNormalizationStatus,
    MonetaryAmount,
)
from ...domain.transactions import (
    TX_BUCKET_NAMESPACE,
    BucketTransactionRef,
    ImportSummary,
    RawTransaction,
    Transaction,
    TransactionCatalogue,
    TransactionValidationError,
    derive_import_fingerprint,
    derive_movement_day_key,
    derive_transaction_id,
)
from ...domain.transactions._protocols import TransactionCatalogueRepositoryProtocol
from ..transactions import LedgerImportDiagnostic, import_ledger_with_diagnostics
from ._actions_common import (
    _append_bucket_events,
    _bucket_event_repository,
    _build_bucket_event,
    _normalise_timestamp,
    _save_transaction_catalogue_and_events,
    _transaction_repository,
)
from ._models import (
    LedgerImportDiagnosticReport,
    LedgerImportOperationResult,
    LedgerSourceImportCommand,
    LedgerSourceImportResult,
    LedgerSourceValidationReport,
    LedgerSourceVerificationReport,
)
from ._protocols import FinancialProviderProtocol


class LedgerProviderID(StrEnum):
    """Canonical provider ID strings accepted by the ledger import dispatch."""

    AUTO = "auto"
    CSV = "csv"
    OFX = "ofx"
    QFX = "qfx"
    XLSX = "xlsx"
    EXCEL = "excel"
    N26 = "n26"
    PDF = "pdf"
    PDF_N26 = "pdf-n26"


def _transaction_dedup_fingerprint(transaction: Transaction) -> str:
    """Return the import-dedup fingerprint for an already-stored transaction.

    Rows imported after the cross-format dedup landed carry a stamped
    :attr:`Transaction.import_fingerprint`; that value is the canonical
    identity and is used verbatim. Hand-entered rows (and any legacy
    imported row that predates the stamp) have no fingerprint, so the
    fingerprint is derived from the current ``raw`` as a best-effort
    fallback â€” this keeps re-imports of legacy rows idempotent.
    """
    return transaction.import_fingerprint or derive_import_fingerprint(transaction.raw)


class _ImportRowPlan(NamedTuple):
    """Per-row outcome of evaluating an import batch against a catalogue.

    ``imported`` rows are new movements; ``skipped_refs`` rows already
    exist (a confident fingerprint match â€” re-import or cross-format
    re-export of a row already present); ``likely_duplicate_refs`` rows
    are imported but share an effective date and amount with an existing
    row under a divergent narrative, so the operator is warned.
    """

    imported: tuple[Transaction, ...]
    skipped_refs: tuple[BucketTransactionRef, ...]
    likely_duplicate_refs: tuple[BucketTransactionRef, ...]


def _apply_fx_conversion(
    raw: RawTransaction,
    currency_normalizer: CurrencyNormalizationService | None,
) -> tuple[Decimal | None, Decimal | None, str | None, str | None]:
    """Return ``(fx_rate, value_in_eur, rate_source, rate_date_iso)`` for a raw row.

    EUR-native rows and non-EUR rows with no normalizer / a missing rate yield
    all ``None``, preserving the coupling invariant on :class:`Transaction`.
    """
    if raw.currency == DEFAULT_CURRENCY or currency_normalizer is None:
        return (None, None, None, None)
    rate_date = raw.value_date or raw.booked_date
    result = currency_normalizer.normalize(MonetaryAmount(amount=raw.amount, currency=raw.currency), rate_date)
    if result.status is not CurrencyNormalizationStatus.NORMALIZED or result.rate is None:
        return (None, None, None, None)
    # value_in_eur is the non-negative EUR magnitude; flow is carried solely by
    # direction (Transaction.value_in_eur rejects negatives).
    rate_date_iso = result.rate_date.isoformat() if result.rate_date is not None else None
    return (result.rate, abs(result.eur_amount), result.rate_source, rate_date_iso)


def _evaluate_import_rows(
    *,
    bucket_id: str,
    catalogue: TransactionCatalogue,
    parsed_rows: tuple[ParsedLedgerRow, ...],
    currency_normalizer: CurrencyNormalizationService | None = None,
    occurred_at: datetime | None = None,
) -> _ImportRowPlan:
    """Classify every parsed row as imported / skipped / likely-duplicate.

    Each :class:`ParsedLedgerRow` carries the magnitude
    :class:`RawTransaction` and the authoritative ``direction`` the provider
    derived from the source sign at the parse boundary; this classifier never
    re-derives flow from a sign. Deduplication keys on
    :func:`derive_import_fingerprint` â€” an identity that is stable across both
    later edits of a transaction and a re-export of the same movement in a
    different file format. This single classifier backs both the persisting
    import path and the ``--dry-run`` preview, so the preview count is exact.
    """
    existing_fingerprints = {_transaction_dedup_fingerprint(transaction) for transaction in catalogue.values()}
    existing_day_keys = {derive_movement_day_key(transaction.raw) for transaction in catalogue.values()}
    imported: list[Transaction] = []
    skipped_refs: list[BucketTransactionRef] = []
    likely_duplicate_refs: list[BucketTransactionRef] = []
    batch_fingerprints: set[str] = set()
    for parsed in parsed_rows:
        raw = parsed.raw
        fingerprint = derive_import_fingerprint(raw)
        if fingerprint in existing_fingerprints or fingerprint in batch_fingerprints:
            skipped_refs.append(BucketTransactionRef(bucket_id=bucket_id, transaction_id=derive_transaction_id(raw)))
            continue
        fx_rate, value_in_eur, rate_source, rate_date = _apply_fx_conversion(raw, currency_normalizer)
        stamped_at = occurred_at if occurred_at is not None else raw.provenance.ingested_at
        transaction = Transaction.model_validate(
            {
                "raw": raw,
                "direction": parsed.direction,
                "import_fingerprint": fingerprint,
                "fx_rate": fx_rate,
                "value_in_eur": value_in_eur,
                "rate_source": rate_source,
                "rate_date": rate_date,
                # D6: an imported row is freshly created at import time.
                "created_at": stamped_at,
                "modified_at": stamped_at,
            },
        )
        batch_fingerprints.add(fingerprint)
        imported.append(transaction)
        if derive_movement_day_key(raw) in existing_day_keys:
            likely_duplicate_refs.append(
                BucketTransactionRef(bucket_id=bucket_id, transaction_id=transaction.transaction_id),
            )
    return _ImportRowPlan(
        imported=tuple(imported),
        skipped_refs=tuple(skipped_refs),
        likely_duplicate_refs=tuple(likely_duplicate_refs),
    )


def import_ledger_transactions(
    *,
    bucket_id: str,
    parsed_rows: Iterable[ParsedLedgerRow],
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    actor: str = "operator",
    source_command: str = "aeat app ledger import",
    occurred_at: datetime | None = None,
    currency_normalizer: CurrencyNormalizationService | None = None,
) -> LedgerImportOperationResult:
    """Import provider rows into one bucket catalogue and emit events.

    Each :class:`ParsedLedgerRow` carries the magnitude
    :class:`RawTransaction` plus the authoritative ``direction`` the provider
    derived at the parse boundary, so the import path never re-derives flow
    from a sign.

    Returns a :class:`LedgerImportOperationResult` summarising the number
    of imported, skipped, and failed transactions.
    """
    now = _normalise_timestamp(occurred_at)
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = _bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    catalogue = repository.load()
    rows = tuple(parsed_rows)
    plan = _evaluate_import_rows(
        bucket_id=bucket_id,
        catalogue=catalogue,
        parsed_rows=rows,
        currency_normalizer=currency_normalizer,
        occurred_at=now,
    )
    imported_transactions = list(plan.imported)
    imported_refs = [
        BucketTransactionRef(bucket_id=bucket_id, transaction_id=transaction.transaction_id)
        for transaction in imported_transactions
    ]
    skipped_refs = list(plan.skipped_refs)
    updated_transactions = dict(catalogue.transactions)
    for transaction in imported_transactions:
        updated_transactions[transaction.transaction_id] = transaction
    import_batch_id = _import_batch_id(
        bucket_id=bucket_id,
        source_command=source_command,
        imported_transaction_ids=tuple(derive_transaction_id(parsed.raw) for parsed in rows),
    )
    summary = ImportSummary(
        imported=len(imported_refs),
        skipped=len(skipped_refs),
        bucket_id=bucket_id,
        imported_refs=tuple(imported_refs),
        skipped_refs=tuple(skipped_refs),
        likely_duplicate_refs=plan.likely_duplicate_refs,
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
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    currency_normalizer: CurrencyNormalizationService | None = None,
) -> LedgerSourceImportResult:
    """Validate, ingest, and optionally persist one ledger source file.

    Returns a :class:`LedgerSourceImportResult`.
    """
    provider = _resolve_financial_provider(command.provider, command.path)
    validation = _validate_import_source(provider, command.path)
    source_verification = _build_source_verification(source=command.source, verify=command.verify)
    from ...adapters.inbound.financial.providers import FinancialProviderError

    try:
        parsed_rows = tuple(provider.ingest(command.path))
    except FinancialProviderError as exc:
        raise TransactionValidationError(
            translated_message="errors.transaction.ledger_import_failed",
            context={"reason": resolve_error_message(exc)},
        ) from exc
    repository = (
        _transaction_repository(bucket_id=command.bucket_id, repository=transaction_repository)
        if command.bucket_id is not None
        else transaction_repository
    )
    existing_catalogue = repository.load() if repository is not None else TransactionCatalogue()
    diagnostic_result = (
        import_ledger_with_diagnostics(
            command.path,
            tuple(parsed.raw for parsed in parsed_rows),
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
        # A dry run must preview the *real* outcome: how many rows would
        # be imported and how many skipped as duplicates against the
        # already-stored catalogue. Reporting a flat zero made the
        # preview useless and misleading. The classification reuses the
        # exact persisting-path dedup logic, then discards every row.
        dry_run_plan = _evaluate_import_rows(
            bucket_id=command.bucket_id or "preview",
            catalogue=existing_catalogue,
            parsed_rows=parsed_rows,
            currency_normalizer=currency_normalizer,
        )
        return LedgerSourceImportResult(
            rows=len(parsed_rows),
            imported=len(dry_run_plan.imported),
            skipped=len(dry_run_plan.skipped_refs),
            likely_duplicates=len(dry_run_plan.likely_duplicate_refs),
            dry_run=True,
            verify=command.verify,
            period=command.period,
            bucket_id=command.bucket_id,
            likely_duplicate_transaction_refs=dry_run_plan.likely_duplicate_refs,
            validation=_validation_report(validation),
            source=source_verification,
            diagnostics=diagnostics,
        )
    if command.bucket_id is None:
        raise TransactionValidationError(
            translated_message="errors.transaction.ledger_import_requires_bucket",
        )
    repository = _transaction_repository(bucket_id=command.bucket_id, repository=repository)
    event_repository = _bucket_event_repository(bucket_id=command.bucket_id, repository=bucket_event_repository)
    result = import_ledger_transactions(
        bucket_id=command.bucket_id,
        parsed_rows=parsed_rows,
        transaction_repository=repository,
        bucket_event_repository=event_repository,
        actor=command.actor,
        source_command=command.source_command,
        currency_normalizer=currency_normalizer,
    )
    summary = result.summary
    diagnostic_events = _diagnostic_events(
        bucket_id=command.bucket_id,
        import_batch_id=result.import_batch_id,
        diagnostics=diagnostic_result.diagnostics if diagnostic_result is not None else (),
        transaction_ids=tuple(derive_transaction_id(parsed.raw) for parsed in parsed_rows),
        actor=command.actor,
        source_command=command.source_command,
    )
    if diagnostic_events:
        _append_bucket_events(repository=event_repository, events=diagnostic_events)
    return LedgerSourceImportResult(
        rows=len(parsed_rows),
        imported=summary.imported,
        skipped=summary.skipped,
        likely_duplicates=len(summary.likely_duplicate_refs),
        dry_run=False,
        verify=command.verify,
        period=command.period,
        bucket_id=summary.bucket_id,
        import_batch_id=result.import_batch_id,
        bucket_event_ids=result.bucket_event_ids + tuple(event.event_id for event in diagnostic_events),
        imported_transaction_refs=summary.imported_refs,
        skipped_transaction_refs=summary.skipped_refs,
        likely_duplicate_transaction_refs=summary.likely_duplicate_refs,
        validation=_validation_report(validation),
        source=source_verification,
        diagnostics=diagnostics,
    )


def _resolve_financial_provider(provider: str, path: Path) -> FinancialProviderProtocol:
    from ...adapters.inbound.financial.providers import (
        CsvProvider,
        OfxProvider,
        PdfN26Provider,
        XlsxProvider,
        detect_provider,
    )

    try:
        provider_id = LedgerProviderID(provider.strip().lower())
    except ValueError as exc:
        known = ", ".join(p.value for p in LedgerProviderID)
        raise TransactionValidationError(
            translated_message="errors.transaction.unknown_ledger_provider",
            context={"provider": provider, "providers": known},
        ) from exc
    if provider_id is LedgerProviderID.AUTO:
        detected = detect_provider(path)
        if detected is None:
            raise TransactionValidationError(f"auto-detection of ledger format failed for {path}")
        return detected
    if provider_id is LedgerProviderID.CSV:
        return CsvProvider()
    if provider_id in {LedgerProviderID.OFX, LedgerProviderID.QFX}:
        return OfxProvider()
    if provider_id in {LedgerProviderID.XLSX, LedgerProviderID.EXCEL}:
        return XlsxProvider()
    if provider_id is LedgerProviderID.N26:
        detected = detect_provider(path)
        if detected is None:
            raise TransactionValidationError(f"auto-detection of N26 format failed for {path}")
        return detected
    # PDF and PDF_N26
    return PdfN26Provider()


def _validate_import_source(provider: FinancialProviderProtocol, path: Path) -> ProviderValidation:
    if not path.exists() or not path.is_file():
        raise TransactionValidationError(
            translated_message="errors.financial.source_file_not_found",
            context={"path": str(path)},
        )
    validation = provider.validate_source(path)
    if not validation.is_valid:
        reason = "; ".join(validation.warnings) or tr("errors.transaction.import_source_invalid")
        raise TransactionValidationError(
            translated_message="errors.transaction.ledger_import_failed",
            context={"reason": reason},
        )
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
                ),
            )
    return tuple(events)


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
