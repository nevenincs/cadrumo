"""The canonical selection semantics behind one Ledger transaction listing.

Filtering, group selection, sort order, and paging decide WHICH ledger rows an
operator is shown and in what order. That is query policy over stored facts, so
it belongs beside the other Ledger use cases rather than inside whichever
frontend happens to ask: the CLI adapter owned all of it, which left the TUI
with no way to list transactions except by reproducing the same rules a second
time.

The split this module draws is between selecting rows and rendering them. The
page it returns carries canonical application results plus the two facts a
caller needs to describe the window truthfully -- the unfiltered total and
whether the window omits anything -- and nothing about columns, labels, or
line formatting, which stay with the surface that displays them.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Final, override

from pydantic import BaseModel, NonNegativeInt

from ...core.ledger_sort import LedgerSortField, LedgerSortOrder
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ..review.filter import LedgerReviewFilterSpec
from .actions_manual import list_manual_transactions, query_ledger_review_rows
from .models import ManualLedgerTransactionResult
from .review_filter import ledger_review_query_for_spec

if TYPE_CHECKING:
    from ...domain.buckets.event import BucketEventHistoryCatalogue
    from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
    from ...domain.transactions.models import Transaction
    from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol

#: Sorts after every real group label, so ungrouped rows trail named groups.
_UNGROUPED_SENTINEL: Final[str] = "￿"

#: The two terminal model decisions on a row: an accepted (applied)
#: classification, or a rejection. The most recent of the two is the standing
#: decision. One home, so a surface reading it cannot drift from another.
LLM_DECISION_EVENT_TYPES: Final = (
    BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
    BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED,
)


class LedgerTransactionListQuery(BaseModel):
    """One operator-intent request for a window over the stored ledger."""

    model_config = STRICT_FROZEN_CONFIG

    spec: LedgerReviewFilterSpec
    group: str | None = None
    by_group: bool = False
    limit: int | None = None
    offset: NonNegativeInt = 0
    sort_by: LedgerSortField | None = None
    sort_order: LedgerSortOrder = LedgerSortOrder.ASC
    exclude_llm_rejected: bool = False


class LedgerTransactionListPageV1(BaseModel):
    """The selected window plus the facts needed to describe it honestly.

    ``total`` counts every row that survived filtering, not the window, so a
    caller can say how much it is not showing. ``truncated`` is that judgement
    already made, covering both a window that starts past the first row and one
    that ends before the last.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: str
    results: tuple[ManualLedgerTransactionResult, ...]
    total: NonNegativeInt
    truncated: bool


class _DescendingKey:
    """A string whose ordering is reversed, so one composite key can mix axes.

    Descending order on the primary axis has to coexist with an ascending
    ``transaction_id`` tie-break in the same tuple. Reversing the comparison on
    this wrapper alone expresses that without sorting twice.
    """

    __slots__ = ("value",)

    def __init__(self, value: str) -> None:
        """Retain the value whose comparison this wrapper inverts."""
        self.value = value

    def __lt__(self, other: _DescendingKey) -> bool:
        """Invert the natural ordering."""
        return other.value < self.value

    @override
    def __eq__(self, other: object) -> bool:
        """Compare only against another reversed key."""
        return isinstance(other, _DescendingKey) and other.value == self.value

    @override
    def __hash__(self) -> int:
        """Hash by the wrapped value so equal keys agree."""
        return hash(self.value)


def _effective_date_sort_value(transaction: Transaction) -> str:
    """Project the effective ledger date used by the default date axis."""
    raw = transaction.raw
    return (raw.value_date or raw.booked_date).isoformat()


def _value_date_sort_value(transaction: Transaction) -> str:
    """Project the optional raw value date, leaving absence sortable last."""
    value_date = transaction.raw.value_date
    return value_date.isoformat() if value_date is not None else ""


def _amount_sort_value(transaction: Transaction) -> str:
    """Project a zero-padded amount so lexical order matches numeric order."""
    # Zero-pad the integer part so lexical order matches numeric order over
    # the non-negative magnitudes (e.g. "9.00" must sort before "10.00").
    return f"{transaction.raw.amount:020.2f}"


def _description_sort_value(transaction: Transaction) -> str:
    """Project the operator-facing description axis."""
    return transaction.raw.description


