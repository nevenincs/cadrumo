"""In-memory ledger date partition for application test repositories."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from ...domain.transactions.date_partition import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
)
from ...domain.transactions.dates import transaction_filing_date
from ...domain.transactions.models import Transaction, TransactionCatalogue


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
