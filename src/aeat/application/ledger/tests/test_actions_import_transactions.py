"""Parsed-row ledger import tests."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    BucketEventObjectType,
    BucketEventType,
    Decimal,
    SecureObjectRepository,
    _repositories,
    datetime,
    import_ledger_transactions,
    parsed_import_transaction,
)
from ._action_test_support import secure_objects as secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["secure_objects"]


def test_import_ledger_transactions_persists_rows_and_emits_import_events(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    first_parsed = parsed_import_transaction()
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
