"""Review-row projection and filtering for bucket ledger transactions.

Use of :class:`BucketEventHistoryRepository`, :class:`TransactionCatalogue` for compliance.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from ...domain.buckets import BucketEventHistoryRepository, BucketEventObjectType, BucketEventType
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.transactions import (
    TX_BUCKET_NAMESPACE,
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionNotFoundError,
)
from ..review import LedgerReviewStatus
from ._models import LedgerReviewQuery, LedgerReviewQueryResult, LedgerReviewRow, LedgerTransactionPayload


def project_ledger_review_query(
    query: LedgerReviewQuery,
    *,
    catalogue: TransactionCatalogue,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None,
    transaction_payload_builder: Callable[[Transaction], LedgerTransactionPayload],
) -> LedgerReviewQueryResult:
    """Return a :class:`LedgerReviewQueryResult` for the already loaded transaction catalogue.

    Uses :class:`TransactionCatalogue` for filtering.
    """
    rows = _filter_ledger_review_rows(
        rows=tuple(catalogue.values()),
        query=query,
        catalogue=catalogue,
        bucket_event_repository=bucket_event_repository,
    )
    sorted_rows = sorted(
        rows,
        key=lambda transaction: (
            transaction.raw.value_date or transaction.raw.booked_date,
            transaction.transaction_id,
        ),
    )
    return LedgerReviewQueryResult(
        bucket_id=query.bucket_id,
        rows=tuple(
            _ledger_review_row(
                transaction,
                include_transaction=query.transaction_id is not None,
                transaction_payload_builder=transaction_payload_builder,
            )
            for transaction in sorted_rows
        ),
        filters=_ledger_review_filter_labels(query),
    )


def ledger_transaction_review_status(transaction: Transaction) -> LedgerReviewStatus:
    """Return the :class:`LedgerReviewStatus` for one bucket-local transaction fact."""
    if transaction.business_classification is BusinessClassification.SKIPPED_BY_RULE:
        return LedgerReviewStatus.SKIPPED
    if transaction.business_classification in {
        BusinessClassification.BUSINESS,
        BusinessClassification.PERSONAL,
        BusinessClassification.MIXED,
    }:
        return LedgerReviewStatus.REVIEWED
    return LedgerReviewStatus.PENDING


def _filter_ledger_review_rows(
    *,
    rows: tuple[Transaction, ...],
    query: LedgerReviewQuery,
    catalogue: TransactionCatalogue,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None,
) -> tuple[Transaction, ...]:
    if query.period is not None:
        rows = tuple(
            transaction
            for transaction in rows
            if query.period.contains(transaction.raw.value_date or transaction.raw.booked_date)
        )
    if query.status is not None:
        rows = tuple(
            transaction for transaction in rows if ledger_transaction_review_status(transaction) == query.status
        )
    if query.classification is not None:
        rows = tuple(
            transaction for transaction in rows if transaction.business_classification.value == query.classification
        )
    if query.direction is not None:
        rows = tuple(transaction for transaction in rows if transaction.direction.value == query.direction)
    if query.text is not None:
        needle = query.text.casefold()
        rows = tuple(
            transaction
            for transaction in rows
            if needle in transaction.raw.description.casefold()
            or needle in transaction.raw.display_counterparty.casefold()
            or needle in (transaction.category_id or "").casefold()
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
        _require_transaction(catalogue, query.transaction_id)
        rows = tuple(transaction for transaction in rows if transaction.transaction_id == query.transaction_id)
    return rows


_LEDGER_REVIEW_FILTER_FIELDS: tuple[tuple[str, str], ...] = (
    ("period", "period"),
    ("status", "status"),
    ("issue", "issue"),
    ("import_id", "import"),
    ("classification", "classification"),
    ("text", "text"),
    ("direction", "direction"),
    ("transaction_id", "id"),
)


def _ledger_review_filter_labels(query: LedgerReviewQuery) -> tuple[str, ...]:
    return tuple(
        f"{label}={getattr(query, attr)}"
        for attr, label in _LEDGER_REVIEW_FILTER_FIELDS
        if getattr(query, attr) is not None
    )


def _ledger_review_row(
    transaction: Transaction,
    *,
    include_transaction: bool,
    transaction_payload_builder: Callable[[Transaction], LedgerTransactionPayload],
) -> LedgerReviewRow:
    effective_date = (transaction.raw.value_date or transaction.raw.booked_date).isoformat()
    row: dict[str, object] = {
        "id": transaction.transaction_id,
        "date": effective_date,
        "amount": _display_decimal(transaction.raw.amount),
        "description": transaction.raw.description,
        "status": ledger_transaction_review_status(transaction),
    }
    if include_transaction:
        row["transaction"] = transaction_payload_builder(transaction)
    return LedgerReviewRow.model_validate(row)


def _transaction_ids_for_review_event_filters(
    *,
    bucket_id: str,
    import_id: str | None,
    issue: str | None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None,
) -> frozenset[str]:
    event_repository = _bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
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


def _bucket_event_repository(
    *,
    bucket_id: str,
    repository: BucketEventHistoryRepositoryProtocol | None,
) -> BucketEventHistoryRepositoryProtocol:
    if repository is not None:
        return repository
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

    return BucketEventHistoryRepository(objects=secure_object_repository_for_bucket(bucket_id))


def _require_transaction(catalogue: TransactionCatalogue, transaction_id: str) -> Transaction:
    transaction = catalogue.get(transaction_id)
    if transaction is None:
        raise TransactionNotFoundError(
            f"transaction not found: {transaction_id}",
            context={"namespace": TX_BUCKET_NAMESPACE, "transaction_id": transaction_id},
        )
    return transaction


def _display_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")
