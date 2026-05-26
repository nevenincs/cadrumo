"""Repository tests for bucket-scoped transaction catalogue persistence."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from ...adapters.persistence.storage.master_key._active_session import activate_session
from ...adapters.persistence.storage.master_key._bucket_session import BucketSession
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.sql.engine import dispose_engine, get_engine
from ...core.config import override_settings
from ...core.errors import get_registered_error_code
from . import (
    LedgerNoActiveBucketError,
    LedgerStorageError,
    TransactionCatalogueRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_BUCKET_ID = "bucket-log"
_KEK = b"t" * 32
_DEK = b"r" * 32


@pytest.fixture
def secure_engine(tmp_path: Path) -> Iterator[Engine]:
    with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=_BUCKET_ID) as settings:
        dispose_engine(settings)
        engine = get_engine(settings)
        with activate_session(_session()):
            try:
                yield engine
            finally:
                dispose_engine(settings)


def _session() -> BucketSession:
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=_KEK,
        dek=_DEK,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )


def test_transaction_repository_rejects_blank_bucket_with_ledger_storage_error(secure_engine: Engine) -> None:
    with pytest.raises(LedgerStorageError, match="bucket_id must not be blank") as exc_info:
        TransactionCatalogueRepository(bucket_id=" ", objects=SecureObjectRepository(engine=secure_engine))

    assert exc_info.value.context == {"repository": "transaction_catalogue", "operation": "object_key"}


def test_transaction_repository_logs_bucket_fields(
    secure_engine: Engine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    repo = TransactionCatalogueRepository(
        bucket_id=_BUCKET_ID,
        objects=SecureObjectRepository(engine=secure_engine),
    )

    with caplog.at_level("INFO", logger="aeat.domain.transactions._repository"):
        repo.save(repo.load())

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        f"bucket_id={_BUCKET_ID}" in message and f"object_key=transaction-catalogue:{_BUCKET_ID}" in message
        for message in messages
    )


def test_ledger_storage_errors_have_registered_codes() -> None:
    assert get_registered_error_code(LedgerStorageError).code == "FAIL_FINANCIAL_LEDGER_STORAGE"
    assert get_registered_error_code(LedgerNoActiveBucketError).code == "REFUSED_FINANCIAL_LEDGER_NO_ACTIVE_BUCKET"
