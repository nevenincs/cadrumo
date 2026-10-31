"""In-memory ledger date partition for application test repositories."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import override

from ...domain.transactions.date_partition import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
)
from ...domain.transactions.dates import transaction_filing_date
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol


def partition_by_filing_date(transactions: Iterable[Transaction], start: date, end: date) -> LedgerDatePartition:
    """Split ``transactions`` by ledger filing date the way the persisted repository does."""
    in_window: list[Transaction] = []
    out_of_window: list[OutOfWindowTransactionIndexEntry] = []
    for transaction in transactions:
        filing_date = transaction_filing_date(transaction)
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


class CatalogueTransactionRepository(TransactionCatalogueRepositoryProtocol):
    """Inward fake for the transaction catalogue port, holding one catalogue in memory."""

    def __init__(self, *, bucket_id: str, catalogue: TransactionCatalogue) -> None:
        self._bucket_id = bucket_id
        self._catalogue = catalogue

    @property
    @override
    def bucket_id(self) -> str:
        return self._bucket_id

    @override
    def exists(self) -> bool:
        return bool(self._catalogue.transactions)

    @override
    def load(self) -> TransactionCatalogue:
        return self._catalogue

    @override
    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        return TransactionCatalogue.from_transactions(
            transaction
            for transaction in self._catalogue
            if start <= (transaction.raw.value_date or transaction.raw.booked_date) <= end
        )

    @override
    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        requested = frozenset(transaction_ids)
        return TransactionCatalogue.from_transactions(
            transaction for transaction in self._catalogue if transaction.transaction_id in requested
        )

    @override
    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        return partition_by_filing_date(self._catalogue, start, end)

    @override
    def save(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue
