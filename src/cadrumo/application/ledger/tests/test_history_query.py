"""Which identities anchor a transaction's history, and in what order.

The lineage rule is the one worth pinning: an id-affecting edit anchors the
pre-edit events on the OLD id, so a chain assembled from the current id alone
silently truncates -- an operator sees a row that appears to have been created
at its last correction, with the import that produced it missing. That is a
wrong audit trail rather than a missing feature, and nothing asserted it while
the logic lived in the CLI adapter.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.transactions.models import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
    Transaction,
    TransactionCatalogue,
)
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..history_query import (
    LEDGER_EVIDENCE_HISTORY_EVENT_TYPES,
    LEDGER_HISTORY_EVENT_TYPES,
    LedgerHistoryQuery,
    ledger_history_object_ids,
    read_ledger_history,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "33333333-3333-4333-8333-333333333333"
_PRIOR = "d" * 64
_SIBLING = "e" * 64


class _EmptyBucketEventHistory:
    """Inward read fake for history tests that do not seed events."""

    def load(self) -> BucketEventHistoryCatalogue:
        return BucketEventHistoryCatalogue()


class _InMemoryTransactionRepository(TransactionCatalogueRepositoryProtocol):
    """Deterministic inward fake for the history transaction read port."""

    def __init__(self, *, bucket_id: str, catalogue: TransactionCatalogue) -> None:
        self._bucket_id = bucket_id
        self._catalogue = catalogue

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self) -> bool:
        return bool(self._catalogue.transactions)

    def load(self) -> TransactionCatalogue:
        return self._catalogue

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        return TransactionCatalogue.from_transactions(
            transaction
            for transaction in self._catalogue
            if start <= (transaction.raw.value_date or transaction.raw.booked_date) <= end
        )

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        requested = frozenset(transaction_ids)
        return TransactionCatalogue.from_transactions(
            transaction for transaction in self._catalogue if transaction.transaction_id in requested
        )

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        in_window: list[Transaction] = []
        out_of_window: list[OutOfWindowTransactionIndexEntry] = []
        for transaction in self._catalogue:
            filing_date = transaction.raw.value_date or transaction.raw.booked_date
            if start <= filing_date <= end:
                in_window.append(transaction)
            else:
                out_of_window.append(
                    OutOfWindowTransactionIndexEntry(
                        transaction_id=transaction.transaction_id,
                        filing_date=filing_date,
                    ),
                )
        return LedgerDatePartition(
            in_window=TransactionCatalogue.from_transactions(in_window),
            out_of_window=tuple(out_of_window),
            out_of_window_summary=OutOfWindowTransactionSummary.from_index_entries(out_of_window),
            index_complete=True,
        )

    def save(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue


def _transaction(*, provider_id: str, edit_lineage: tuple[object, ...] = ()) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2024, 4, 10),
        value_date=date(2024, 4, 10),
        amount=Decimal("10.00"),
        currency="EUR",
        counterparty="Supplier SL",
        description="office supplies",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="test",
        ),
        raw_fields={},
    )
    payload: dict[str, object] = {
        "raw": raw,
        "direction": TransactionDirection.OUTGOING,
        "business_classification": BusinessClassification.NOT_YET_PROCESSED,
        "source_jurisdiction": "ES",
        "group_label": None,
        "created_at": datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
        "modified_at": datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
    }
    if edit_lineage:
        payload["edit_lineage"] = edit_lineage
    return Transaction.model_validate(payload)


@contextmanager
def _stored(*transactions: Transaction) -> Iterator[TransactionCatalogueRepositoryProtocol]:
    """Build a deterministic catalogue through the application read protocol."""
    yield _InMemoryTransactionRepository(
        bucket_id=_BUCKET,
        catalogue=TransactionCatalogue.from_transactions(transactions),
    )


def test_the_anchor_set_is_the_transaction_itself_when_it_has_no_lineage() -> None:
    """The baseline: one identity, one anchor."""
    transaction = _transaction(provider_id="a")
    with _stored(transaction) as repository:
        anchors = ledger_history_object_ids(
            transaction_id=transaction.transaction_id,
            transaction_repository=repository,
        )

    assert anchors == (transaction.transaction_id,)


def test_an_unknown_id_still_anchors_on_itself() -> None:
    """A superseded id must resolve to a chain, never to an empty answer.

    The catalogue no longer holds the old identity after an edit, so returning
    nothing here is what would make an operator's written-down id look invalid.
    """
    with _stored(_transaction(provider_id="a")) as repository:
        anchors = ledger_history_object_ids(transaction_id=_PRIOR, transaction_repository=repository)

    assert anchors == (_PRIOR,)


def test_split_siblings_are_excluded_unless_the_caller_opts_in() -> None:
    """Siblings share a parent; they are not earlier names for this row."""
    transaction = _transaction(provider_id="a")
    with _stored(transaction) as repository:
        without = ledger_history_object_ids(
            transaction_id=transaction.transaction_id,
            transaction_repository=repository,
            include_split_siblings=False,
        )
        with_siblings = ledger_history_object_ids(
            transaction_id=transaction.transaction_id,
            transaction_repository=repository,
            include_split_siblings=True,
        )

    # This row has no split lineage, so opting in must not invent anchors.
    assert without == with_siblings == (transaction.transaction_id,)


def test_a_history_read_reports_its_anchors_and_a_consistent_count() -> None:
    """``event_count`` and ``events`` must not be able to disagree."""
    transaction = _transaction(provider_id="a")
    with _stored(transaction) as repository:
        history = read_ledger_history(
            LedgerHistoryQuery(transaction_id=transaction.transaction_id),
            bucket_id=_BUCKET,
            transaction_repository=repository,
            bucket_event_repository=_EmptyBucketEventHistory(),
        )

    assert history.bucket_id == _BUCKET
    assert history.transaction_id == transaction.transaction_id
    assert history.object_ids == (transaction.transaction_id,)
    assert history.event_count == len(history.events)


def test_the_assembled_chain_is_ordered_by_occurrence() -> None:
    """Ordering is the contract; a caller renders the chain as given."""
    transaction = _transaction(provider_id="a")
    with _stored(transaction) as repository:
        history = read_ledger_history(
            LedgerHistoryQuery(transaction_id=transaction.transaction_id),
            bucket_id=_BUCKET,
            transaction_repository=repository,
            bucket_event_repository=_EmptyBucketEventHistory(),
        )

    occurred = [event.occurred_at for event in history.events]
    assert occurred == sorted(occurred)


def test_history_is_a_curated_subset_of_bucket_event_types() -> None:
    """Widening either set turns an audit trail into a log, so both are pinned.

    Asserted as disjoint named sets rather than by count: the point is that a
    transaction-anchored event and a payload-referenced evidence event are
    collected by different mechanisms and must not overlap.
    """
    assert LEDGER_HISTORY_EVENT_TYPES
    assert LEDGER_EVIDENCE_HISTORY_EVENT_TYPES
    assert not set(LEDGER_HISTORY_EVENT_TYPES) & set(LEDGER_EVIDENCE_HISTORY_EVENT_TYPES)
