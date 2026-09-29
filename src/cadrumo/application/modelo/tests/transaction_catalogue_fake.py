"""Inward ledger store over real transaction records, for verify-path tests.

Holds real :class:`~cadrumo.domain.transactions.models.Transaction` records and
answers ``load_for_date_range`` by the same filing date the protocol defines --
``value_date`` when the row carries one, else ``booked_date`` -- so a test that
depends on the window depends on the window the production repository applies.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from ....domain.transactions.dates import transaction_filing_date
from ....domain.transactions.models import LedgerDatePartition, Transaction, TransactionCatalogue

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["TransactionCatalogueFake"]


class TransactionCatalogueFake:
    """Protocol-conforming ledger store over real transaction records."""

    def __init__(self, *transactions: Transaction, bucket_id: str = "bucket") -> None:
        """Hold ``transactions`` as the persisted catalogue for ``bucket_id``."""
        self._catalogue = TransactionCatalogue.model_validate(
            {"transactions": {transaction.transaction_id: transaction for transaction in transactions}},
        )
        self._bucket_id = bucket_id

    @property
    def bucket_id(self) -> str:
        """Return the bucket this store answers for."""
        return self._bucket_id

    def exists(self) -> bool:
        """Report whether a catalogue has been persisted."""
        return bool(self._catalogue.transactions)

    def load(self) -> TransactionCatalogue:
        """Return the held catalogue."""
        return self._catalogue

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        """Return the held rows whose filing date falls inside ``[start, end]``."""
        return TransactionCatalogue.model_validate(
            {
                "transactions": {
                    transaction_id: transaction
                    for transaction_id, transaction in self._catalogue.transactions.items()
                    if start <= transaction_filing_date(transaction) <= end
                },
            },
        )

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        """Return only the held rows addressed by ``transaction_ids``."""
        wanted = set(transaction_ids)
        return TransactionCatalogue.model_validate(
            {
                "transactions": {
                    transaction_id: transaction
                    for transaction_id, transaction in self._catalogue.transactions.items()
                    if transaction_id in wanted
                },
            },
        )

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        """Split the held catalogue into the in-window half and its remainder."""
        return LedgerDatePartition(in_window=self.load_for_date_range(start, end), index_complete=True)

    def save(self, catalogue: TransactionCatalogue) -> None:
        """Replace the held catalogue."""
        self._catalogue = catalogue
