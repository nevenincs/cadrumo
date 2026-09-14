"""Encrypted persistence coverage for the transaction catalogue repository.

The application cache contract is covered by the inward application suite with
a domain-protocol fake.  This outer suite exercises the concrete encrypted SQL
repository directly, including round trips, addressed reads, date partitions,
and writes that replace the persisted catalogue.

See Also:
    :class:`~domain.transactions.TransactionCatalogueRepositoryProtocol`
        Repository port whose full, date-range, partition, and save methods the
        encrypted adapter implements.
    :class:`~domain.transactions.LedgerDatePartition`
        Period partition result returned for an exact ``(start, end)`` window.
    :mod:`~application.aggregation.renta_income_ledger`
        Cumulative M130/M100 income consumers that share period partitions.
    :mod:`~application.aggregation.renta_gasto_ledger`
        Companion M130 gasto consumer that requests the same cumulative window.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    TestRuntimeProfile,
    isolated_runtime_profile,
    reset_secure_object_store,
)
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

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


def test_load_round_trip_exposes_storage_changes(
    runtime_profile: TestRuntimeProfile,
    repository: TransactionCatalogueRepository,
) -> None:
    first_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    added_transaction = _transaction("provider-row-2", date(2024, 2, 15))
    repository.save(_catalogue(first_transaction))
    first_load = repository.load()
    assert _transaction_ids(first_load) == {first_transaction.transaction_id}

    _repository(runtime_profile).save(_catalogue(first_transaction, added_transaction))
    repeated_load = repository.load()

    assert _transaction_ids(repeated_load) == {
        first_transaction.transaction_id,
        added_transaction.transaction_id,
    }


def test_date_range_reads_honor_exact_window(
    runtime_profile: TestRuntimeProfile,
    repository: TransactionCatalogueRepository,
) -> None:
    january_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    added_january_transaction = _transaction("provider-row-2", date(2024, 1, 25))
    april_transaction = _transaction("provider-row-3", date(2024, 4, 10))
    repository.save(_catalogue(january_transaction, april_transaction))
    january_window = (date(2024, 1, 1), date(2024, 1, 31))

    first_january_load = repository.load_for_date_range(*january_window)
    april_load = repository.load_for_date_range(date(2024, 4, 1), date(2024, 4, 30))

    assert _transaction_ids(first_january_load) == {january_transaction.transaction_id}
    assert _transaction_ids(april_load) == {april_transaction.transaction_id}

    _repository(runtime_profile).save(
        _catalogue(january_transaction, added_january_transaction, april_transaction),
    )
    repeated_january_load = repository.load_for_date_range(*january_window)

    assert _transaction_ids(repeated_january_load) == {
        january_transaction.transaction_id,
        added_january_transaction.transaction_id,
    }


def test_full_and_date_range_reads_select_their_respective_rows(
    runtime_profile: TestRuntimeProfile,
    repository: TransactionCatalogueRepository,
) -> None:
    january_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    february_transaction = _transaction("provider-row-2", date(2024, 2, 15))
    repository.save(_catalogue(january_transaction, february_transaction))
    full_load = repository.load()
    february_load = repository.load_for_date_range(date(2024, 2, 1), date(2024, 2, 29))

    assert _transaction_ids(full_load) == {
        january_transaction.transaction_id,
        february_transaction.transaction_id,
    }
    assert _transaction_ids(february_load) == {february_transaction.transaction_id}


def test_targeted_id_reads_are_canonical_and_independent(
    runtime_profile: TestRuntimeProfile,
    repository: TransactionCatalogueRepository,
) -> None:
    first_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    second_transaction = _transaction("provider-row-2", date(2024, 2, 15))
    added_transaction = _transaction("provider-row-3", date(2024, 3, 15))
    repository.save(_catalogue(first_transaction, second_transaction))
    first = repository.load_by_ids((second_transaction.transaction_id, first_transaction.transaction_id))
    assert _transaction_ids(first) == {first_transaction.transaction_id, second_transaction.transaction_id}

    _repository(runtime_profile).save(_catalogue(first_transaction, second_transaction, added_transaction))
    repeated = repository.load_by_ids((first_transaction.transaction_id, second_transaction.transaction_id))
    added = repository.load_by_ids((added_transaction.transaction_id,))

    assert _transaction_ids(repeated) == {first_transaction.transaction_id, second_transaction.transaction_id}
    assert _transaction_ids(added) == {added_transaction.transaction_id}


def test_targeted_id_reads_match_the_current_persisted_partition(
    runtime_profile: TestRuntimeProfile,
    repository: TransactionCatalogueRepository,
) -> None:
    january_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    february_transaction = _transaction("provider-row-2", date(2024, 2, 15))
    repository.save(_catalogue(january_transaction, february_transaction))
    partition = repository.partition_by_date_range(date(2024, 1, 1), date(2024, 3, 31))
    targeted = repository.load_by_ids((january_transaction.transaction_id,))

    assert _transaction_ids(partition.in_window) == {
        january_transaction.transaction_id,
        february_transaction.transaction_id,
    }
    assert _transaction_ids(targeted) == {january_transaction.transaction_id}

    _repository(runtime_profile).save(_catalogue(february_transaction))
    assert _transaction_ids(repository.load_by_ids((january_transaction.transaction_id,))) == set()


def test_partition_reads_honor_exact_window(
    runtime_profile: TestRuntimeProfile,
    repository: TransactionCatalogueRepository,
) -> None:
    """Partitioning retains every row while selecting the requested window."""
    january_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    added_january_transaction = _transaction("provider-row-2", date(2024, 1, 25))
    april_transaction = _transaction("provider-row-3", date(2024, 4, 10))
    repository.save(_catalogue(january_transaction, april_transaction))
    january_window = (date(2024, 1, 1), date(2024, 1, 31))

    first_january_partition = repository.partition_by_date_range(*january_window)
    april_partition = repository.partition_by_date_range(date(2024, 4, 1), date(2024, 4, 30))

    assert _transaction_ids(first_january_partition.in_window) == {january_transaction.transaction_id}
    assert _transaction_ids(april_partition.in_window) == {april_transaction.transaction_id}

    _repository(runtime_profile).save(
        _catalogue(january_transaction, added_january_transaction, april_transaction),
    )
    repeated_january_partition = repository.partition_by_date_range(*january_window)

    assert _transaction_ids(repeated_january_partition.in_window) == {
        january_transaction.transaction_id,
        added_january_transaction.transaction_id,
    }


def test_exists_save_and_bucket_id_are_exposed_by_concrete_repository(
    runtime_profile: TestRuntimeProfile,
    repository: TransactionCatalogueRepository,
) -> None:
    first_transaction = _transaction("provider-row-1", date(2024, 1, 15))
    replacement_transaction = _transaction("provider-row-2", date(2024, 3, 15))

    assert repository.bucket_id == runtime_profile.bucket_id
    assert repository.exists() is False

    repository.save(_catalogue(first_transaction))
    assert repository.exists() is True

    march_window = (date(2024, 3, 1), date(2024, 3, 31))
    assert _transaction_ids(repository.load()) == {first_transaction.transaction_id}
    assert _transaction_ids(repository.load_for_date_range(*march_window)) == set()
    assert _transaction_ids(repository.partition_by_date_range(*march_window).in_window) == set()
    assert _transaction_ids(repository.load_by_ids((first_transaction.transaction_id,))) == {
        first_transaction.transaction_id,
    }

    repository.save(_catalogue(replacement_transaction))

    expected = {replacement_transaction.transaction_id}
    assert _transaction_ids(repository.load()) == expected
    assert _transaction_ids(repository.load_for_date_range(*march_window)) == expected
    assert _transaction_ids(repository.partition_by_date_range(*march_window).in_window) == expected
    assert _transaction_ids(repository.load_by_ids((replacement_transaction.transaction_id,))) == expected
    assert _transaction_ids(repository.load_by_ids((first_transaction.transaction_id,))) == set()
