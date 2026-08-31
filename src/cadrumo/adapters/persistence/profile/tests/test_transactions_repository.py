"""Repository tests for bucket-scoped transaction catalogue persistence."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete, select

from .....core.errors.error_codes import get_registered_error_code
from .....domain.transactions.enums import BusinessClassification, TransactionDirection
from .....domain.transactions.errors import LedgerNoActiveBucketError, LedgerStorageError
from .....domain.transactions.models import Transaction, TransactionCatalogue
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .....tests.secure_sql import TestRuntimeProfile
from ...storage.sql import orm as _orm
from ...storage.sql.session import session_scope
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..transactions import TransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "32323232-3232-4323-8323-323232323232"

runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")


def _raw(provider_id: str, filing_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=filing_date,
        value_date=filing_date,
        amount=amount,
        currency="EUR",
        counterparty="Repository Guard SL",
        description=f"repository guard {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2024, 1, 1, 9, 0, tzinfo=UTC),
            provider_name="repository guard provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def _transaction(provider_id: str, filing_date: date, amount: Decimal) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id, filing_date, amount),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
        },
    )


def test_transaction_repository_rejects_blank_bucket_with_ledger_storage_error() -> None:
    with pytest.raises(LedgerStorageError, match="bucket_id must not be blank") as exc_info:
        TransactionCatalogueRepository(bucket_id=" ")

    assert exc_info.value.translated_message == "errors.fail.fail_financial_ledger_storage"
    assert exc_info.value.context == {"repository": "transaction_catalogue", "operation": "object_key"}


def test_transaction_repository_logs_bucket_fields(
    runtime_profile: TestRuntimeProfile,
    caplog: pytest.LogCaptureFixture,
) -> None:
    repo = TransactionCatalogueRepository(bucket_id=runtime_profile.bucket_id)

    with caplog.at_level("INFO", logger="cadrumo.adapters.persistence.profile.transactions"):
        repo.save(repo.load())

    messages = [record.getMessage() for record in caplog.records]
    # Per-row catalogue: the save log carries the bucket id and the diff counts
    # (rewritten / deleted rows) rather than a single catalogue object_key.
    assert any(
        f"bucket_id={_BUCKET_ID}" in message and "rewritten=" in message and "deleted=" in message
        for message in messages
    )


def test_partition_fallback_matches_complete_index_partition(runtime_profile: TestRuntimeProfile) -> None:
    """A stale date index changes only the serving path, not the partition contents."""

    repo = TransactionCatalogueRepository(bucket_id=runtime_profile.bucket_id)
    q1_a = _transaction("partition-q1-a", date(2024, 1, 15), Decimal("10.00"))
    q1_b = _transaction("partition-q1-b", date(2024, 3, 31), Decimal("20.00"))
    q2 = _transaction("partition-q2", date(2024, 4, 1), Decimal("30.00"))
    repo.save(TransactionCatalogue.from_transactions([q1_a, q1_b, q2]))

    start, end = date(2024, 1, 1), date(2024, 3, 31)
    complete = TransactionCatalogueRepository(bucket_id=runtime_profile.bucket_id).partition_by_date_range(start, end)
    assert complete.index_complete is True

    engine = runtime_profile.repository.engine
    with session_scope(engine) as session:
        session.execute(
            delete(_orm.TransactionDateIndexRow).where(
                _orm.TransactionDateIndexRow.bucket_id == runtime_profile.bucket_id,
                _orm.TransactionDateIndexRow.transaction_id == q2.transaction_id,
            ),
        )
    with session_scope(engine) as session:
        remaining = (
            session.execute(
                select(_orm.TransactionDateIndexRow.transaction_id).where(
                    _orm.TransactionDateIndexRow.bucket_id == runtime_profile.bucket_id,
                ),
            )
            .scalars()
            .all()
        )
    assert set(remaining) == {q1_a.transaction_id, q1_b.transaction_id}

    fallback = TransactionCatalogueRepository(bucket_id=runtime_profile.bucket_id).partition_by_date_range(start, end)

    assert fallback.index_complete is False
    assert dict(fallback.in_window.transactions) == dict(complete.in_window.transactions)
    assert {(row.transaction_id, row.filing_date) for row in fallback.out_of_window} == {
        (row.transaction_id, row.filing_date) for row in complete.out_of_window
    }
    assert set(fallback.in_window.transactions) | {row.transaction_id for row in fallback.out_of_window} == {
        q1_a.transaction_id,
        q1_b.transaction_id,
        q2.transaction_id,
    }


def test_ledger_storage_errors_have_registered_codes() -> None:
    assert get_registered_error_code(LedgerStorageError).code == "FAIL_FINANCIAL_LEDGER_STORAGE"
    assert get_registered_error_code(LedgerNoActiveBucketError).code == "REFUSED_FINANCIAL_LEDGER_NO_ACTIVE_BUCKET"
