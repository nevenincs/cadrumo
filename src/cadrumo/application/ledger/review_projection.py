"""Review-row projection and filtering for bucket ledger transactions.

Review rows are filtered from a loaded :class:`TransactionCatalogue`;
:class:`BucketEventHistoryRepository` supplies event-derived review context.
The public projection returns
:class:`~cadrumo.application.ledger.models.LedgerReviewQueryResult` for a
:class:`~cadrumo.application.ledger.models.LedgerReviewQuery`.
"""

from __future__ import annotations

from collections.abc import Callable

from ...core.period import Period
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ...domain.transactions.enums import BusinessClassification
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ..review.filter import LedgerReviewStatus
from .actions_common import display_decimal, require_transaction
from .models import LedgerReviewQuery, LedgerReviewQueryResult, LedgerReviewRow, LedgerTransactionPayload
from .protocols import BucketEventHistoryCoCommitWriterProtocol


def project_ledger_review_query(
    query: LedgerReviewQuery,
    *,
    catalogue: TransactionCatalogue,
    bucket_event_repository: BucketEventHistoryCoCommitWriterProtocol,
    transaction_payload_builder: Callable[[Transaction], LedgerTransactionPayload],
) -> LedgerReviewQueryResult:
    """Return a :class:`~cadrumo.application.ledger.models.LedgerReviewQueryResult`.

    The supplied :class:`TransactionCatalogue` provides the row set and lookup
    context for period, status, and classification filters.
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
    """Return the :class:`~cadrumo.application.review.LedgerReviewStatus` for one bucket-local transaction fact."""
    if transaction.business_classification is BusinessClassification.SKIPPED_BY_RULE:
        return LedgerReviewStatus.SKIPPED
    if transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED:
        return LedgerReviewStatus.EXCLUDED
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
    bucket_event_repository: BucketEventHistoryCoCommitWriterProtocol,
) -> tuple[Transaction, ...]:
    rows = _filter_review_rows_by_period(rows, query.period)
    rows = _filter_review_rows_by_status(rows, query.status)
    rows = _filter_review_rows_by_classification(rows, query.classification)
    rows = _filter_review_rows_by_direction(rows, query.direction)
    rows = _filter_review_rows_by_text(rows, query.text)
    rows = _filter_review_rows_by_event(
        rows,
        bucket_id=query.bucket_id,
        import_id=query.import_id,
        issue=query.issue,
        bucket_event_repository=bucket_event_repository,
    )
    return _filter_review_rows_by_transaction_id(rows, query.transaction_id, catalogue)


def _apply_review_row_filter(
    rows: tuple[Transaction, ...],
    predicate: Callable[[Transaction], bool],
) -> tuple[Transaction, ...]:
    """Apply one review predicate while retaining catalogue order."""
    return tuple(transaction for transaction in rows if predicate(transaction))


def _filter_review_rows_by_period(
    rows: tuple[Transaction, ...],
    period: Period | None,
) -> tuple[Transaction, ...]:
    if period is None:
        return rows
    return _apply_review_row_filter(
        rows,
        lambda transaction: period.contains(transaction.raw.value_date or transaction.raw.booked_date),
    )


def _filter_review_rows_by_status(
    rows: tuple[Transaction, ...],
    status: str | None,
) -> tuple[Transaction, ...]:
    if status is None:
        return rows
    return _apply_review_row_filter(rows, lambda transaction: ledger_transaction_review_status(transaction) == status)


def _filter_review_rows_by_classification(
    rows: tuple[Transaction, ...],
    classification: str | None,
) -> tuple[Transaction, ...]:
    if classification is None:
        return rows
    return _apply_review_row_filter(
        rows,
        lambda transaction: transaction.business_classification.value == classification,
    )


def _filter_review_rows_by_direction(
    rows: tuple[Transaction, ...],
    direction: str | None,
) -> tuple[Transaction, ...]:
    if direction is None:
        return rows
    return _apply_review_row_filter(rows, lambda transaction: transaction.direction.value == direction)


def _filter_review_rows_by_text(
    rows: tuple[Transaction, ...],
    text: str | None,
) -> tuple[Transaction, ...]:
    if text is None:
        return rows
    needle = text.casefold()
    return _apply_review_row_filter(rows, lambda transaction: _review_row_contains_text(transaction, needle))


def _review_row_contains_text(transaction: Transaction, needle: str) -> bool:
    """Return whether *needle* occurs in searchable review-row fields."""
    return (
        needle in transaction.raw.description.casefold()
        or needle in transaction.raw.display_counterparty.casefold()
        or needle in (transaction.category_id or "").casefold()
    )


def _filter_review_rows_by_event(
    rows: tuple[Transaction, ...],
    *,
    bucket_id: str,
    import_id: str | None,
    issue: str | None,
    bucket_event_repository: BucketEventHistoryCoCommitWriterProtocol,
) -> tuple[Transaction, ...]:
    if import_id is None and issue is None:
        return rows
    matching_ids = _transaction_ids_for_review_event_filters(
        bucket_id=bucket_id,
        import_id=import_id,
        issue=issue,
        bucket_event_repository=bucket_event_repository,
    )
    return _apply_review_row_filter(rows, lambda transaction: transaction.transaction_id in matching_ids)


def _filter_review_rows_by_transaction_id(
    rows: tuple[Transaction, ...],
    transaction_id: str | None,
    catalogue: TransactionCatalogue,
) -> tuple[Transaction, ...]:
    if transaction_id is None:
        return rows
    require_transaction(catalogue, transaction_id)
    return _apply_review_row_filter(rows, lambda transaction: transaction.transaction_id == transaction_id)


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
        "amount": display_decimal(transaction.raw.amount),
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
    bucket_event_repository: BucketEventHistoryCoCommitWriterProtocol,
) -> frozenset[str]:
    events = bucket_event_repository.load().for_bucket(
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


__all__ = [
    "ledger_transaction_review_status",
]
