"""Per-calculation :class:`TransactionCatalogue` read-through caching."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...domain.transactions import LedgerDatePartition, TransactionCatalogue, TransactionCatalogueRepositoryProtocol


class MemoizedTransactionCatalogueRepository:
    """Cache immutable catalogue reads across one source-mesh calculation.

    Multiple enrolled ledger resolvers share the same repository during one
    calculation. The wrapper loads each full catalogue or exact date window at
    most once while delegating writes directly to the authority repository.
    """

    __slots__ = ("_catalogue", "_date_range_catalogues", "_id_catalogues", "_partition_catalogues", "_repository")

    def __init__(self, repository: TransactionCatalogueRepositoryProtocol) -> None:
        self._repository = repository
        self._catalogue: TransactionCatalogue | None = None
        self._date_range_catalogues: dict[tuple[date, date], TransactionCatalogue] = {}
        self._id_catalogues: dict[tuple[str, ...], TransactionCatalogue] = {}
        self._partition_catalogues: dict[tuple[date, date], LedgerDatePartition] = {}

    @property
    def bucket_id(self) -> str:
        """Return the wrapped repository's bound bucket id."""
        return self._repository.bucket_id

    def exists(self) -> bool:
        """Delegate the repository's cheap index-only existence read."""
        return self._repository.exists()

    def load(self) -> TransactionCatalogue:
        """Load the full catalogue from storage at most once."""
        if self._catalogue is None:
            self._catalogue = self._repository.load()
        return self._catalogue

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        """Load an exact date-window catalogue at most once."""
        key = (start, end)
        cached = self._date_range_catalogues.get(key)
        if cached is None:
            cached = self._repository.load_for_date_range(start, end)
            self._date_range_catalogues[key] = cached
        return cached

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        """Load one canonical contributor-id set at most once."""
        key = tuple(sorted(set(transaction_ids)))
        cached = self._id_catalogues.get(key)
        if cached is None:
            requested = set(key)
            for partition in self._partition_catalogues.values():
                available = partition.in_window.transactions
                if requested.issubset(available):
                    from ...domain.transactions import TransactionCatalogue

                    cached = TransactionCatalogue.from_transactions(available[transaction_id] for transaction_id in key)
                    break
            if cached is None:
                cached = self._repository.load_by_ids(key)
            self._id_catalogues[key] = cached
        return cached

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        """Load an exact date-window partition at most once."""
        key = (start, end)
        cached = self._partition_catalogues.get(key)
        if cached is None:
            cached = self._repository.partition_by_date_range(start, end)
            self._partition_catalogues[key] = cached
        return cached

    def save(self, catalogue: TransactionCatalogue) -> None:
        """Delegate a :class:`TransactionCatalogue` write to the authority repository."""
        self._repository.save(catalogue)


__all__ = ["MemoizedTransactionCatalogueRepository"]
