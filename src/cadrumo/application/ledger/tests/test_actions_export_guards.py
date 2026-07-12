"""Manual ledger export guard and failure-mode tests."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    _OTHER_BUCKET_ID,
    UTC,
    BucketEventType,
    Decimal,
    ExportSerializationFormat,
    LedgerExportCommand,
    ManualLedgerTransactionCommand,
    Path,
    SecureObjectRepository,
    TransactionDirection,
    _repositories,
    create_manual_transaction,
    date,
    datetime,
    export_ledger_transactions,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_export_ledger_transactions_event_payload_stays_bounded_for_large_exports(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    for index in range(12):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, index + 1),
                amount=Decimal("25.00"),
                direction=TransactionDirection.OUTGOING,
                description=f"export row {index:02d}",
                idempotency_key=f"export-bulk-{index:02d}",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    result = export_ledger_transactions(
        LedgerExportCommand(bucket_id=_BUCKET_ID),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert result.row_count == 12
    event = event_repository.load().for_bucket(_BUCKET_ID)[-1]
    assert event.event_type is BucketEventType.LEDGER_TRANSACTION_EXPORTED
    assert "transaction_ids" not in event.payload
    assert event.payload["row_count"] == "12"
    assert len(event.payload["transaction_ids_sha256"]) == 64
    assert all(len(value) <= 500 for value in event.payload.values())


def test_export_ledger_transactions_reads_requested_bucket_only(secure_objects: SecureObjectRepository) -> None:
    repo_a, event_repo_a = _repositories(secure_objects, bucket_id=_BUCKET_ID)
    repo_b, event_repo_b = _repositories(secure_objects, bucket_id=_OTHER_BUCKET_ID)
    first = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("25.00"),
            direction=TransactionDirection.OUTGOING,
            description="bucket a row",
            idempotency_key="shared-key",
        ),
        transaction_repository=repo_a,
        bucket_event_repository=event_repo_a,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_OTHER_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("25.00"),
            direction=TransactionDirection.OUTGOING,
            description="bucket b row",
            idempotency_key="shared-key",
        ),
        transaction_repository=repo_b,
        bucket_event_repository=event_repo_b,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )

    result = export_ledger_transactions(
        LedgerExportCommand(bucket_id=_BUCKET_ID, export_format=ExportSerializationFormat.JSONL),
        transaction_repository=repo_a,
        bucket_event_repository=event_repo_a,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert result.row_count == 1
    assert result.rows[0].bucket_id == _BUCKET_ID
    assert result.rows[0].transaction_id == first.ref.transaction_id
    assert b"bucket b row" not in result.payload
    assert [event.event_type for event in event_repo_b.load().for_bucket(_OTHER_BUCKET_ID)] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
    ]


def test_export_ledger_transactions_writes_output_before_export_event(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("25.00"),
            direction=TransactionDirection.OUTGOING,
            description="export row",
            idempotency_key="export-output-before-event",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    with pytest.raises(OSError):
        export_ledger_transactions(
            LedgerExportCommand(bucket_id=_BUCKET_ID, output_path=tmp_path),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
        )

    assert [event.event_type for event in event_repository.load().for_bucket(_BUCKET_ID)] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
    ]
