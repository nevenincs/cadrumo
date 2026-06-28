"""Repository tests for bucket-scoped transaction catalogue persistence."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.errors import get_registered_error_code
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .. import (
    LedgerNoActiveBucketError,
    LedgerStorageError,
    TransactionCatalogueRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-log") as profile:
        yield profile


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

    with caplog.at_level("INFO", logger="aeat.domain.transactions._repository"):
        repo.save(repo.load())

    messages = [record.getMessage() for record in caplog.records]
    # Per-row catalogue: the save log carries the bucket id and the diff counts
    # (rewritten / deleted rows) rather than a single catalogue object_key.
    assert any(
        "bucket_id=bucket-log" in message and "rewritten=" in message and "deleted=" in message for message in messages
    )


def test_ledger_storage_errors_have_registered_codes() -> None:
    assert get_registered_error_code(LedgerStorageError).code == "FAIL_FINANCIAL_LEDGER_STORAGE"
    assert get_registered_error_code(LedgerNoActiveBucketError).code == "REFUSED_FINANCIAL_LEDGER_NO_ACTIVE_BUCKET"
