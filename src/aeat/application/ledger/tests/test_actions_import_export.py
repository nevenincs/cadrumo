"""Manual ledger transaction application tests split by workflow."""

from __future__ import annotations

import json
import logging

import pytest

from ....domain.iva import EUMemberState, IvaCategory
from ._action_test_support import (
    _BUCKET_ID,
    _OTHER_BUCKET_ID,
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
    _repositories,
    create_manual_transaction,
    csv,
    date,
    datetime,
    export_ledger_transactions,
    import_ledger_source,
    import_ledger_transactions,
    parsed_import_transaction,
    stash_manual_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_import_ledger_transactions_persists_rows_and_emits_import_events(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    first_parsed = parsed_import_transaction()
    # A genuinely distinct movement: import dedup keys on the movement
    # identity (date + amount + normalised narrative), so the second
    # row must differ in one of those — not merely in the provider id.
    second_parsed = parsed_import_transaction(
        transaction_id="provider-row-2",
        amount=Decimal("48.40"),
        description="second provider import row",
    )

    first_import = import_ledger_transactions(
        bucket_id=_BUCKET_ID,
        parsed_rows=(first_parsed, second_parsed),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        actor="operator-A",
        source_command="aeat app ledger import",
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    duplicate_import = import_ledger_transactions(
        bucket_id=_BUCKET_ID,
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
        sorted(ref.transaction_id for ref in first_import.summary.imported_refs),
    )
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_IMPORTED,
        BucketEventType.LEDGER_TRANSACTION_IMPORTED,
    ]
    assert {event.object_id for event in events} == {ref.transaction_id for ref in first_import.summary.imported_refs}
    assert all(event.object_type is BucketEventObjectType.LEDGER_TRANSACTION for event in events)
    assert {event.payload["source_row_index"] for event in events} == {"1"}
    assert {event.payload["provider_name"] for event in events} == {"CSV provider"}


def test_import_keeps_genuine_intrabatch_twins_with_distinct_ids(
    secure_objects: SecureObjectRepository,
) -> None:
    """Two genuine same-day/same-amount/same-narrative movements in ONE statement
    carry distinct provider row ids (``synthesize_transaction_id`` embeds the
    source row index), so both must import — collapsing them on the coarser
    import fingerprint (date + amount + narrative) silently drops a real movement
    and under-declares the return. Re-importing the same rows still dedups against
    the persisted catalogue. Regression for the intra-batch fingerprint skip."""
    transaction_repository, event_repository = _repositories(secure_objects)
    twin_a = parsed_import_transaction(
        transaction_id="provider-row-1",
        amount=Decimal("605.00"),
        description="Cobro factura recurrente",
    )
    twin_b = parsed_import_transaction(
        transaction_id="provider-row-2",
        amount=Decimal("605.00"),
        description="Cobro factura recurrente",
    )

    first = import_ledger_transactions(
        bucket_id=_BUCKET_ID,
        parsed_rows=(twin_a, twin_b),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        actor="operator-A",
        occurred_at=datetime(2026, 6, 7, 9, 0, tzinfo=UTC),
    )
    assert first.summary.imported == 2
    assert first.summary.skipped == 0
    assert len(transaction_repository.load().transactions) == 2

    second = import_ledger_transactions(
        bucket_id=_BUCKET_ID,
        parsed_rows=(twin_a, twin_b),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        actor="operator-A",
        occurred_at=datetime(2026, 6, 7, 9, 5, tzinfo=UTC),
    )
    assert second.summary.imported == 0
    assert second.summary.skipped == 2
    assert len(transaction_repository.load().transactions) == 2


def test_import_skips_true_transaction_id_collision_within_batch(
    secure_objects: SecureObjectRepository,
) -> None:
    """Two rows resolving to the SAME content transaction id (identical provider
    id + date + amount + narrative) cannot both persist — the catalogue keys on
    that id and the later would overwrite the earlier — so the later is skipped to
    keep the imported and stored counts consistent."""
    transaction_repository, event_repository = _repositories(secure_objects)
    row = parsed_import_transaction(
        transaction_id="same-provider-id",
        amount=Decimal("605.00"),
        description="Cobro factura recurrente",
    )

    result = import_ledger_transactions(
        bucket_id=_BUCKET_ID,
        parsed_rows=(row, row),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        actor="operator-A",
        occurred_at=datetime(2026, 6, 7, 9, 0, tzinfo=UTC),
    )
    assert result.summary.imported == 1
    assert result.summary.skipped == 1
    assert len(transaction_repository.load().transactions) == 1


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
        LedgerSourceImportCommand(bucket_id=_BUCKET_ID, path=statement, provider="csv", actor="operator-A"),
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
    assert persisted.bucket_id == _BUCKET_ID
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


@pytest.mark.parametrize("export_format", [ExportSerializationFormat.CSV, ExportSerializationFormat.JSONL])
def test_import_ledger_source_honors_explicit_direction_column_on_positive_amount_in_exports(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    export_format: ExportSerializationFormat,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    statement = tmp_path / "explicit-direction.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID,direction,source_jurisdiction\n"
        "2026-04-17,French Vendor,FR expense,48.40,EUR,n26-fr-expense,OUTGOING,FR\n",
        encoding="utf-8",
    )

    imported = import_ledger_source(
        LedgerSourceImportCommand(bucket_id=_BUCKET_ID, path=statement, provider="csv", actor="operator-A"),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    exported = export_ledger_transactions(
        LedgerExportCommand(bucket_id=_BUCKET_ID, export_format=export_format),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )

    assert imported.imported == 1
    (stored,) = transaction_repository.load().values()
    assert stored.raw.amount == Decimal("48.40")
    assert stored.direction is TransactionDirection.OUTGOING
    assert stored.source_jurisdiction == "FR"
    if export_format == ExportSerializationFormat.CSV:
        rows = tuple(csv.DictReader(StringIO(exported.payload.decode("utf-8"))))
    else:
        rows = tuple(json.loads(line) for line in exported.payload.decode("utf-8").splitlines() if line.strip())
    assert len(rows) == 1
    (row,) = rows
    assert row["amount"] == "48.40"
    assert row["direction"] == "OUTGOING"
    assert row["source_jurisdiction"] == "FR"


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
    assert "zero amount" in str((exc_info.value.context or {}).get("reason", ""))


def test_import_outgoing_magnitude_row_stores_positive_with_outgoing_direction(
    secure_objects: SecureObjectRepository,
) -> None:
    """An OUTGOING parsed row stores a positive magnitude with direction=OUTGOING."""
    transaction_repository, event_repository = _repositories(secure_objects)
    parsed = parsed_import_transaction(
        transaction_id="out-row-1",
        amount=Decimal("48.40"),
        description="SaaS subscription",
        direction=TransactionDirection.OUTGOING,
    )
    result = import_ledger_transactions(
        bucket_id=_BUCKET_ID,
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
    parsed = parsed_import_transaction(
        transaction_id="transfer-row-1",
        amount=Decimal("5000.00"),
        description="Traspaso a cuenta de ahorro",
        direction=TransactionDirection.INTERNAL_TRANSFER,
    )
    result = import_ledger_transactions(
        bucket_id=_BUCKET_ID,
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


def test_import_ledger_source_auto_missing_file_is_clean_refusal_without_probe_noise(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``--provider auto`` on a missing file refuses cleanly without probe noise.

    Regression guard for audit finding m1: a non-existent path with
    ``provider="auto"`` previously ran the format-detection probe loop
    before the existence check, dumping a raw ``FileNotFoundError``
    traceback and spurious provider-probe ``ERROR`` log lines (the OFX and
    PDF parsers) before finally raising the auto-detection failure. The fix
    refuses up front with the path-naming ``source_file_not_found`` typed
    error, and the detection probe loop never runs, so no provider emits an
    ERROR-level probe-failure record.
    """
    from ....core.errors import resolve_error_message

    missing = tmp_path / "no-such-statement.csv"
    with (
        caplog.at_level("ERROR", logger="aeat.adapters.inbound.financial.providers"),
        pytest.raises(TransactionValidationError) as excinfo,
    ):
        import_ledger_source(
            LedgerSourceImportCommand(path=missing, provider="auto", dry_run=True),
        )

    error = excinfo.value
    # The refusal names the missing path; it is NOT the downstream
    # "auto-detection of ledger format failed" error the probe loop raised.
    assert error.translated_message == "errors.financial.source_file_not_found"
    assert error.context == {"path": str(missing)}
    rendered = resolve_error_message(error)
    assert str(missing) in rendered
    assert "auto-detection" not in rendered
    # No provider-probe ERROR records leaked to the operator-facing log.
    probe_errors = [
        record
        for record in caplog.records
        if record.levelno >= logging.ERROR and record.name.startswith("aeat.adapters.inbound.financial.providers")
    ]
    assert probe_errors == []


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
def test_export_ledger_transactions_serializes_iva_category_and_counterparty_eu_member_state(
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
            counterparty_eu_member_state=EUMemberState.DE,
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
        assert "counterparty_eu_member_state" in (reader.fieldnames or ())
        rows = tuple(reader)
    else:
        rows = tuple(json.loads(line) for line in text.splitlines() if line.strip())
        assert rows
        assert "iva_category" in rows[0]
        assert "counterparty_eu_member_state" in rows[0]

    assert len(rows) == 1
    assert rows[0]["transaction_id"] == created.ref.transaction_id
    assert rows[0]["iva_category"] == IvaCategory.INTRA_COMMUNITY_SUPPLY.value
    assert rows[0]["counterparty_eu_member_state"] == EUMemberState.DE.value


def test_export_ledger_transactions_excludes_inactive_rows_by_default(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    active = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
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
            bucket_id=_BUCKET_ID,
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
        bucket_id=_BUCKET_ID,
        transaction_id=inactive.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 9, 0, tzinfo=UTC),
    )

    active_only = export_ledger_transactions(
        LedgerExportCommand(bucket_id=_BUCKET_ID),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )
    with_inactive = export_ledger_transactions(
        LedgerExportCommand(bucket_id=_BUCKET_ID, include_inactive=True),
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
