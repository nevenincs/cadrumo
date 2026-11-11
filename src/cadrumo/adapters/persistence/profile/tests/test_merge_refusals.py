"""Refusal paths for the merge_transactions action."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.actions_split_merge import merge_transactions, split_transaction
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand, SplitChildCommand
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.errors import TransactionValidationError

from .....application.ledger.tests.manual_transaction_support import create_manual_transaction
from .ledger_action_create_support import ledger_ports_for_test
from .merge_test_support import BUCKET_ID, repositories, split_setup

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_YEAR = filing_year_envelope().horizon


def test_merge_refuses_partial_cohort(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = repositories(secure_objects)
    # Split into 3 so supplying only 2 proves partial-cohort refusal.
    parent_command = ManualLedgerTransactionCommand(
        bucket_id=BUCKET_ID,
        booked_date=date(_YEAR, 5, 2),
        amount=Decimal("100.00"),
        direction=TransactionDirection.OUTGOING,
        counterparty="Vendor SL",
        description="materials",
        actor="operator-A",
    )
    with ledger_ports_for_test(
        bucket_id=BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        parent = create_manual_transaction(
            parent_command,
            ports=ports,
            occurred_at=datetime(_YEAR, 5, 4, 9, 30, tzinfo=UTC),
        )
    with ledger_ports_for_test(
        bucket_id=BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        split = split_transaction(
            bucket_id=BUCKET_ID,
            transaction_id=parent.ref.transaction_id,
            children=(
                SplitChildCommand(amount=Decimal("30.00"), description="slice-a"),
                SplitChildCommand(amount=Decimal("30.00"), description="slice-b"),
                SplitChildCommand(amount=Decimal("40.00"), description="slice-c"),
            ),
            actor="operator-A",
            ports=ports,
        )

    with (
        pytest.raises(TransactionValidationError, match="cohort is incomplete"),
        ledger_ports_for_test(
            bucket_id=BUCKET_ID,
            objects=secure_objects,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        ) as ports,
    ):
        merge_transactions(
            bucket_id=BUCKET_ID,
            child_transaction_ids=split.child_transaction_ids[:2],
            actor="operator-A",
            ports=ports,
        )


def test_merge_refuses_duplicate_child_ids(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = repositories(secure_objects)
    _parent_result, split = split_setup(secure_objects, transaction_repository, event_repository)
    duplicate = (split.child_transaction_ids[0], split.child_transaction_ids[0])

    with (
        pytest.raises(TransactionValidationError, match="must be unique"),
        ledger_ports_for_test(
            bucket_id=BUCKET_ID,
            objects=secure_objects,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        ) as ports,
    ):
        merge_transactions(
            bucket_id=BUCKET_ID,
            child_transaction_ids=duplicate,
            actor="operator-A",
            ports=ports,
        )


def test_merge_refuses_cross_group(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = repositories(secure_objects)
    _parent_a, split_a = split_setup(secure_objects, transaction_repository, event_repository)
    with ledger_ports_for_test(
        bucket_id=BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        second_parent = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=BUCKET_ID,
                booked_date=date(_YEAR, 5, 9),
                amount=Decimal("200.00"),
                direction=TransactionDirection.OUTGOING,
                counterparty="Other Vendor",
                description="other materials",
                actor="operator-A",
            ),
            ports=ports,
            occurred_at=datetime(_YEAR, 5, 9, 9, 30, tzinfo=UTC),
        )
    with ledger_ports_for_test(
        bucket_id=BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        split_b = split_transaction(
            bucket_id=BUCKET_ID,
            transaction_id=second_parent.ref.transaction_id,
            children=(
                SplitChildCommand(amount=Decimal("120.00"), description="b1"),
                SplitChildCommand(amount=Decimal("80.00"), description="b2"),
            ),
            actor="operator-A",
            ports=ports,
        )
    with (
        pytest.raises(TransactionValidationError, match="one split_group_id"),
        ledger_ports_for_test(
            bucket_id=BUCKET_ID,
            objects=secure_objects,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        ) as ports,
    ):
        merge_transactions(
            bucket_id=BUCKET_ID,
            child_transaction_ids=(split_a.child_transaction_ids[0], split_b.child_transaction_ids[0]),
            actor="operator-A",
            ports=ports,
        )


def test_merge_refuses_single_child(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = repositories(secure_objects)
    _parent_result, split = split_setup(secure_objects, transaction_repository, event_repository)
    with (
        pytest.raises(TransactionValidationError, match="at least two child"),
        ledger_ports_for_test(
            bucket_id=BUCKET_ID,
            objects=secure_objects,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        ) as ports,
    ):
        merge_transactions(
            bucket_id=BUCKET_ID,
            child_transaction_ids=(split.child_transaction_ids[0],),
            actor="operator-A",
            ports=ports,
        )
