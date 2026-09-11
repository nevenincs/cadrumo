"""Manual ledger export lifecycle filtering tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....domain.transactions.enums import TransactionDirection
from ..actions_export import export_ledger_transactions
from ..actions_lifecycle import stash_manual_transaction
from ..actions_manual import create_manual_transaction
from ..models import LedgerExportCommand, ManualLedgerTransactionCommand
from .action_fixtures import (
    _BUCKET_ID,
    _repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_export_ledger_transactions_excludes_inactive_rows_by_default(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    active = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("250.00"),
            direction=TransactionDirection.INCOMING,
            description="client payment",
            idempotency_key="export-active",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    inactive = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 2),
            amount=Decimal("25.00"),
            direction=TransactionDirection.OUTGOING,
            description="stashed payment",
            idempotency_key="export-inactive",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 31, tzinfo=UTC),
    )
    stash_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=inactive.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 9, 0, tzinfo=UTC),
    )

    active_only = export_ledger_transactions(
        LedgerExportCommand(bucket_id=_BUCKET_ID),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )
    with_inactive = export_ledger_transactions(
        LedgerExportCommand(bucket_id=_BUCKET_ID, include_inactive=True),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 1, tzinfo=UTC),
    )

    assert tuple(row.transaction_id for row in active_only.rows) == (active.ref.transaction_id,)
    assert tuple(row.transaction_id for row in with_inactive.rows) == (
        active.ref.transaction_id,
        inactive.ref.transaction_id,
    )
    assert with_inactive.rows[1].lifecycle_state == "STASHED"
