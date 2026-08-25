"""Manual ledger transaction application tests split by workflow."""

from __future__ import annotations

import pytest

from ....core import Period
from ....domain.transactions import TransactionNotFoundError
from ..actions_lifecycle import stash_manual_transaction
from ..actions_manual import (
    create_manual_transaction,
    get_manual_transaction,
    list_manual_transactions,
    summarize_manual_transactions,
)
from ..models import ManualLedgerTransactionCommand
from ..review_projection import ledger_transaction_review_status
from ._action_test_support import (
    _BUCKET_ID,
    _OTHER_BUCKET_ID,
    UTC,
    BusinessClassification,
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


def test_list_and_get_manual_transactions_read_the_requested_bucket_only(
    secure_objects: SecureObjectRepository,
) -> None:
    repo_a, event_repo = _repositories(secure_objects, bucket_id=_BUCKET_ID)
    repo_b, event_repo_b = _repositories(secure_objects, bucket_id=_OTHER_BUCKET_ID)
    first = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("25.00"),
            direction=TransactionDirection.OUTGOING,
            description="first bucket row",
            idempotency_key="first",
        ),
        transaction_repository=repo_a,
        bucket_event_repository=event_repo,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_OTHER_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("25.00"),
            direction=TransactionDirection.OUTGOING,
            description="other bucket row",
            idempotency_key="first",
        ),
        transaction_repository=repo_b,
        bucket_event_repository=event_repo_b,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    listed = list_manual_transactions(bucket_id=_BUCKET_ID, transaction_repository=repo_a)
    fetched = get_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=first.ref.transaction_id,
        transaction_repository=repo_a,
    )

    assert [item.ref.transaction_id for item in listed] == [first.ref.transaction_id]
    assert fetched.transaction.raw.description == "first bucket row"
    with pytest.raises(TransactionNotFoundError):
        get_manual_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id="0" * 64,
            transaction_repository=repo_a,
        )


def test_summarize_manual_transactions_reports_bucket_status_and_readiness(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects, bucket_id=_BUCKET_ID)
    ready = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="ready row",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("21.00"),
            idempotency_key="ready-status",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    pending = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 2),
            amount=Decimal("25.00"),
            direction=TransactionDirection.OUTGOING,
            description="pending row",
            idempotency_key="pending-status",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
    )
    stash_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=pending.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 3, 8, 0, tzinfo=UTC),
    )

    report = summarize_manual_transactions(
        bucket_id=_BUCKET_ID,
        period=Period.from_year_and_code(2026, "05"),
        transaction_repository=transaction_repository,
    )

    assert ledger_transaction_review_status(ready.transaction) == "reviewed"
    assert report.total_count == 2
    assert report.active_count == 1
    assert report.stashed_count == 1
    assert report.reviewed_count == 1
    assert report.pending_review_count == 0
    assert report.checked_transaction_count == 1
    assert report.readiness_issue_count == 0
    assert report.ready is True
