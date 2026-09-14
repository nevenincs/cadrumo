"""Manual ledger transaction application tests split by workflow."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.action_ports import LedgerActionPorts
from cadrumo.application.ledger.actions_lifecycle import stash_manual_transaction
from cadrumo.application.ledger.actions_manual import (
    create_manual_transaction,
    get_manual_transaction,
    list_manual_transactions,
    summarize_manual_transactions,
)
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand
from cadrumo.application.ledger.review_projection import ledger_transaction_review_status
from cadrumo.core.period import Period
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.errors import TransactionNotFoundError

from .ledger_action_create_support import ledger_ports_for_test
from .ledger_action_persistence_support import (
    _BUCKET_ID,
    _OTHER_BUCKET_ID,
    _repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["secure_objects"]


def _ledger_ports(
    transaction_repository: TransactionCatalogueRepository,
    event_repository: BucketEventHistoryRepository,
    *,
    bucket_id: str,
) -> LedgerActionPorts:
    """Compose canonical ledger ports over the isolated repositories."""
    return cast(
        LedgerActionPorts,
        ledger_ports_for_test(
            bucket_id=bucket_id,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
        ),
    )


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
        ports=_ledger_ports(repo_a, event_repo, bucket_id=_BUCKET_ID),
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
        ports=_ledger_ports(repo_b, event_repo_b, bucket_id=_OTHER_BUCKET_ID),
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    bucket_ports = _ledger_ports(repo_a, event_repo, bucket_id=_BUCKET_ID)
    listed = list_manual_transactions(bucket_id=_BUCKET_ID, ports=bucket_ports)
    fetched = get_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=first.ref.transaction_id,
        ports=bucket_ports,
    )

    assert [item.ref.transaction_id for item in listed] == [first.ref.transaction_id]
    assert fetched.transaction.raw.description == "first bucket row"
    with pytest.raises(TransactionNotFoundError):
        get_manual_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id="0" * 64,
            ports=bucket_ports,
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
        ports=_ledger_ports(transaction_repository, event_repository, bucket_id=_BUCKET_ID),
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
        ports=_ledger_ports(transaction_repository, event_repository, bucket_id=_BUCKET_ID),
        occurred_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
    )
    stash_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=pending.ref.transaction_id,
        actor="operator-A",
        ports=_ledger_ports(transaction_repository, event_repository, bucket_id=_BUCKET_ID),
        occurred_at=datetime(2026, 5, 3, 8, 0, tzinfo=UTC),
    )

    report = summarize_manual_transactions(
        bucket_id=_BUCKET_ID,
        period=Period.from_year_and_code(2026, "05"),
        ports=_ledger_ports(transaction_repository, event_repository, bucket_id=_BUCKET_ID),
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
