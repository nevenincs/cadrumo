"""Ledger review-row query tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.actions_manual import create_manual_transaction, query_ledger_review_rows
from cadrumo.application.ledger.models import LedgerReviewQuery, ManualLedgerTransactionCommand
from cadrumo.core.period import Period
from cadrumo.domain.transactions.enums import TransactionDirection

from .ledger_action_create_support import ledger_ports_for_test
from .ledger_action_persistence_support import (
    _BUCKET_ID,
    _repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_query_ledger_review_rows_filters_exact_period_and_projects_rows(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects, bucket_id=_BUCKET_ID)
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        may = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 1),
                amount=Decimal("25.00"),
                direction=TransactionDirection.OUTGOING,
                counterparty="Vendor SL",
                description="may row",
                idempotency_key="review-may",
            ),
            ports=ports,
            occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
        )
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 6, 1),
                amount=Decimal("25.00"),
                direction=TransactionDirection.OUTGOING,
                counterparty="Vendor SL",
                description="june row",
                idempotency_key="review-june",
            ),
            ports=ports,
            occurred_at=datetime(2026, 6, 1, 8, 0, tzinfo=UTC),
        )

        listed = query_ledger_review_rows(
            LedgerReviewQuery(bucket_id=_BUCKET_ID, period=Period.from_year_and_code(2026, "05"), status="pending"),
            ports=ports,
        )
        single = query_ledger_review_rows(
            LedgerReviewQuery(bucket_id=_BUCKET_ID, transaction_id=may.ref.transaction_id),
            ports=ports,
        )
        single_filtered_out = query_ledger_review_rows(
            LedgerReviewQuery(
                bucket_id=_BUCKET_ID,
                period=Period.from_year_and_code(2026, "06"),
                transaction_id=may.ref.transaction_id,
            ),
            ports=ports,
        )

    assert [row.description for row in listed.rows] == ["may row"]
    assert listed.filters == ("period=2026 05", "status=pending")
    assert single.rows[0].id == may.ref.transaction_id
    assert single.rows[0].transaction is not None
    assert single_filtered_out.rows == ()


def test_query_ledger_review_rows_filters_by_direction(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects, bucket_id=_BUCKET_ID)
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 1),
                amount=Decimal("250.00"),
                direction=TransactionDirection.INCOMING,
                description="client payment",
                idempotency_key="dir-incoming",
            ),
            ports=ports,
            occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
        )
        expense = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 2),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description="material oficina",
                idempotency_key="dir-outgoing",
            ),
            ports=ports,
            occurred_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
        )

        full = query_ledger_review_rows(
            LedgerReviewQuery(bucket_id=_BUCKET_ID),
            ports=ports,
        )
        outgoing = query_ledger_review_rows(
            LedgerReviewQuery(bucket_id=_BUCKET_ID, direction=TransactionDirection.OUTGOING.value),
            ports=ports,
        )

    assert len(full.rows) == 2
    assert [row.id for row in outgoing.rows] == [expense.ref.transaction_id]
    assert outgoing.filters == ("direction=OUTGOING",)