def _created_at_sort_value(transaction: Transaction) -> str:
    """Project the persistence creation timestamp axis."""
    return transaction.created_at.isoformat()


def _modified_at_sort_value(transaction: Transaction) -> str:
    """Project the persistence modification timestamp axis."""
    return transaction.modified_at.isoformat()


def _classified_at_sort_value(transaction: Transaction) -> str:
    """Project the optional classification timestamp axis."""
    return transaction.classified_at.isoformat() if transaction.classified_at is not None else ""


def _lifecycle_state_sort_value(transaction: Transaction) -> str:
    """Project the lifecycle-state token axis."""
    return transaction.lifecycle_state.value


def _classification_sort_value(transaction: Transaction) -> str:
    """Project the business-classification token axis."""
    return transaction.business_classification.value


_SORT_FIELD_PROJECTORS: Final[dict[LedgerSortField, Callable[[Transaction], str]]] = {
    LedgerSortField.DATE: _effective_date_sort_value,
    LedgerSortField.VALUE_DATE: _value_date_sort_value,
    LedgerSortField.AMOUNT: _amount_sort_value,
    LedgerSortField.DESCRIPTION: _description_sort_value,
    LedgerSortField.CREATED_AT: _created_at_sort_value,
    LedgerSortField.MODIFIED_AT: _modified_at_sort_value,
    LedgerSortField.CLASSIFIED_AT: _classified_at_sort_value,
    LedgerSortField.LIFECYCLE_STATE: _lifecycle_state_sort_value,
    LedgerSortField.CLASSIFICATION: _classification_sort_value,
}


def _sort_field_value(transaction: Transaction, field: LedgerSortField) -> str:
    """Project one sort axis to a string so ordering can never raise."""
    return _SORT_FIELD_PROJECTORS.get(field, _classification_sort_value)(transaction)


def sort_ledger_results(
    results: tuple[ManualLedgerTransactionResult, ...],
    *,
    sort_by: LedgerSortField,
    sort_order: LedgerSortOrder,
) -> tuple[ManualLedgerTransactionResult, ...]:
    """Stably order ``results`` on one axis, tie-broken by transaction id.

    The composite key is ``(missing, primary, transaction_id)``: a row with no
    value on the axis always sorts last regardless of direction, and the
    content-addressed id makes the order deterministic between equal rows.
    """
    descending = sort_order is LedgerSortOrder.DESC

    def composite_key(result: ManualLedgerTransactionResult) -> tuple[bool, object, str]:
        value = _sort_field_value(result.transaction, sort_by)
        primary: object = _DescendingKey(value) if descending else value
        return (not value, primary, result.transaction.transaction_id)

    return tuple(sorted(results, key=composite_key))


def latest_llm_decision_is_rejection(
    event_catalogue: BucketEventHistoryCatalogue,
    transaction_id: str,
) -> bool:
    """Report whether this transaction's most recent model decision was a rejection.

    Reads the event history only and never consults ``review_status``: a
    rejection is a decision that was made, which the current status cannot
    distinguish from a row that was never assessed.
    """
    decisions = [
        event
        for event in event_catalogue.for_object(
            object_type=BucketEventObjectType.LEDGER_TRANSACTION,
            object_id=transaction_id,
        )
        if event.event_type in LLM_DECISION_EVENT_TYPES
    ]
    if not decisions:
        return False
    decisions.sort(key=lambda event: event.occurred_at)
    return decisions[-1].event_type is BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED


def _filter_by_review_spec(
    results: tuple[ManualLedgerTransactionResult, ...],
    *,
    query: LedgerTransactionListQuery,
    bucket_id: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None,
) -> tuple[ManualLedgerTransactionResult, ...]:
    """Apply the canonical review-filter projection when clauses are present."""
    if not query.spec.clauses:
        return results
    matching = query_ledger_review_rows(
        ledger_review_query_for_spec(query.spec, bucket_id=bucket_id),
        transaction_repository=transaction_repository,
    )
    matching_ids = {row.id for row in matching.rows}
    return tuple(item for item in results if item.transaction.transaction_id in matching_ids)


