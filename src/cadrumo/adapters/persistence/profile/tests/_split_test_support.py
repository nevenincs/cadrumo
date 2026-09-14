"""Shared real setup for split transaction tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.tests.ledger_action_create_support import ledger_ports_for_test
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.actions_manual import create_manual_transaction
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand
from cadrumo.domain.transactions.enums import TransactionDirection

_BUCKET_ID = "24242424-2424-4424-8424-242424242424"


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
        ports=ledger_ports_for_test(
            transaction_repository=transaction_repository, bucket_event_repository=event_repository
        ),
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
