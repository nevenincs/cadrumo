"""Encrypted application edit using the opened-record baseline commit path."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from .....application.ledger.actions_manual import create_manual_transaction, update_manual_transaction_fields
from .....application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from .....domain.transactions.enums import TransactionDirection
from ...storage.sql.secure_objects import SecureObjectRepository
from ..transactions import TransactionCatalogueRepository
from .ledger_action_create_support import ledger_ports_for_test
from .ledger_action_persistence_support import (
    BUCKET_ID as _BUCKET_ID,
    repositories as _repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


def test_unlinked_detail_edit_replaces_only_its_row_with_durable_predecessor(
    secure_objects: SecureObjectRepository,
) -> None:
    """The TUI baseline path persists one replacement, lineage and audit event."""
    transaction_repository, event_repository = _repositories(secure_objects)
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 2),
                amount=Decimal("10.00"),
                direction=TransactionDirection.OUTGOING,
                description="Original detail",
                idempotency_key="guarded-detail-edit",
            ),
            ports=ports,
            occurred_at=datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
        )
        baseline = created.transaction
        updated = update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=baseline.transaction_id,
            patch=ManualLedgerTransactionPatch(description="Corrected detail"),
            actor="operator",
            source_command="tui.ledger.transaction.update",
            expected_current=baseline,
            ports=ports,
            occurred_at=datetime(2026, 5, 2, 9, 1, tzinfo=UTC),
        )

    reopened = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).load()
    assert reopened.get(baseline.transaction_id) is None
    assert reopened.get(updated.ref.transaction_id) == updated.transaction
    assert updated.ref.transaction_id != baseline.transaction_id
    assert updated.transaction.edit_lineage[-1].previous_transaction_id == baseline.transaction_id
    assert updated.transaction.raw.amount == baseline.raw.amount
    assert updated.bucket_event_ids
