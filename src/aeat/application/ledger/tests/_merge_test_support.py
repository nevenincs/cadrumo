"""Shared real setup for merge transaction tests."""

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
from .. import (
    ManualLedgerTransactionCommand,
    SplitChildCommand,
    create_manual_transaction,
    split_transaction,
)

_BUCKET_ID = "25252525-2525-4525-8525-252525252525"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _repositories(objects: SecureObjectRepository, *, bucket_id: str = _BUCKET_ID):
    return (
        TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects),
        BucketEventHistoryRepository(objects=objects),
    )


def _split_setup(
    transaction_repository: TransactionCatalogueRepository,
    event_repository: BucketEventHistoryRepository,
    *,
    parent_amount: Decimal = Decimal("100.00"),
    direction: TransactionDirection = TransactionDirection.OUTGOING,
):
    parent_command = ManualLedgerTransactionCommand(
        bucket_id=_BUCKET_ID,
        booked_date=date(2026, 5, 2),
        amount=parent_amount,
        direction=direction,
        counterparty="Vendor SL",
        description="materials",
        actor="operator-A",
    )
    parent = create_manual_transaction(
        parent_command,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    half = parent_amount / Decimal("2")
    split = split_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=parent.ref.transaction_id,
        children=(
            SplitChildCommand(amount=half, description="business portion"),
            SplitChildCommand(amount=parent_amount - half, description="personal portion"),
        ),
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 10, 0, tzinfo=UTC),
    )
    return parent, split
