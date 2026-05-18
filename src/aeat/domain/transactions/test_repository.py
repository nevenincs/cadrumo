"""Repository tests for bucket-scoped transaction catalogue persistence."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from ...adapters.persistence.storage import EphemeralMasterKeyProvider
from ...adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from ...adapters.persistence.storage.sql._orm import Base
from ...core.config import Settings
from ...core.errors import get_registered_error_code
from . import (
    LedgerNoActiveBucketError,
    LedgerStorageError,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    TransactionCatalogueRepository,
    TransactionDirection,
    derive_transaction_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@pytest.fixture
def secure_engine(tmp_path: Path) -> Iterator[Engine]:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            yield engine
        finally:
            engine.dispose()


def _raw_transaction() -> RawTransaction:
    return RawTransaction(
        transaction_id="provider-row-1",
        booked_date=date(2026, 5, 1),
        value_date=date(2026, 5, 1),
        amount=Decimal("-80.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description="same imported row in two buckets",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": "same imported row in two buckets"},
    )


def test_same_imported_row_is_idempotent_per_bucket_not_globally(
    secure_engine: Engine,
) -> None:
    raw = _raw_transaction()
    expected_tx_id = derive_transaction_id(raw)
    repo_a = TransactionCatalogueRepository(
        bucket_id="bucket-a",
        objects=SecureObjectRepository(engine=secure_engine),
    )
    repo_b = TransactionCatalogueRepository(
        bucket_id="bucket-b",
        objects=SecureObjectRepository(engine=secure_engine),
    )

    first = repo_a.merge_raw_transactions((raw,), direction_resolver=lambda _: TransactionDirection.OUTGOING)
    second = repo_b.merge_raw_transactions((raw,), direction_resolver=lambda _: TransactionDirection.OUTGOING)
    duplicate = repo_a.merge_raw_transactions((raw,), direction_resolver=lambda _: TransactionDirection.OUTGOING)

    assert first.imported == 1
    assert second.imported == 1
    assert duplicate.imported == 0
    assert duplicate.skipped == 1
    assert first.imported_refs[0].bucket_id == "bucket-a"
    assert second.imported_refs[0].bucket_id == "bucket-b"
    assert duplicate.skipped_refs[0].bucket_id == "bucket-a"
    assert first.imported_refs[0].transaction_id == expected_tx_id
    assert second.imported_refs[0].transaction_id == expected_tx_id
    assert tuple(repo_a.load().transactions) == (expected_tx_id,)
    assert tuple(repo_b.load().transactions) == (expected_tx_id,)


def test_transaction_repository_rejects_blank_bucket_with_ledger_storage_error() -> None:
    with pytest.raises(LedgerStorageError, match="bucket_id must not be blank") as exc_info:
        TransactionCatalogueRepository(bucket_id=" ")

    assert exc_info.value.context == {"repository": "transaction_catalogue", "operation": "object_key"}


def test_transaction_repository_logs_bucket_fields(
    secure_engine: Engine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    repo = TransactionCatalogueRepository(
        bucket_id="bucket-log",
        objects=SecureObjectRepository(engine=secure_engine),
    )

    with caplog.at_level("INFO", logger="aeat.domain.transactions._repository"):
        repo.save(repo.load())

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "bucket_id=bucket-log" in message and "object_key=transaction-catalogue:bucket-log" in message
        for message in messages
    )


def test_ledger_storage_errors_have_registered_codes() -> None:
    assert get_registered_error_code(LedgerStorageError).code == "FAIL_FINANCIAL_LEDGER_STORAGE"
    assert get_registered_error_code(LedgerNoActiveBucketError).code == "REFUSED_FINANCIAL_LEDGER_NO_ACTIVE_BUCKET"
