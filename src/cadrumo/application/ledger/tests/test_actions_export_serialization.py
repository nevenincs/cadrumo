"""Manual ledger export serialization tests."""

from __future__ import annotations

import json

import pytest

from ....domain.iva.schema import IvaCategory
from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    BucketEventObjectType,
    BucketEventType,
    BusinessClassification,
    Decimal,
    ExportSerializationFormat,
    LedgerExportCommand,
    ManualLedgerTransactionCommand,
    SecureObjectRepository,
    StringIO,
    TransactionDirection,
    _repositories,
    create_manual_transaction,
    csv,
    date,
    datetime,
    export_ledger_transactions,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_export_ledger_transactions_serializes_active_bucket_rows_and_emits_event(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    first = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 2),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("21.00"),
            idempotency_key="export-first",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    second = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("250.00"),
            direction=TransactionDirection.INCOMING,
            description="client payment",
            business_classification=BusinessClassification.BUSINESS,
            idempotency_key="export-second",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 31, tzinfo=UTC),
    )

    result = export_ledger_transactions(
        LedgerExportCommand(
            bucket_id=_BUCKET_ID,
            export_format=ExportSerializationFormat.CSV,
            actor="operator-A",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    parsed = tuple(csv.DictReader(StringIO(result.payload.decode("utf-8"))))
    assert result.row_count == 2
    assert result.media_type == "text/csv"
    assert result.byte_size == len(result.payload)
    assert len(result.sha256) == 64
    assert [row["transaction_id"] for row in parsed] == [second.ref.transaction_id, first.ref.transaction_id]
    assert parsed[1]["taxable_base"] == "100.00"
    assert parsed[1]["purchase_invoice_evidence_id"] == ""
    assert transaction_repository.load().get(first.ref.transaction_id) is not None
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert events[-1].event_type is BucketEventType.LEDGER_TRANSACTION_EXPORTED
    assert events[-1].object_type is BucketEventObjectType.LEDGER_EXPORT
    assert events[-1].object_id == result.export_id
    assert events[-1].payload["row_count"] == "2"
    assert events[-1].payload["sha256"] == result.sha256
    assert events[-1].payload["first_transaction_id"] == second.ref.transaction_id
    assert events[-1].payload["last_transaction_id"] == first.ref.transaction_id
    assert len(events[-1].payload["transaction_ids_sha256"]) == 64


@pytest.mark.parametrize("export_format", [ExportSerializationFormat.CSV, ExportSerializationFormat.JSONL])
def test_export_ledger_transactions_serializes_iva_category_and_counterparty_country(
    secure_objects: SecureObjectRepository,
    export_format: ExportSerializationFormat,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 6),
            amount=Decimal("1000.00"),
            direction=TransactionDirection.INCOMING,
            description="intracommunity client invoice",
            business_classification=BusinessClassification.BUSINESS,
            taxable_base=Decimal("1000.00"),
            iva_rate=Decimal("0.00"),
            iva_amount=Decimal("0.00"),
            iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
            counterparty_country="DE",
            idempotency_key="export-intracommunity",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 6, 9, 30, tzinfo=UTC),
    )

    exported = export_ledger_transactions(
        LedgerExportCommand(bucket_id=_BUCKET_ID, export_format=export_format),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 6, 10, 0, tzinfo=UTC),
    )
    text = exported.payload.decode("utf-8")
    if export_format is ExportSerializationFormat.CSV:
        reader = csv.DictReader(StringIO(text))
        assert "iva_category" in (reader.fieldnames or ())
        assert "counterparty_country" in (reader.fieldnames or ())
        rows = tuple(reader)
    else:
        rows = tuple(json.loads(line) for line in text.splitlines() if line.strip())
        assert rows
        assert "iva_category" in rows[0]
        assert "counterparty_country" in rows[0]

    assert len(rows) == 1
    assert rows[0]["transaction_id"] == created.ref.transaction_id
    assert rows[0]["iva_category"] == IvaCategory.INTRA_COMMUNITY_SUPPLY.value
    assert rows[0]["counterparty_country"] == "DE"
