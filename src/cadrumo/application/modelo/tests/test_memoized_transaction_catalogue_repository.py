"""Application contract tests for the transaction-catalogue read cache.

The memoized wrapper is an application policy: it caches immutable reads for
one calculation and invalidates every read cache after a write.  These tests
exercise that contract through the domain repository protocol and an
in-memory fake.  Encrypted SQL persistence is covered by the companion profile
adapter test, so this inward suite does not need to know the storage adapter.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    Transaction,
    TransactionCatalogue,
)
from ....domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .._transaction_catalogue_cache import MemoizedTransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "51515151-5151-4151-9151-515151515151"


class _InMemoryTransactionCatalogueRepository(TransactionCatalogueRepositoryProtocol):
    """Small protocol fake whose catalogue can change behind the cache."""

    def __init__(self) -> None:
        self._catalogue = TransactionCatalogue()

    @property
    def bucket_id(self) -> str:
        return _BUCKET_ID

    def exists(self) -> bool:
        return bool(self._catalogue.transactions)

    def load(self) -> TransactionCatalogue:
        return self._catalogue

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        return TransactionCatalogue.from_transactions(
            transaction
            for transaction in self._catalogue
            if start <= transaction.raw.booked_date <= end
        )

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        requested = tuple(sorted(set(transaction_ids)))
        return TransactionCatalogue.from_transactions(
            transaction
            for transaction_id in requested
            if (transaction := self._catalogue.get(transaction_id)) is not None
        )

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        in_window = tuple(
            transaction
            for transaction in self._catalogue
            if start <= transaction.raw.booked_date <= end
        )
        out_of_window = tuple(
            OutOfWindowTransactionIndexEntry(
                transaction_id=transaction.transaction_id,
                filing_date=transaction.raw.booked_date,
            )
            for transaction in self._catalogue
            if not start <= transaction.raw.booked_date <= end
        )
        return LedgerDatePartition(
            in_window=TransactionCatalogue.from_transactions(in_window),
            out_of_window=out_of_window,
            index_complete=True,
        )

    def save(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue


@pytest.fixture
def repository() -> _InMemoryTransactionCatalogueRepository:
    return _InMemoryTransactionCatalogueRepository()


def _raw(provider_id: str, booked_on: date, amount: Decimal, description: str) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_on,
        value_date=booked_on,
        amount=amount,
        currency="EUR",
        counterparty="Supplier SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=7,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": description},
    )


def _transaction(
    provider_id: str,
    booked_on: date,
    *,
    amount: Decimal = Decimal("100.00"),
    description: str = "Software subscription",
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id, booked_on, amount, description),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
        },
    )


def _catalogue(*transactions: Transaction) -> TransactionCatalogue:
    return TransactionCatalogue.from_transactions(transactions)


def _transaction_ids(catalogue: TransactionCatalogue) -> set[str]:
    return set(catalogue.transactions)


def test_load_cache_keeps_initial_catalogue_after_repository_changes(
    repository: _InMemoryTransactionCatalogueRepository,
) -> None:
    first_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    added_transaction = _transaction("provider-row-2", date(2024, 2, 15))
    repository.save(_catalogue(first_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)

    first_load = memoized.load()
    repository.save(_catalogue(first_transaction, added_transaction))
    repeated_load = memoized.load()

    assert repeated_load is first_load
    assert _transaction_ids(repeated_load) == {first_transaction.transaction_id}
    assert _transaction_ids(repository.load()) == {
        first_transaction.transaction_id,
        added_transaction.transaction_id,
    }


def test_date_range_cache_is_keyed_by_exact_window(
    repository: _InMemoryTransactionCatalogueRepository,
) -> None:
    january_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    added_january_transaction = _transaction("provider-row-2", date(2024, 1, 25))
    april_transaction = _transaction("provider-row-3", date(2024, 4, 10))
    repository.save(_catalogue(january_transaction, april_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)
    january_window = (date(2024, 1, 1), date(2024, 1, 31))

    first_january_load = memoized.load_for_date_range(*january_window)
    repository.save(_catalogue(january_transaction, added_january_transaction, april_transaction))
    repeated_january_load = memoized.load_for_date_range(*january_window)
    april_load = memoized.load_for_date_range(date(2024, 4, 1), date(2024, 4, 30))

    assert repeated_january_load is first_january_load
    assert _transaction_ids(repeated_january_load) == {january_transaction.transaction_id}
    assert _transaction_ids(april_load) == {april_transaction.transaction_id}
    assert _transaction_ids(repository.load_for_date_range(*january_window)) == {
        january_transaction.transaction_id,
        added_january_transaction.transaction_id,
    }


def test_full_load_and_date_range_caches_are_independent(
    repository: _InMemoryTransactionCatalogueRepository,
) -> None:
    january_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    february_transaction = _transaction("provider-row-2", date(2024, 2, 15))
    repository.save(_catalogue(january_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)

    full_load = memoized.load()
    repository.save(_catalogue(january_transaction, february_transaction))
    february_load = memoized.load_for_date_range(date(2024, 2, 1), date(2024, 2, 29))

    assert memoized.load() is full_load
    assert _transaction_ids(full_load) == {january_transaction.transaction_id}
    assert _transaction_ids(february_load) == {february_transaction.transaction_id}


def test_targeted_id_cache_is_canonical_and_independent(
    repository: _InMemoryTransactionCatalogueRepository,
) -> None:
    first_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    second_transaction = _transaction("provider-row-2", date(2024, 2, 15))
    added_transaction = _transaction("provider-row-3", date(2024, 3, 15))
    repository.save(_catalogue(first_transaction, second_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)

    first = memoized.load_by_ids((second_transaction.transaction_id, first_transaction.transaction_id))
    repository.save(_catalogue(first_transaction, second_transaction, added_transaction))
    repeated = memoized.load_by_ids((first_transaction.transaction_id, second_transaction.transaction_id))
    added = memoized.load_by_ids((added_transaction.transaction_id,))

    assert repeated is first
    assert _transaction_ids(repeated) == {first_transaction.transaction_id, second_transaction.transaction_id}
    assert _transaction_ids(added) == {added_transaction.transaction_id}


def test_targeted_id_read_reuses_an_already_decrypted_partition(
    repository: _InMemoryTransactionCatalogueRepository,
) -> None:
    january_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    february_transaction = _transaction("provider-row-2", date(2024, 2, 15))
    repository.save(_catalogue(january_transaction, february_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)

    partition = memoized.partition_by_date_range(date(2024, 1, 1), date(2024, 3, 31))
    repository.save(_catalogue(february_transaction))
    targeted = memoized.load_by_ids((january_transaction.transaction_id,))

    assert targeted.get(january_transaction.transaction_id) is partition.in_window.get(
        january_transaction.transaction_id,
    )
    assert _transaction_ids(targeted) == {january_transaction.transaction_id}
    assert _transaction_ids(repository.load_by_ids((january_transaction.transaction_id,))) == set()


def test_partition_cache_is_keyed_by_exact_window(
    repository: _InMemoryTransactionCatalogueRepository,
) -> None:
    january_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    added_january_transaction = _transaction("provider-row-2", date(2024, 1, 25))
    april_transaction = _transaction("provider-row-3", date(2024, 4, 10))
    repository.save(_catalogue(january_transaction, april_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)
    january_window = (date(2024, 1, 1), date(2024, 1, 31))

    first_january_partition = memoized.partition_by_date_range(*january_window)
    repository.save(_catalogue(january_transaction, added_january_transaction, april_transaction))
    repeated_january_partition = memoized.partition_by_date_range(*january_window)
    april_partition = memoized.partition_by_date_range(date(2024, 4, 1), date(2024, 4, 30))

    assert repeated_january_partition is first_january_partition
    assert _transaction_ids(repeated_january_partition.in_window) == {january_transaction.transaction_id}
    assert _transaction_ids(april_partition.in_window) == {april_transaction.transaction_id}
    live_january_partition = repository.partition_by_date_range(*january_window)
    assert _transaction_ids(live_january_partition.in_window) == {
        january_transaction.transaction_id,
        added_january_transaction.transaction_id,
    }


def test_exists_save_and_bucket_id_delegate_to_repository(
    repository: _InMemoryTransactionCatalogueRepository,
) -> None:
    memoized = MemoizedTransactionCatalogueRepository(repository)
    first_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    replacement_transaction = _transaction("provider-row-2", date(2024, 3, 15))

    assert memoized.bucket_id == _BUCKET_ID
    assert memoized.exists() is False

    repository.save(_catalogue(first_transaction))
    assert memoized.exists() is True

    march_window = (date(2024, 3, 1), date(2024, 3, 31))
    assert _transaction_ids(memoized.load()) == {first_transaction.transaction_id}
    assert _transaction_ids(memoized.load_for_date_range(*march_window)) == set()
    assert _transaction_ids(memoized.partition_by_date_range(*march_window).in_window) == set()
    assert _transaction_ids(memoized.load_by_ids((first_transaction.transaction_id,))) == {
        first_transaction.transaction_id,
    }

    memoized.save(_catalogue(replacement_transaction))

    expected = {replacement_transaction.transaction_id}
    assert _transaction_ids(memoized.load()) == expected
    assert _transaction_ids(memoized.load_for_date_range(*march_window)) == expected
    assert _transaction_ids(memoized.partition_by_date_range(*march_window).in_window) == expected
    assert _transaction_ids(memoized.load_by_ids((replacement_transaction.transaction_id,))) == expected
    assert _transaction_ids(memoized.load_by_ids((first_transaction.transaction_id,))) == set()
    assert _transaction_ids(repository.load()) == expected
