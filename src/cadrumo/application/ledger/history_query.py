"""What counts as one ledger transaction's history, and in what order.

Answering that is not transport work. It decides which prior identities anchor
a row's events after an id-affecting edit, whether split siblings belong to the
same story, which of the bucket's event types are history at all, and how
evidence events -- which are anchored elsewhere and reference the transaction
only through their payload -- join the chain. All of it lived in the CLI
adapter, so a second surface showing a transaction's history had no choice but
to reimplement the same four decisions.

The two event-type sets are part of the contract rather than an implementation
detail. History is a curated subset: a bucket carries events that are not this
transaction's story, and widening the set silently turns an audit trail into a
log.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, NonNegativeInt

from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from .actions_common import resolve_bucket_event_repository, resolve_transaction_repository

if TYPE_CHECKING:
    from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
    from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol

#: Events anchored on the transaction identity itself.
LEDGER_HISTORY_EVENT_TYPES: Final[tuple[BucketEventType, ...]] = (
    BucketEventType.LEDGER_TRANSACTION_CREATED,
    BucketEventType.LEDGER_TRANSACTION_IMPORTED,
    BucketEventType.LEDGER_TRANSACTION_UPDATED,
    BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
    BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED,
    BucketEventType.LEDGER_TRANSACTION_ALLOCATED,
    BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
    BucketEventType.LEDGER_TRANSACTION_STASHED,
    BucketEventType.LEDGER_TRANSACTION_RESTORED,
    BucketEventType.LEDGER_TRANSACTION_REMOVED,
    BucketEventType.LEDGER_TRANSACTION_EXPORTED,
    BucketEventType.LEDGER_TRANSACTION_SPLIT,
    BucketEventType.LEDGER_TRANSACTION_MERGED,
    BucketEventType.LEDGER_TRANSACTION_INVOICE_LINKED,
)

#: Evidence events anchored on their own object, naming the transaction only in
#: their payload. They belong to the row's story but cannot be found by
#: object-id lookup, which is why they are collected separately.
LEDGER_EVIDENCE_HISTORY_EVENT_TYPES: Final[tuple[BucketEventType, ...]] = (
    BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
    BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED,
    BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
    BucketEventType.ATTACHMENT_LINKED,
    BucketEventType.ATTACHMENT_REMOVED,
)


class LedgerHistoryQuery(BaseModel):
    """One request for a transaction's chronological event chain."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: str
    include_split_siblings: bool = False


class LedgerHistoryV1(BaseModel):
    """The assembled chain plus the identities it was assembled from.

    ``object_ids`` is returned rather than hidden because it is the answer to
    "why is this event here": an operator looking at events under an id they
    did not ask for is seeing the edit lineage work, not a leak.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: str
    transaction_id: str
    object_ids: tuple[str, ...]
    events: tuple[BucketEvent, ...]
    event_count: NonNegativeInt


def ledger_history_object_ids(
    *,
    transaction_id: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    include_split_siblings: bool = False,
) -> tuple[str, ...]:
    """Return every event-anchor id whose events belong to ``transaction_id``.

    Always the id itself plus every prior id in its edit lineage. An update
    that edits an id-affecting fact anchors the pre-edit events (create,
    import) on the OLD id and everything after on the new one, so walking the
    lineage is what lets an operator holding a superseded id still see the
    whole chain instead of a truncated one.

    Split siblings are a different relationship -- rows that came from the same
    parent, not earlier names for this row -- so they are included only when
    the caller opts in.
    """
    catalogue = transaction_repository.load()
    transaction = catalogue.get(transaction_id)
    object_ids: list[str] = [transaction_id]
    if transaction is not None:
        for entry in transaction.edit_lineage:
            if entry.previous_transaction_id not in object_ids:
                object_ids.append(entry.previous_transaction_id)
    if not include_split_siblings or transaction is None or transaction.split_lineage is None:
        return tuple(object_ids)
    for sibling in transaction.split_lineage.sibling_transaction_ids:
        if sibling not in object_ids:
            object_ids.append(sibling)
    return tuple(object_ids)


def read_ledger_history(
    query: LedgerHistoryQuery,
    *,
    bucket_id: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
) -> LedgerHistoryV1:
    """Assemble one transaction's chronological event chain.

    Args:
        query: The transaction and whether split siblings are included.
        bucket_id: The owning profile bucket.
        transaction_repository: Injected catalogue; resolved when omitted.
        bucket_event_repository: Injected event history; resolved when omitted.

    Returns:
        The chain, ordered by occurrence, with the anchor ids it came from.
    """
    tx_repo = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repo = resolve_bucket_event_repository(bucket_id=bucket_id, repository=bucket_event_repository)
    object_ids = ledger_history_object_ids(
        transaction_id=query.transaction_id,
        transaction_repository=tx_repo,
        include_split_siblings=query.include_split_siblings,
    )
    catalogue = event_repo.load()
    anchored = set(object_ids)

    events: list[BucketEvent] = []
    for object_id in object_ids:
        events.extend(
            event
            for event in catalogue.for_object(
                object_type=BucketEventObjectType.LEDGER_TRANSACTION,
                object_id=object_id,
            )
            if event.event_type in LEDGER_HISTORY_EVENT_TYPES
        )
    events.extend(
        event
        for event in catalogue.values()
        if event.event_type in LEDGER_EVIDENCE_HISTORY_EVENT_TYPES and event.payload.get("transaction_id") in anchored
    )
    events.sort(key=lambda event: event.occurred_at)

    return LedgerHistoryV1(
        bucket_id=bucket_id,
        transaction_id=query.transaction_id,
        object_ids=object_ids,
        events=tuple(events),
        event_count=len(events),
    )


__all__ = [
    "LEDGER_EVIDENCE_HISTORY_EVENT_TYPES",
    "LEDGER_HISTORY_EVENT_TYPES",
    "LedgerHistoryQuery",
    "LedgerHistoryV1",
    "ledger_history_object_ids",
    "read_ledger_history",
]