def _exclude_rejected_results(
    results: tuple[ManualLedgerTransactionResult, ...],
    *,
    query: LedgerTransactionListQuery,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None,
) -> tuple[ManualLedgerTransactionResult, ...]:
    """Drop rows whose latest model decision is a rejection when requested."""
    if not query.exclude_llm_rejected:
        return results
    if bucket_event_repository is None:
        raise ValueError("excluding model-rejected rows requires the bucket event history repository")
    catalogue = bucket_event_repository.load()
    return tuple(
        item for item in results if not latest_llm_decision_is_rejection(catalogue, item.transaction.transaction_id)
    )


def _filter_by_group(
    results: tuple[ManualLedgerTransactionResult, ...],
    *,
    group: str | None,
) -> tuple[ManualLedgerTransactionResult, ...]:
    """Keep only the requested normalized group label."""
    if group is None:
        return results
    wanted = group.strip() or None
    return tuple(item for item in results if item.transaction.group_label == wanted)


def _sort_if_requested(
    results: tuple[ManualLedgerTransactionResult, ...],
    *,
    sort_by: LedgerSortField | None,
    sort_order: LedgerSortOrder,
) -> tuple[ManualLedgerTransactionResult, ...]:
    """Apply the requested primary sort while retaining the stored order otherwise."""
    if sort_by is None:
        return results
    return sort_ledger_results(results, sort_by=sort_by, sort_order=sort_order)


def _partition_by_group(
    results: tuple[ManualLedgerTransactionResult, ...],
    *,
    by_group: bool,
    sort_by: LedgerSortField | None,
) -> tuple[ManualLedgerTransactionResult, ...]:
    """Partition named groups before ungrouped rows without changing their order."""
    if not by_group:
        return results
    return tuple(
        sorted(
            results,
            key=lambda item: (
                item.transaction.group_label or _UNGROUPED_SENTINEL,
                # Only the residual tie-break when no axis was chosen;
                # otherwise the stable sort above already holds the order.
                item.transaction.transaction_id if sort_by is None else "",
            ),
        )
    )


def _page_results(
    results: tuple[ManualLedgerTransactionResult, ...],
    *,
    bucket_id: str,
    limit: int | None,
    offset: int,
) -> LedgerTransactionListPageV1:
    """Build the truthful unpaged total and requested result window."""
    total = len(results)
    window_end = total if limit is None else min(offset + limit, total)
    return LedgerTransactionListPageV1(
        bucket_id=bucket_id,
        results=results[offset:window_end],
        total=total,
        truncated=offset > 0 or window_end < total,
    )


def query_ledger_transaction_list(
    query: LedgerTransactionListQuery,
    *,
    bucket_id: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
) -> LedgerTransactionListPageV1:
    """Select, order, and page one window over a bucket's stored transactions.

    Order of operations is part of the contract: filter, then group selection,
    then sort, then group partitioning, then paging. Sorting before paging is
    what makes a page mean the same thing to every caller, and partitioning
    after sorting keeps the chosen order inside each group block.

    Args:
        query: The operator's selection intent.
        bucket_id: The owning profile bucket.
        transaction_repository: Injected transaction catalogue; resolved from
            ``bucket_id`` when omitted.
        bucket_event_repository: Injected event history, required only when
            ``exclude_llm_rejected`` is set.

    Returns:
        The selected window with its unfiltered total and truncation flag.

    Raises:
        ValueError: If model-rejection exclusion is requested without an event
            repository to read the decisions from.
    """
    results = list_manual_transactions(bucket_id=bucket_id, transaction_repository=transaction_repository)
    results = _filter_by_review_spec(
        results,
        query=query,
        bucket_id=bucket_id,
        transaction_repository=transaction_repository,
    )
    results = _exclude_rejected_results(
        results,
        query=query,
        bucket_event_repository=bucket_event_repository,
    )
    results = _filter_by_group(results, group=query.group)
    results = _sort_if_requested(
        results,
        sort_by=query.sort_by,
        sort_order=query.sort_order,
    )
    results = _partition_by_group(
        results,
        by_group=query.by_group,
        sort_by=query.sort_by,
    )
    return _page_results(
        results,
        bucket_id=bucket_id,
        limit=query.limit,
        offset=query.offset,
    )


__all__ = [
    "LLM_DECISION_EVENT_TYPES",
    "LedgerTransactionListPageV1",
    "LedgerTransactionListQuery",
    "latest_llm_decision_is_rejection",
    "query_ledger_transaction_list",
    "sort_ledger_results",
]
