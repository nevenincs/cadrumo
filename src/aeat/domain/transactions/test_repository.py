"""Repository tests for bucket-scoped transaction catalogue persistence."""

from __future__ import annotations

from collections.abc import Iterator
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
    TransactionCatalogueRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@pytest.fixture
def secure_engine(tmp_path: Path) -> Iterator[Engine]:
    provider = EphemeralMasterKeyProvider()
    with provider:
        database_url = f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}"
        engine = create_engine_from_settings(Settings(aeat_database_url=database_url))
        Base.metadata.create_all(engine)
        try:
            yield engine
        finally:
            engine.dispose()


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
