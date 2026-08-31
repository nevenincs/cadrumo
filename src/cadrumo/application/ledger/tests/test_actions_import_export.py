"""Manual ledger transaction application tests split by workflow."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    Decimal,
    LedgerSourceImportCommand,
    Path,
    SecureObjectRepository,
    TransactionDirection,
    _repositories,
    import_ledger_source,
    import_ledger_transactions,
    parsed_import_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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
    # One file, so one report -- the field is a tuple because a DIRECTORY import
    # folds several and used to keep only the first.
    assert len(dry_run.sources) == 1
    assert dry_run.sources[0].sha256 is not None
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
