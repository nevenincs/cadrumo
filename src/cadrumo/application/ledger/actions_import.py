"""Ledger source import services for bucket-scoped transaction catalogues.

Provider rows arrive as
:class:`~cadrumo.adapters.inbound.financial.providers.ParsedLedgerRow` objects.
This module classifies them against a loaded :class:`TransactionCatalogue`,
persists imported :class:`~cadrumo.domain.transactions.Transaction` instances,
records ``LEDGER_TRANSACTION_IMPORTED`` bucket events, and returns
:class:`~cadrumo.application.ledger.models.LedgerImportOperationResult` or
:class:`~cadrumo.application.ledger.models.LedgerSourceImportResult`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from ...core.hashing import sha256_hex

if TYPE_CHECKING:
    from ...adapters.inbound.financial.providers import ParsedLedgerRow, ProviderValidation

from ...adapters.persistence.storage import TRANSACTION_CATALOGUE_NAMESPACE
from ...core.errors import resolve_error_message
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.hashing import canonical_json_bytes, sha256_file
from ...core.i18n import tr
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepositoryProtocol,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.currency import (
    CurrencyNormalizationService,
    CurrencyNormalizationStatus,
    MonetaryAmount,
)
from ...domain.transactions import (
    BucketTransactionRef,
    ImportSummary,
    RawTransaction,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepositoryProtocol,
    TransactionValidationError,
    derive_import_fingerprint,
    derive_movement_day_key,
    derive_transaction_id,
    existing_transaction_import_fingerprints,
)
from ..transactions import LedgerImportDiagnostic, classify_import_row, import_ledger_with_diagnostics
from .actions_common import (
    append_bucket_events,
    build_ledger_bucket_event,
    normalise_timestamp,
    resolve_bucket_event_repository,
    resolve_transaction_repository,
    save_transaction_catalogue_and_events,
)
from .models import (
    LedgerImportDiagnosticReport,
    LedgerImportOperationResult,
    LedgerSourceImportCommand,
    LedgerSourceImportResult,
    LedgerSourceValidationReport,
    LedgerSourceVerificationReport,
)
from .protocols import FinancialProviderProtocol


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


def _source_jurisdiction_from_raw_fields(raw_fields: Mapping[str, str]) -> str | None:
    """Read canonical source-jurisdiction provenance from provider raw fields."""
    for header, value in raw_fields.items():
        normalized_header = " ".join(header.replace("\ufeff", "").replace("_", " ").replace("-", " ").lower().split())
        if normalized_header != "source jurisdiction":
            continue
        normalized_value = value.strip()
        return normalized_value or None
    return None


def _apply_fx_conversion(
    raw: RawTransaction,
    currency_normalizer: CurrencyNormalizationService | None,
) -> tuple[Decimal | None, Decimal | None, str | None, str | None]:
    """Return ``(fx_rate, value_in_eur, rate_source, rate_date_iso)`` for a raw row.

    EUR-native rows and non-EUR rows with no normalizer / a missing rate yield
    all ``None``, preserving the coupling invariant on
    :class:`~cadrumo.domain.transactions.Transaction`.
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

    Each :class:`~cadrumo.adapters.inbound.financial.providers.ParsedLedgerRow`
    carries the magnitude :class:`~cadrumo.domain.transactions.RawTransaction`
    and the authoritative ``direction`` the provider derived from the source
    sign at the parse boundary; this classifier never re-derives flow from a
    sign. Deduplication keys on
    :func:`~cadrumo.domain.transactions.derive_import_fingerprint` - a direction-
    and currency-qualified identity that is stable across both later edits of a
    transaction and a re-export of the same movement in a different file format.
    The import/skip verdict itself comes from
    :func:`~cadrumo.application.transactions.classify_import_row`, which the
    ``--verify`` diagnostics path consumes too, so the persisting path, the
    ``--dry-run`` preview and the verify report all agree on what a row is.
    """
    existing_fingerprints = {
        fingerprint
        for transaction in catalogue.values()
        for fingerprint in existing_transaction_import_fingerprints(transaction)
    }
    existing_day_keys = {derive_movement_day_key(transaction.raw) for transaction in catalogue.values()}
    imported: list[Transaction] = []
    skipped_refs: list[BucketTransactionRef] = []
    likely_duplicate_refs: list[BucketTransactionRef] = []
    batch_transaction_ids: set[str] = set()
    batch_fingerprints: set[str] = set()
    for parsed in parsed_rows:
        raw = parsed.raw
        fingerprint = derive_import_fingerprint(raw, direction=parsed.direction)
        transaction_id = derive_transaction_id(raw)
        # Re-import dedup keys on the persisted catalogue only: a fingerprint
        # already stored is the same movement seen before (re-importing the same
        # statement, or the same movement re-exported in another file format), so
        # it is skipped. An intra-batch fingerprint collision is NOT a re-import:
        # the provider synthesises a distinct, row-index-bearing transaction id
        # per source row (``synthesize_transaction_id``), so two same-signature
        # rows in ONE statement are two genuine movements (e.g. two identical
        # same-day retainers/subscriptions) carrying collision-free ids — both
        # must import, or the return silently under-declares. The only intra-batch
        # skip is a true content-id collision: two rows resolving to the SAME
        # transaction id cannot both persist (the catalogue keys on that id; the
        # later would overwrite the earlier), so the later is skipped to keep the
        # count honest. That reasoning now lives in `classify_import_row`, which
        # the ``--verify`` diagnostics path consumes too; it used to hold only
        # here, and the diagnostics path reasoned the opposite way.
        verdict = classify_import_row(
            fingerprint=fingerprint,
            transaction_id=transaction_id,
            stored_fingerprints=existing_fingerprints,
            batch_fingerprints=batch_fingerprints,
            batch_transaction_ids=batch_transaction_ids,
        )
        batch_fingerprints.add(fingerprint)
        if not verdict.imports:
            skipped_refs.append(BucketTransactionRef(bucket_id=bucket_id, transaction_id=transaction_id))
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
                "source_jurisdiction": _source_jurisdiction_from_raw_fields(raw.raw_fields),
                "group_label": None,
                # D6: an imported row is freshly created at import time.
                "created_at": stamped_at,
                "modified_at": stamped_at,
            },
        )
        batch_transaction_ids.add(transaction_id)
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

    Each :class:`~cadrumo.adapters.inbound.financial.providers.ParsedLedgerRow`
    carries the magnitude :class:`~cadrumo.domain.transactions.RawTransaction`
    plus the authoritative ``direction`` the provider derived at the parse
    boundary, so the import path never re-derives flow from a sign.

    Returns a :class:`~cadrumo.application.ledger.models.LedgerImportOperationResult`
    summarising the imported, skipped, and likely-duplicate transactions.
    """
    now = normalise_timestamp(occurred_at)
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = resolve_bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
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
        catalogue_path=(
            f"db://secure_objects/{TRANSACTION_CATALOGUE_NAMESPACE.namespace}/transaction-catalogue:{bucket_id}"
        ),
    )
    if not imported_transactions:
        return LedgerImportOperationResult(summary=summary, import_batch_id=import_batch_id)
    events = tuple(
        build_ledger_bucket_event(
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
    save_transaction_catalogue_and_events(
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

    Returns a :class:`~cadrumo.application.ledger.models.LedgerSourceImportResult`.
    """
    # Refuse a missing/unreadable source up front, before provider
    # resolution. With ``--provider auto`` resolution runs the detection
    # probe loop, which would otherwise open a non-existent path through
    # every candidate provider and surface raw parse tracebacks instead of
    # one clean, path-naming refusal.
    _require_readable_source(command.path)
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
        resolve_transaction_repository(bucket_id=command.bucket_id, repository=transaction_repository)
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
            import_fingerprints=tuple(
                derive_import_fingerprint(parsed.raw, direction=parsed.direction) for parsed in parsed_rows
            ),
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
    repository = resolve_transaction_repository(bucket_id=command.bucket_id, repository=repository)
    event_repository = resolve_bucket_event_repository(bucket_id=command.bucket_id, repository=bucket_event_repository)
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
        append_bucket_events(repository=event_repository, events=diagnostic_events)
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
            raise _unsupported_import_source(path)
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
            raise _unsupported_import_source(path)
        return detected
    # PDF and PDF_N26
    return PdfN26Provider()


def _require_readable_source(path: Path) -> None:
    """Refuse a missing or non-regular import source with a typed refusal.

    Naming the path in the refusal lets the operator correct the argument
    without reading a Python traceback, and short-circuiting before
    provider resolution keeps the ``--provider auto`` detection probe loop
    from opening a non-existent path through every candidate provider.
    """
    if not path.exists() or not path.is_file():
        raise TransactionValidationError(
            translated_message="errors.financial.source_file_not_found",
            context={"path": str(path)},
        )


def _validate_import_source(provider: FinancialProviderProtocol, path: Path) -> ProviderValidation:
    _require_readable_source(path)
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
        raise TransactionValidationError(
            translated_message="errors.financial.source_file_not_found",
            context={"path": str(source)},
        )
    return LedgerSourceVerificationReport(requested=True, path=str(resolved), sha256=sha256_file(resolved))


def _unsupported_import_source(path: Path) -> TransactionValidationError:
    """Build the shared translated refusal for sources no provider recognises."""
    return TransactionValidationError(
        translated_message="errors.transaction.ledger_import_failed",
        context={
            "reason": f"{tr('errors.transaction.import_source_invalid')}: {path}",
            "path": str(path),
        },
    )


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
    now = normalise_timestamp(None)
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
                build_ledger_bucket_event(
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
    return sha256_hex(
        canonical_json_bytes(
            {
                "bucket_id": bucket_id,
                "source_command": source_command,
                "imported_transaction_ids": imported_transaction_ids,
            },
        ),
    )


apply_fx_conversion = _apply_fx_conversion

__all__ = [
    "LedgerProviderID",
    "import_ledger_source",
    "import_ledger_transactions",
]
