"""Manual ledger transaction application tests split by workflow."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    UTC,
    BucketEventObjectType,
    BucketEventType,
    BusinessClassification,
    Decimal,
    ExportSerializationFormat,
    LedgerExportCommand,
    LedgerSourceImportCommand,
    ManualLedgerTransactionCommand,
    Path,
    SecureObjectRepository,
    StringIO,
    TransactionDirection,
    TransactionValidationError,
    _parsed_import_transaction,
    _raw_import_transaction,
    _repositories,
    create_manual_transaction,
    csv,
    date,
    datetime,
    export_ledger_transactions,
    import_ledger_source,
    import_ledger_transactions,
    stash_manual_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_import_ledger_transactions_persists_rows_and_emits_import_events(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    first_parsed = _parsed_import_transaction()
    # A genuinely distinct movement: import dedup keys on the movement
    # identity (date + amount + normalised narrative), so the second
    # row must differ in one of those — not merely in the provider id.
    second_parsed = _parsed_import_transaction(
        transaction_id="provider-row-2",
        amount=Decimal("48.40"),
        description="second provider import row",
    )

    first_import = import_ledger_transactions(
        bucket_id="bucket-a",
        parsed_rows=(first_parsed, second_parsed),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        actor="operator-A",
        source_command="aeat app ledger import",
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    duplicate_import = import_ledger_transactions(
        bucket_id="bucket-a",
        parsed_rows=(first_parsed,),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        actor="operator-A",
        source_command="aeat app ledger import",
        occurred_at=datetime(2026, 5, 4, 9, 31, tzinfo=UTC),
    )

    assert first_import.summary.imported == 2
    assert first_import.summary.skipped == 0
    assert len(first_import.bucket_event_ids) == 2
    assert duplicate_import.summary.imported == 0
    assert duplicate_import.summary.skipped == 1
    assert duplicate_import.bucket_event_ids == ()
    persisted = transaction_repository.load()
    assert tuple(sorted(persisted.transactions)) == tuple(
        sorted(ref.transaction_id for ref in first_import.summary.imported_refs)
    )
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_IMPORTED,
        BucketEventType.LEDGER_TRANSACTION_IMPORTED,
    ]
    assert {event.object_id for event in events} == {ref.transaction_id for ref in first_import.summary.imported_refs}
    assert all(event.object_type is BucketEventObjectType.LEDGER_TRANSACTION for event in events)
    assert {event.payload["source_row_index"] for event in events} == {"1"}
    assert {event.payload["provider_name"] for event in events} == {"CSV provider"}


def test_import_ledger_source_owns_provider_validation_ingest_and_persistence(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    statement = tmp_path / "bank.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n"
        "2026-04-16,SaaS Vendor,Subscription,-48.40,EUR,n26-002\n",
        encoding="utf-8",
    )

    dry_run = import_ledger_source(
        LedgerSourceImportCommand(path=statement, provider="csv", dry_run=True, verify=True, source=statement),
    )
    persisted = import_ledger_source(
        LedgerSourceImportCommand(bucket_id="bucket-a", path=statement, provider="csv", actor="operator-A"),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )

    assert dry_run.dry_run is True
    assert dry_run.rows == 2
    # A dry run previews the real outcome: against an empty catalogue
    # both parsed rows would be imported. A flat zero was the defect.
    assert dry_run.imported == 2
    assert dry_run.skipped == 0
    assert dry_run.source.sha256 is not None
    assert persisted.bucket_id == "bucket-a"
    assert persisted.imported == 2
    assert persisted.skipped == 0
    assert persisted.import_batch_id is not None
    assert dry_run.diagnostics
    assert len(persisted.imported_transaction_refs) == 2
    assert len(persisted.bucket_event_ids) == 2
    assert len(transaction_repository.load().transactions) == 2
    # The signed CSV columns map to magnitudes + authoritative direction at the
    # parse boundary: the +121.00 row is INCOMING, the -48.40 row is OUTGOING,
    # and both amounts are stored as non-negative magnitudes.
    stored = sorted(transaction_repository.load().values(), key=lambda tx: tx.raw.amount)
    assert [tx.raw.amount for tx in stored] == [Decimal("48.40"), Decimal("121.00")]
    assert stored[0].direction is TransactionDirection.OUTGOING
    assert stored[1].direction is TransactionDirection.INCOMING


def test_import_rejects_zero_amount_row_at_parse_boundary(tmp_path: Path) -> None:
    """A zero-amount source row is refused at the parse boundary, like the manual path."""
    statement = tmp_path / "bank-zero.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,0.00,EUR,n26-zero\n",
        encoding="utf-8",
    )
    with pytest.raises(TransactionValidationError) as exc_info:
        import_ledger_source(
            LedgerSourceImportCommand(path=statement, provider="csv", dry_run=True),
        )
    assert exc_info.value.translated_message == "errors.transaction.ledger_import_failed"
    assert "zero amount" in (exc_info.value.context or {}).get("reason", "")


def test_import_outgoing_magnitude_row_stores_positive_with_outgoing_direction(
    secure_objects: SecureObjectRepository,
) -> None:
    """An OUTGOING parsed row stores a positive magnitude with direction=OUTGOING."""
    transaction_repository, event_repository = _repositories(secure_objects)
    parsed = _parsed_import_transaction(
        transaction_id="out-row-1",
        amount=Decimal("48.40"),
        description="SaaS subscription",
        direction=TransactionDirection.OUTGOING,
    )
    result = import_ledger_transactions(
        bucket_id="bucket-a",
        parsed_rows=(parsed,),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    assert result.summary.imported == 1
    (stored,) = transaction_repository.load().values()
    assert stored.raw.amount == Decimal("48.40")
    assert stored.direction is TransactionDirection.OUTGOING


def test_import_internal_transfer_row_stores_magnitude_with_transfer_direction(
    secure_objects: SecureObjectRepository,
) -> None:
    """An INTERNAL_TRANSFER parsed row stores an absolute magnitude with that direction.

    The adapter contract (``ParsedLedgerRow``) carries any
    :class:`TransactionDirection`, so a transfer between the taxpayer's own
    accounts rides through import as a magnitude paired with
    ``direction=INTERNAL_TRANSFER``.
    """
    transaction_repository, event_repository = _repositories(secure_objects)
    parsed = _parsed_import_transaction(
        transaction_id="transfer-row-1",
        amount=Decimal("5000.00"),
        description="Traspaso a cuenta de ahorro",
        direction=TransactionDirection.INTERNAL_TRANSFER,
    )
    result = import_ledger_transactions(
        bucket_id="bucket-a",
        parsed_rows=(parsed,),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    assert result.summary.imported == 1
    (stored,) = transaction_repository.load().values()
    assert stored.raw.amount == Decimal("5000.00")
    assert stored.direction is TransactionDirection.INTERNAL_TRANSFER


def test_import_ledger_source_missing_file_raises_localised_error(tmp_path: Path) -> None:
    """A missing source file raises a tr()-localised error, not naked English.

    Regression guard for the CLI persona testimonial finding: the ledger
    import error must carry the ``translated_message`` tr-key and render
    in the operator's locale (Spanish by default), not a hardcoded
    English sentence.
    """
    from ....core.errors import resolve_error_message

    missing = tmp_path / "no-such-statement.csv"
    with pytest.raises(TransactionValidationError) as excinfo:
        import_ledger_source(
            LedgerSourceImportCommand(path=missing, provider="csv", dry_run=True, verify=False, source=missing),
        )

    error = excinfo.value
    assert error.translated_message == "errors.financial.source_file_not_found"
    assert error.context == {"path": str(missing)}
    rendered = resolve_error_message(error)
    assert "El archivo de origen no existe" in rendered
    assert str(missing) in rendered


def test_export_ledger_transactions_serializes_active_bucket_rows_and_emits_event(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    first = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
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
            bucket_id="bucket-a",
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
            bucket_id="bucket-a",
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
    events = event_repository.load().for_bucket("bucket-a")
    assert events[-1].event_type is BucketEventType.LEDGER_TRANSACTION_EXPORTED
    assert events[-1].object_type is BucketEventObjectType.LEDGER_EXPORT
    assert events[-1].object_id == result.export_id
    assert events[-1].payload["row_count"] == "2"
    assert events[-1].payload["sha256"] == result.sha256
    assert events[-1].payload["first_transaction_id"] == second.ref.transaction_id
    assert events[-1].payload["last_transaction_id"] == first.ref.transaction_id
    assert len(events[-1].payload["transaction_ids_sha256"]) == 64


def test_export_ledger_transactions_excludes_inactive_rows_by_default(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    active = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("250.00"),
            direction=TransactionDirection.INCOMING,
            description="client payment",
            idempotency_key="export-active",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    inactive = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("25.00"),
            direction=TransactionDirection.OUTGOING,
            description="stashed payment",
            idempotency_key="export-inactive",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 31, tzinfo=UTC),
    )
    stash_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=inactive.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 9, 0, tzinfo=UTC),
    )

    active_only = export_ledger_transactions(
        LedgerExportCommand(bucket_id="bucket-a"),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )
    with_inactive = export_ledger_transactions(
        LedgerExportCommand(bucket_id="bucket-a", include_inactive=True),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 1, tzinfo=UTC),
    )

    assert tuple(row.transaction_id for row in active_only.rows) == (active.ref.transaction_id,)
    assert tuple(row.transaction_id for row in with_inactive.rows) == (
        active.ref.transaction_id,
        inactive.ref.transaction_id,
    )
    assert with_inactive.rows[1].lifecycle_state == "STASHED"


def test_export_ledger_transactions_event_payload_stays_bounded_for_large_exports(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    for index in range(12):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
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
        LedgerExportCommand(bucket_id="bucket-a"),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert result.row_count == 12
    event = event_repository.load().for_bucket("bucket-a")[-1]
    assert event.event_type is BucketEventType.LEDGER_TRANSACTION_EXPORTED
    assert "transaction_ids" not in event.payload
    assert event.payload["row_count"] == "12"
    assert len(event.payload["transaction_ids_sha256"]) == 64
    assert all(len(value) <= 500 for value in event.payload.values())


def test_export_ledger_transactions_reads_requested_bucket_only(secure_objects: SecureObjectRepository) -> None:
    repo_a, event_repo_a = _repositories(secure_objects, bucket_id="bucket-a")
    repo_b, event_repo_b = _repositories(secure_objects, bucket_id="bucket-b")
    first = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
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
            bucket_id="bucket-b",
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
        LedgerExportCommand(bucket_id="bucket-a", export_format=ExportSerializationFormat.JSONL),
        transaction_repository=repo_a,
        bucket_event_repository=event_repo_a,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert result.row_count == 1
    assert result.rows[0].bucket_id == "bucket-a"
    assert result.rows[0].transaction_id == first.ref.transaction_id
    assert b"bucket b row" not in result.payload
    assert [event.event_type for event in event_repo_b.load().for_bucket("bucket-b")] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED
    ]


def test_export_ledger_transactions_writes_output_before_export_event(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
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
            LedgerExportCommand(bucket_id="bucket-a", output_path=tmp_path),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
        )

    assert [event.event_type for event in event_repository.load().for_bucket("bucket-a")] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED
    ]
