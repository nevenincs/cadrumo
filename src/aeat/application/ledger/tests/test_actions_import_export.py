"""Manual ledger transaction application tests split by workflow."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    BucketEventObjectType,
    BucketEventType,
    Decimal,
    LedgerSourceImportCommand,
    Path,
    SecureObjectRepository,
    TransactionDirection,
    _repositories,
    datetime,
    import_ledger_source,
    import_ledger_transactions,
    parsed_import_transaction,
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



