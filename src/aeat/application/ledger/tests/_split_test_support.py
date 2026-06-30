"""Shared real setup for split transaction tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.transactions import TransactionCatalogueRepository, TransactionDirection
from ....tests.secure_sql import isolated_runtime_profile
from .. import ManualLedgerTransactionCommand, create_manual_transaction

_BUCKET_ID = "24242424-2424-4424-8424-242424242424"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _repositories(objects: SecureObjectRepository, *, bucket_id: str = _BUCKET_ID):
    return (
        TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects),
        BucketEventHistoryRepository(objects=objects),
    )


def _create_parent(
    transaction_repository: TransactionCatalogueRepository,
    event_repository: BucketEventHistoryRepository,
    *,
    amount: Decimal = Decimal("100.00"),
    direction: TransactionDirection = TransactionDirection.OUTGOING,
):
    command = ManualLedgerTransactionCommand(
        bucket_id=_BUCKET_ID,
        booked_date=date(2026, 5, 2),
        amount=amount,
        direction=direction,
        counterparty="Vendor SL",
        description="materials",
        actor="operator-A",
    )
    return create_manual_transaction(
        command,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
