"""Application contract tests for the transaction-catalogue read cache.

The memoized wrapper is an application policy: it caches immutable reads for
one calculation and invalidates every read cache after a write.  These tests
exercise that contract through the domain repository protocol and an
in-memory fake.  Encrypted SQL persistence is covered by the companion profile
adapter test, so this inward suite does not need to know the storage adapter.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable
from datetime import date
from typing import override

import pytest

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.date_partition import LedgerDatePartition, OutOfWindowTransactionIndexEntry
from ....domain.transactions.models import TransactionCatalogue
from ....domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..transaction_catalogue_cache import MemoizedTransactionCatalogueRepository
from .memoized_transaction_catalogue_support import (
    memoized_catalogue,
    memoized_transaction,
    memoized_transaction_ids,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "51515151-5151-4151-9151-515151515151"
_YEAR = filing_year_envelope().horizon


def _month_window(month: int) -> tuple[date, date]:
    """Return the first and last day of one month of the exercise, whatever its leap status."""
    return date(_YEAR, month, 1), date(_YEAR, month, calendar.monthrange(_YEAR, month)[1])


class _InMemoryTransactionCatalogueRepository(TransactionCatalogueRepositoryProtocol):
    """Small protocol fake whose catalogue can change behind the cache."""

    def __init__(self) -> None:
        self.memoized_catalogue = TransactionCatalogue()
        self.load_by_ids_calls = 0

    @property
    @override
    def bucket_id(self) -> str:
        return _BUCKET_ID

    @override
    def exists(self) -> bool:
        return bool(self.memoized_catalogue.transactions)

    @override
    def load(self) -> TransactionCatalogue:
        return self.memoized_catalogue

    @override
    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        return TransactionCatalogue.from_transactions(
            transaction for transaction in self.memoized_catalogue if start <= transaction.raw.booked_date <= end
        )

    @override
    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        self.load_by_ids_calls += 1
        requested = tuple(sorted(set(transaction_ids)))
        return TransactionCatalogue.from_transactions(
            transaction
            for transaction_id in requested
            if (transaction := self.memoized_catalogue.get(transaction_id)) is not None
        )

    @override
    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        in_window = tuple(
            transaction for transaction in self.memoized_catalogue if start <= transaction.raw.booked_date <= end
        )
        out_of_window = tuple(
            OutOfWindowTransactionIndexEntry(
                transaction_id=transaction.transaction_id,
                filing_date=transaction.raw.booked_date,
            )
            for transaction in self.memoized_catalogue
            if not start <= transaction.raw.booked_date <= end
        )
        return LedgerDatePartition(
            in_window=TransactionCatalogue.from_transactions(in_window),
            out_of_window=out_of_window,
            index_complete=True,
        )

    @override
    def save(self, catalogue: TransactionCatalogue) -> None:
        self.memoized_catalogue = catalogue


@pytest.fixture
def repository() -> _InMemoryTransactionCatalogueRepository:
    return _InMemoryTransactionCatalogueRepository()


def test_load_cache_keeps_initial_catalogue_after_repository_changes(
    repository: _InMemoryTransactionCatalogueRepository,
) -> None:
    first_transaction = memoized_transaction("provider-row-1", date(_YEAR, 1, 15))
    added_transaction = memoized_transaction("provider-row-2", date(_YEAR, 2, 15))
    repository.save(memoized_catalogue(first_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)

    first_load = memoized.load()
    repository.save(memoized_catalogue(first_transaction, added_transaction))
    repeated_load = memoized.load()

    assert repeated_load is first_load
    assert memoized_transaction_ids(repeated_load) == {first_transaction.transaction_id}
    assert memoized_transaction_ids(repository.load()) == {
        first_transaction.transaction_id,
        added_transaction.transaction_id,
    }


def test_date_range_cache_is_keyed_by_exact_window(
    repository: _InMemoryTransactionCatalogueRepository,
) -> None:
    january_transaction = memoized_transaction("provider-row-1", date(_YEAR, 1, 15))
    added_january_transaction = memoized_transaction("provider-row-2", date(_YEAR, 1, 25))
    april_transaction = memoized_transaction("provider-row-3", date(_YEAR, 4, 10))
    repository.save(memoized_catalogue(january_transaction, april_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)
    january_window = _month_window(1)

    first_january_load = memoized.load_for_date_range(*january_window)
    repository.save(memoized_catalogue(january_transaction, added_january_transaction, april_transaction))
    repeated_january_load = memoized.load_for_date_range(*january_window)
    april_load = memoized.load_for_date_range(*_month_window(4))

    assert repeated_january_load is first_january_load
    assert memoized_transaction_ids(repeated_january_load) == {january_transaction.transaction_id}
    assert memoized_transaction_ids(april_load) == {april_transaction.transaction_id}
    assert memoized_transaction_ids(repository.load_for_date_range(*january_window)) == {
        january_transaction.transaction_id,
        added_january_transaction.transaction_id,
    }


def test_full_load_and_date_range_caches_are_independent(
    repository: _InMemoryTransactionCatalogueRepository,
) -> None:
    january_transaction = memoized_transaction("provider-row-1", date(_YEAR, 1, 15))
    february_transaction = memoized_transaction("provider-row-2", date(_YEAR, 2, 15))
    repository.save(memoized_catalogue(january_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)

    full_load = memoized.load()
    repository.save(memoized_catalogue(january_transaction, february_transaction))
    february_load = memoized.load_for_date_range(*_month_window(2))

    assert memoized.load() is full_load
    assert memoized_transaction_ids(full_load) == {january_transaction.transaction_id}
    assert memoized_transaction_ids(february_load) == {february_transaction.transaction_id}


def test_targeted_id_cache_is_canonical_and_independent(
    repository: _InMemoryTransactionCatalogueRepository,
) -> None:
    first_transaction = memoized_transaction("provider-row-1", date(_YEAR, 1, 15))
    second_transaction = memoized_transaction("provider-row-2", date(_YEAR, 2, 15))
    added_transaction = memoized_transaction("provider-row-3", date(_YEAR, 3, 15))
    repository.save(memoized_catalogue(first_transaction, second_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)

    first = memoized.load_by_ids((second_transaction.transaction_id, first_transaction.transaction_id))
    repository.save(memoized_catalogue(first_transaction, second_transaction, added_transaction))
    repeated = memoized.load_by_ids((first_transaction.transaction_id, second_transaction.transaction_id))
    added = memoized.load_by_ids((added_transaction.transaction_id,))

    assert repeated is first
    assert memoized_transaction_ids(repeated) == {first_transaction.transaction_id, second_transaction.transaction_id}
    assert memoized_transaction_ids(added) == {added_transaction.transaction_id}


def test_targeted_id_read_reuses_an_already_decrypted_partition(
    repository: _InMemoryTransactionCatalogueRepository,
) -> None:
    january_transaction = memoized_transaction("provider-row-1", date(_YEAR, 1, 15))
    february_transaction = memoized_transaction("provider-row-2", date(_YEAR, 2, 15))
    repository.save(memoized_catalogue(january_transaction, february_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)

    partition = memoized.partition_by_date_range(date(_YEAR, 1, 1), date(_YEAR, 3, 31))
    full_partition_read = memoized.load_by_ids(tuple(partition.in_window.transactions))
    repository.save(memoized_catalogue(february_transaction))
    targeted = memoized.load_by_ids((january_transaction.transaction_id,))

    assert full_partition_read is partition.in_window
    assert targeted.get(january_transaction.transaction_id) is partition.in_window.get(
        january_transaction.transaction_id,
    )
    assert memoized_transaction_ids(targeted) == {january_transaction.transaction_id}
    assert repository.load_by_ids_calls == 0
    assert memoized_transaction_ids(repository.load_by_ids((january_transaction.transaction_id,))) == set()


def test_partition_cache_is_keyed_by_exact_window(
    repository: _InMemoryTransactionCatalogueRepository,
) -> None:
    january_transaction = memoized_transaction("provider-row-1", date(_YEAR, 1, 15))
    added_january_transaction = memoized_transaction("provider-row-2", date(_YEAR, 1, 25))
    april_transaction = memoized_transaction("provider-row-3", date(_YEAR, 4, 10))
    repository.save(memoized_catalogue(january_transaction, april_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)
    january_window = _month_window(1)

    first_january_partition = memoized.partition_by_date_range(*january_window)
    repository.save(memoized_catalogue(january_transaction, added_january_transaction, april_transaction))
    repeated_january_partition = memoized.partition_by_date_range(*january_window)
    april_partition = memoized.partition_by_date_range(*_month_window(4))

    assert repeated_january_partition is first_january_partition
    assert memoized_transaction_ids(repeated_january_partition.in_window) == {january_transaction.transaction_id}
    assert memoized_transaction_ids(april_partition.in_window) == {april_transaction.transaction_id}
    live_january_partition = repository.partition_by_date_range(*january_window)
    assert memoized_transaction_ids(live_january_partition.in_window) == {
        january_transaction.transaction_id,
        added_january_transaction.transaction_id,
    }


def test_exists_save_and_bucket_id_delegate_to_repository(
    repository: _InMemoryTransactionCatalogueRepository,
) -> None:
    memoized = MemoizedTransactionCatalogueRepository(repository)
    first_transaction = memoized_transaction("provider-row-1", date(_YEAR, 1, 15))
    replacement_transaction = memoized_transaction("provider-row-2", date(_YEAR, 3, 15))

    assert memoized.bucket_id == _BUCKET_ID
    assert memoized.exists() is False

    repository.save(memoized_catalogue(first_transaction))
    assert memoized.exists() is True

    march_window = _month_window(3)
    assert memoized_transaction_ids(memoized.load()) == {first_transaction.transaction_id}
    assert memoized_transaction_ids(memoized.load_for_date_range(*march_window)) == set()
    assert memoized_transaction_ids(memoized.partition_by_date_range(*march_window).in_window) == set()
    assert memoized_transaction_ids(memoized.load_by_ids((first_transaction.transaction_id,))) == {
        first_transaction.transaction_id,
    }

    memoized.save(memoized_catalogue(replacement_transaction))

    expected = {replacement_transaction.transaction_id}
    assert memoized_transaction_ids(memoized.load()) == expected
    assert memoized_transaction_ids(memoized.load_for_date_range(*march_window)) == expected
    assert memoized_transaction_ids(memoized.partition_by_date_range(*march_window).in_window) == expected
    assert memoized_transaction_ids(memoized.load_by_ids((replacement_transaction.transaction_id,))) == expected
    assert memoized_transaction_ids(memoized.load_by_ids((first_transaction.transaction_id,))) == set()
    assert memoized_transaction_ids(repository.load()) == expected
