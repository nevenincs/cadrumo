"""Manual ledger rows carry the taxpayer's own bank account through add and edit.

Every case writes through the real manual-transaction service onto encrypted
secure-object storage and reads the stored row back.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.actions_manual import create_manual_transaction, update_manual_transaction_fields
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import derive_transaction_id

from .ledger_action_create_support import ledger_ports_for_test
from .ledger_action_persistence_support import BUCKET_ID as _BUCKET_ID
from .ledger_action_persistence_support import repositories as _repositories

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _command(**overrides: object) -> ManualLedgerTransactionCommand:
    return ManualLedgerTransactionCommand.model_validate(
        {
            "bucket_id": _BUCKET_ID,
            "booked_date": date(2026, 5, 1),
            "amount": Decimal("75.00"),
            "direction": TransactionDirection.OUTGOING,
            "description": "bank fee",
            **overrides,
        },
    )


def test_an_added_row_is_bound_and_an_edit_keeps_or_moves_the_binding(secure_objects: SecureObjectRepository) -> None:
    """Add binds; an unrelated edit keeps the account; an explicit edit moves it and re-derives the id."""
    transaction_repository, event_repository = _repositories(secure_objects)

    def ports():
        return ledger_ports_for_test(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        )

    with ports() as bound_ports:
        created = create_manual_transaction(
            _command(own_account_id="acc-01"),
            ports=bound_ports,
            occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
        )
    assert created.transaction.own_account_id == "acc-01"
    assert created.ref.transaction_id == derive_transaction_id(created.transaction.raw, own_account_id="acc-01")
    assert created.ref.transaction_id != derive_transaction_id(created.transaction.raw)

    with ports() as edit_ports:
        noted = update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=created.ref.transaction_id,
            patch=ManualLedgerTransactionPatch(notes="monthly"),
            actor="operator",
            source_command="aeat app ledger update",
            ports=edit_ports,
            occurred_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
        )
    assert noted.transaction.own_account_id == "acc-01"
    assert noted.ref.transaction_id == created.ref.transaction_id

    with ports() as move_ports:
        moved = update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=noted.ref.transaction_id,
            patch=ManualLedgerTransactionPatch(own_account_id="acc-02"),
            actor="operator",
            source_command="aeat app ledger update",
            ports=move_ports,
            occurred_at=datetime(2026, 5, 3, 8, 0, tzinfo=UTC),
        )
    assert moved.transaction.own_account_id == "acc-02"
    assert moved.ref.transaction_id == derive_transaction_id(moved.transaction.raw, own_account_id="acc-02")

    stored = transaction_repository.load()
    assert set(stored.transactions) == {moved.ref.transaction_id}
    assert stored.transactions[moved.ref.transaction_id].own_account_id == "acc-02"


def test_an_unbound_add_keeps_the_unbound_id(secure_objects: SecureObjectRepository) -> None:
    """A row added without an account derives exactly the id it always had."""
    transaction_repository, event_repository = _repositories(secure_objects)
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        created = create_manual_transaction(
            _command(),
            ports=ports,
            occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
        )

    assert created.transaction.own_account_id is None
    assert created.ref.transaction_id == derive_transaction_id(created.transaction.raw)
