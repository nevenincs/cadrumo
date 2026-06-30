"""Ledger review-row query tests."""

from __future__ import annotations

import pytest

from ....core import Period
from ....domain.buckets import BucketEventType
from .. import (
    LedgerReviewQuery,
    LedgerSourceImportCommand,
    ManualLedgerTransactionCommand,
    create_manual_transaction,
    import_ledger_source,
    query_ledger_review_rows,
)
from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    Decimal,
    Path,
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


def test_query_ledger_review_rows_filters_quarter_import_and_issue_events(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects, bucket_id=_BUCKET_ID)
    statement = tmp_path / "bank.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n"
        "2026-06-16,SaaS Vendor,Subscription,-48.40,EUR,n26-002\n",
        encoding="utf-8",
    )

    first_import = import_ledger_source(
        LedgerSourceImportCommand(
            bucket_id=_BUCKET_ID,
            path=statement,
            provider="csv",
            verify=True,
            source=statement,
            actor="operator-A",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    duplicate_import = import_ledger_source(
        LedgerSourceImportCommand(
            bucket_id=_BUCKET_ID,
            path=statement,
            provider="csv",
            verify=True,
            actor="operator-A",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )

    assert first_import.import_batch_id is not None
    assert duplicate_import.import_batch_id is not None
    assert first_import.imported == 2
    assert duplicate_import.skipped == 2
    assert {diagnostic.kind for diagnostic in duplicate_import.diagnostics} == {"duplicate", "gap"}
    assert BucketEventType.LEDGER_IMPORT_DIAGNOSTIC_RECORDED in {
        event.event_type for event in event_repository.load().for_bucket(_BUCKET_ID)
    }

    quarter_rows = query_ledger_review_rows(
        LedgerReviewQuery(bucket_id=_BUCKET_ID, period=Period.from_year_and_code(2026, "2T")),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    imported_rows = query_ledger_review_rows(
        LedgerReviewQuery(bucket_id=_BUCKET_ID, import_id=first_import.import_batch_id),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    duplicate_rows = query_ledger_review_rows(
        LedgerReviewQuery(bucket_id=_BUCKET_ID, issue="duplicate", import_id=duplicate_import.import_batch_id),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    gap_rows = query_ledger_review_rows(
        LedgerReviewQuery(bucket_id=_BUCKET_ID, issue="gap", import_id=first_import.import_batch_id),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )

    assert [row.description for row in quarter_rows.rows] == ["Invoice 1", "Subscription"]
    assert [row.description for row in imported_rows.rows] == ["Invoice 1", "Subscription"]
    assert [row.description for row in duplicate_rows.rows] == ["Invoice 1", "Subscription"]
    assert [row.description for row in gap_rows.rows] == ["Invoice 1", "Subscription"]
    assert duplicate_rows.filters == (
        "issue=duplicate",
        f"import={duplicate_import.import_batch_id}",
    )
