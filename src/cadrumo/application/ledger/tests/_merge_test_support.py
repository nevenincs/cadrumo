"""Shared real setup for merge transaction tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.transactions import TransactionDirection
from ..actions_manual import create_manual_transaction
from ..actions_split_merge import split_transaction
from ..models import ManualLedgerTransactionCommand, SplitChildCommand

_BUCKET_ID = "25252525-2525-4525-8525-252525252525"


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
