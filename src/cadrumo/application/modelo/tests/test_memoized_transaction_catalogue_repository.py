"""Real-repository coverage for
:class:`~application.modelo._transaction_catalogue_cache.MemoizedTransactionCatalogueRepository`.

The wrapper is exercised against the encrypted SQL-backed
:class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`.
Cache assertions use a second concrete repository as the storage oracle after
the first read, so the tests do not replace the repository implementation or
count calls.

See Also:
    :class:`~domain.transactions.TransactionCatalogueRepositoryProtocol`
        Repository port whose full, date-range, partition, and save methods the
        wrapper preserves.
    :class:`~domain.transactions.LedgerDatePartition`
        Period partition result cached by exact ``(start, end)`` window.
    :mod:`~application.aggregation._renta_income_ledger`
        Cumulative M130/M100 income consumers that share period partitions.
    :mod:`~application.aggregation._renta_gasto_ledger`
        Companion M130 gasto consumer that requests the same cumulative window.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile, reset_secure_object_store
from .._transaction_catalogue_cache import MemoizedTransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "51515151-5151-4151-9151-515151515151"


@pytest.fixture(scope="module")
def runtime_profile(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(
        tmp_path=tmp_path_factory.mktemp("memoized-transaction-catalogue"),
        bucket_id=_BUCKET_ID,
    ) as profile:
        yield profile


@pytest.fixture
def repository(runtime_profile: TestRuntimeProfile) -> TransactionCatalogueRepository:
    reset_secure_object_store(runtime_profile.repository)
    return _repository(runtime_profile)


def _repository(profile: TestRuntimeProfile) -> TransactionCatalogueRepository:
    return TransactionCatalogueRepository(bucket_id=profile.bucket_id, objects=profile.repository)


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


def test_load_cache_keeps_initial_catalogue_after_storage_changes(
    runtime_profile: TestRuntimeProfile,
    repository: TransactionCatalogueRepository,
) -> None:
    first_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    added_transaction = _transaction("provider-row-2", date(2024, 2, 15))
    repository.save(_catalogue(first_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)

    first_load = memoized.load()
    _repository(runtime_profile).save(_catalogue(first_transaction, added_transaction))
    repeated_load = memoized.load()

    assert repeated_load is first_load
    assert _transaction_ids(repeated_load) == {first_transaction.transaction_id}
    assert _transaction_ids(_repository(runtime_profile).load()) == {
        first_transaction.transaction_id,
        added_transaction.transaction_id,
    }


def test_date_range_cache_is_keyed_by_exact_window(
    runtime_profile: TestRuntimeProfile,
    repository: TransactionCatalogueRepository,
) -> None:
    january_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    added_january_transaction = _transaction("provider-row-2", date(2024, 1, 25))
    april_transaction = _transaction("provider-row-3", date(2024, 4, 10))
    repository.save(_catalogue(january_transaction, april_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)
    january_window = (date(2024, 1, 1), date(2024, 1, 31))

    first_january_load = memoized.load_for_date_range(*january_window)
    _repository(runtime_profile).save(
        _catalogue(january_transaction, added_january_transaction, april_transaction),
    )
    repeated_january_load = memoized.load_for_date_range(*january_window)
    april_load = memoized.load_for_date_range(date(2024, 4, 1), date(2024, 4, 30))

    assert repeated_january_load is first_january_load
    assert _transaction_ids(repeated_january_load) == {january_transaction.transaction_id}
    assert _transaction_ids(april_load) == {april_transaction.transaction_id}
    assert _transaction_ids(_repository(runtime_profile).load_for_date_range(*january_window)) == {
        january_transaction.transaction_id,
        added_january_transaction.transaction_id,
    }


def test_full_load_and_date_range_caches_are_independent(
    runtime_profile: TestRuntimeProfile,
    repository: TransactionCatalogueRepository,
) -> None:
    january_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    february_transaction = _transaction("provider-row-2", date(2024, 2, 15))
    repository.save(_catalogue(january_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)

    full_load = memoized.load()
    _repository(runtime_profile).save(_catalogue(january_transaction, february_transaction))
    february_load = memoized.load_for_date_range(date(2024, 2, 1), date(2024, 2, 29))

    assert memoized.load() is full_load
    assert _transaction_ids(full_load) == {january_transaction.transaction_id}
    assert _transaction_ids(february_load) == {february_transaction.transaction_id}


def test_targeted_id_cache_is_canonical_and_independent(
    runtime_profile: TestRuntimeProfile,
    repository: TransactionCatalogueRepository,
) -> None:
    first_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    second_transaction = _transaction("provider-row-2", date(2024, 2, 15))
    added_transaction = _transaction("provider-row-3", date(2024, 3, 15))
    repository.save(_catalogue(first_transaction, second_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)

    first = memoized.load_by_ids((second_transaction.transaction_id, first_transaction.transaction_id))
    _repository(runtime_profile).save(_catalogue(first_transaction, second_transaction, added_transaction))
    repeated = memoized.load_by_ids((first_transaction.transaction_id, second_transaction.transaction_id))
    added = memoized.load_by_ids((added_transaction.transaction_id,))

    assert repeated is first
    assert _transaction_ids(repeated) == {first_transaction.transaction_id, second_transaction.transaction_id}
    assert _transaction_ids(added) == {added_transaction.transaction_id}


def test_targeted_id_read_reuses_an_already_decrypted_partition(
    runtime_profile: TestRuntimeProfile,
    repository: TransactionCatalogueRepository,
) -> None:
    january_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    february_transaction = _transaction("provider-row-2", date(2024, 2, 15))
    repository.save(_catalogue(january_transaction, february_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)

    partition = memoized.partition_by_date_range(date(2024, 1, 1), date(2024, 3, 31))
    _repository(runtime_profile).save(_catalogue(february_transaction))
    targeted = memoized.load_by_ids((january_transaction.transaction_id,))

    assert targeted.get(january_transaction.transaction_id) is partition.in_window.get(
        january_transaction.transaction_id,
    )
    assert _transaction_ids(targeted) == {january_transaction.transaction_id}
    assert _transaction_ids(_repository(runtime_profile).load_by_ids((january_transaction.transaction_id,))) == set()


def test_partition_cache_is_keyed_by_exact_window(
    runtime_profile: TestRuntimeProfile,
    repository: TransactionCatalogueRepository,
) -> None:
    """The partition cache is keyed like ``load_for_date_range``'s, and independent from it.

    Regression coverage for #408 Path A / O2: the M130 income and gasto
    resolvers request the IDENTICAL cumulative window via
    :meth:`~MemoizedTransactionCatalogueRepository.partition_by_date_range`
    in one calculate invocation, so this cache is load-bearing, not
    incidental.
    """
    january_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    added_january_transaction = _transaction("provider-row-2", date(2024, 1, 25))
    april_transaction = _transaction("provider-row-3", date(2024, 4, 10))
    repository.save(_catalogue(january_transaction, april_transaction))
    memoized = MemoizedTransactionCatalogueRepository(repository)
    january_window = (date(2024, 1, 1), date(2024, 1, 31))

    first_january_partition = memoized.partition_by_date_range(*january_window)
    _repository(runtime_profile).save(
        _catalogue(january_transaction, added_january_transaction, april_transaction),
    )
    repeated_january_partition = memoized.partition_by_date_range(*january_window)
    april_partition = memoized.partition_by_date_range(date(2024, 4, 1), date(2024, 4, 30))

    assert repeated_january_partition is first_january_partition
    assert _transaction_ids(repeated_january_partition.in_window) == {january_transaction.transaction_id}
    assert _transaction_ids(april_partition.in_window) == {april_transaction.transaction_id}
    live_january_partition = _repository(runtime_profile).partition_by_date_range(*january_window)
    assert _transaction_ids(live_january_partition.in_window) == {
        january_transaction.transaction_id,
        added_january_transaction.transaction_id,
    }


def test_exists_save_and_bucket_id_delegate_to_concrete_repository(
    runtime_profile: TestRuntimeProfile,
    repository: TransactionCatalogueRepository,
) -> None:
    memoized = MemoizedTransactionCatalogueRepository(repository)
    first_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    replacement_transaction = _transaction("provider-row-2", date(2024, 3, 15))

    assert memoized.bucket_id == runtime_profile.bucket_id
    assert memoized.exists() is False

    _repository(runtime_profile).save(_catalogue(first_transaction))
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
    assert _transaction_ids(_repository(runtime_profile).load()) == expected
