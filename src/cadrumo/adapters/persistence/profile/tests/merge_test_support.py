"""Shared real setup for merge transaction tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.actions_split_merge import split_transaction
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand, SplitChildCommand
from cadrumo.domain.transactions.enums import TransactionDirection

from .....application.ledger.tests.manual_transaction_support import create_manual_transaction
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .ledger_action_create_support import ledger_ports_for_test

_YEAR = filing_year_envelope().horizon

BUCKET_ID = "25252525-2525-4525-8525-252525252525"


def repositories(objects: SecureObjectRepository, *, bucket_id: str = BUCKET_ID):
    return (
        TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects),
        BucketEventHistoryRepository(objects=objects),
    )


def split_setup(
    objects: SecureObjectRepository,
    transaction_repository: TransactionCatalogueRepository,
    event_repository: BucketEventHistoryRepository,
    *,
    parent_amount: Decimal = Decimal("100.00"),
    direction: TransactionDirection = TransactionDirection.OUTGOING,
):
    parent_command = ManualLedgerTransactionCommand(
        bucket_id=BUCKET_ID,
        booked_date=date(_YEAR, 5, 2),
        amount=parent_amount,
        direction=direction,
        counterparty="Vendor SL",
        description="materials",
        actor="operator-A",
    )
    with ledger_ports_for_test(
        bucket_id=BUCKET_ID,
        objects=objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        parent = create_manual_transaction(
            parent_command,
            ports=ports,
            occurred_at=datetime(_YEAR, 5, 4, 9, 30, tzinfo=UTC),
        )
    half = parent_amount / Decimal("2")
    with ledger_ports_for_test(
        bucket_id=BUCKET_ID,
        objects=objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        split = split_transaction(
            bucket_id=BUCKET_ID,
            transaction_id=parent.ref.transaction_id,
            children=(
                SplitChildCommand(amount=half, description="business portion"),
                SplitChildCommand(amount=parent_amount - half, description="personal portion"),
            ),
            actor="operator-A",
            ports=ports,
            occurred_at=datetime(_YEAR, 5, 4, 10, 0, tzinfo=UTC),
        )
    return parent, split
