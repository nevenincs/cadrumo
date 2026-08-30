"""Ledger review-row query tests."""

from __future__ import annotations

import pytest

from ....core.period import Period
from ..actions_manual import create_manual_transaction, query_ledger_review_rows
from ..models import LedgerReviewQuery, ManualLedgerTransactionCommand
from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    Decimal,
    SecureObjectRepository,
    TransactionDirection,
    _repositories,
    date,
    datetime,
    secure_objects,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["secure_objects"]


def test_query_ledger_review_rows_filters_exact_period_and_projects_rows(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects, bucket_id=_BUCKET_ID)
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
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
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
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 6, 1, 8, 0, tzinfo=UTC),
    )

    listed = query_ledger_review_rows(
        LedgerReviewQuery(bucket_id=_BUCKET_ID, period=Period.from_year_and_code(2026, "05"), status="pending"),
        transaction_repository=transaction_repository,
    )
    single = query_ledger_review_rows(
        LedgerReviewQuery(bucket_id=_BUCKET_ID, transaction_id=may.ref.transaction_id),
        transaction_repository=transaction_repository,
    )
    single_filtered_out = query_ledger_review_rows(
        LedgerReviewQuery(
            bucket_id=_BUCKET_ID,
            period=Period.from_year_and_code(2026, "06"),
            transaction_id=may.ref.transaction_id,
        ),
        transaction_repository=transaction_repository,
    )

    assert [row.description for row in listed.rows] == ["may row"]
    assert listed.filters == ("period=2026 05", "status=pending")
    assert single.rows[0].id == may.ref.transaction_id
    assert single.rows[0].transaction is not None
    assert single_filtered_out.rows == ()


def test_query_ledger_review_rows_filters_by_direction(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects, bucket_id=_BUCKET_ID)
    create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("250.00"),
            direction=TransactionDirection.INCOMING,
            description="client payment",
            idempotency_key="dir-incoming",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
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
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
    )

    full = query_ledger_review_rows(
        LedgerReviewQuery(bucket_id=_BUCKET_ID),
        transaction_repository=transaction_repository,
    )
    outgoing = query_ledger_review_rows(
        LedgerReviewQuery(bucket_id=_BUCKET_ID, direction=TransactionDirection.OUTGOING.value),
        transaction_repository=transaction_repository,
    )

    assert len(full.rows) == 2
    assert [row.id for row in outgoing.rows] == [expense.ref.transaction_id]
    assert outgoing.filters == ("direction=OUTGOING",)
