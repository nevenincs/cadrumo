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

from typing import TYPE_CHECKING, Final

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

    def __eq__(self, other: object) -> bool:
        """Compare only against another reversed key."""
        return isinstance(other, _DescendingKey) and other.value == self.value

    def __hash__(self) -> int:
        """Hash by the wrapped value so equal keys agree."""
        return hash(self.value)


def _sort_field_value(transaction: Transaction, field: LedgerSortField) -> str:
    """Project one sort axis to a string so ordering can never raise.

    Every axis becomes a ``str`` so a sort never compares mixed types, and an
    optional axis with no value yields the empty string; the caller pairs that
    with a *missing* flag so a blank never sorts as though it held a value.
    """
    raw = transaction.raw
    if field is LedgerSortField.DATE:
        return (raw.value_date or raw.booked_date).isoformat()
    if field is LedgerSortField.VALUE_DATE:
        return raw.value_date.isoformat() if raw.value_date is not None else ""
    if field is LedgerSortField.AMOUNT:
        # Zero-pad the integer part so lexical order matches numeric order over
        # the non-negative magnitudes (e.g. "9.00" must sort before "10.00").
        return f"{raw.amount:020.2f}"
    if field is LedgerSortField.DESCRIPTION:
        return raw.description
    if field is LedgerSortField.CREATED_AT:
        return transaction.created_at.isoformat()
    if field is LedgerSortField.MODIFIED_AT:
        return transaction.modified_at.isoformat()
    if field is LedgerSortField.CLASSIFIED_AT:
        return transaction.classified_at.isoformat() if transaction.classified_at is not None else ""
    if field is LedgerSortField.LIFECYCLE_STATE:
        return transaction.lifecycle_state.value
    return transaction.business_classification.value


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
    if query.spec.clauses:
        matching = query_ledger_review_rows(
            ledger_review_query_for_spec(query.spec, bucket_id=bucket_id),
            transaction_repository=transaction_repository,
        )
        matching_ids = {row.id for row in matching.rows}
        results = tuple(item for item in results if item.transaction.transaction_id in matching_ids)
    if query.exclude_llm_rejected:
        if bucket_event_repository is None:
            raise ValueError("excluding model-rejected rows requires the bucket event history repository")
        catalogue = bucket_event_repository.load()
        results = tuple(
            item for item in results if not latest_llm_decision_is_rejection(catalogue, item.transaction.transaction_id)
        )
    if query.group is not None:
        wanted = query.group.strip() or None
        results = tuple(item for item in results if item.transaction.group_label == wanted)
    if query.sort_by is not None:
        results = sort_ledger_results(results, sort_by=query.sort_by, sort_order=query.sort_order)
    if query.by_group:
        results = tuple(
            sorted(
                results,
                key=lambda item: (
                    item.transaction.group_label or _UNGROUPED_SENTINEL,
                    # Only the residual tie-break when no axis was chosen;
                    # otherwise the stable sort above already holds the order.
                    item.transaction.transaction_id if query.sort_by is None else "",
                ),
            )
        )

    total = len(results)
    window_end = total if query.limit is None else min(query.offset + query.limit, total)
    return LedgerTransactionListPageV1(
        bucket_id=bucket_id,
        results=results[query.offset : window_end],
        total=total,
        truncated=query.offset > 0 or window_end < total,
    )


__all__ = [
    "LLM_DECISION_EVENT_TYPES",
    "LedgerTransactionListPageV1",
    "LedgerTransactionListQuery",
    "latest_llm_decision_is_rejection",
    "query_ledger_transaction_list",
    "sort_ledger_results",
]
