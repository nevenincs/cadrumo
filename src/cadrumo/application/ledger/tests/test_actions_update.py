"""Manual ledger transaction application tests split by workflow."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    POST_UPDATE_EVENT_PAYLOADS,
    PRESERVED_CREATE_AUDIT_FIELDS,
    UPDATED_FIELD_EXPECTATIONS,
    UTC,
    BucketEvent,
    BucketEventType,
    BusinessClassification,
    Decimal,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionResult,
    SecureObjectRepository,
    TransactionCatalogue,
    TransactionDirection,
    _repositories,
    create_manual_transaction,
    dataclass,
    date,
    datetime,
    update_manual_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True, slots=True)
class _UpdateManualOutcome:
    """Bundle returned by _drive_update_manual_transaction.

    Captures the create + update results, the post-update catalogue
    state, and the loaded bucket events for the focused tests to
    share without duplicating the two-command scenario.
    """

    created: ManualLedgerTransactionResult
    updated: ManualLedgerTransactionResult
    reloaded: TransactionCatalogue
    events: tuple[BucketEvent, ...]


def _drive_update_manual_transaction(secure_objects: SecureObjectRepository) -> _UpdateManualOutcome:
    """Run the canonical create -> update scenario and bundle the observable state."""
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="draft description",
            idempotency_key="cash-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    updated = update_manual_transaction(
        transaction_id=created.ref.transaction_id,
        command=ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("60.00"),
            direction=TransactionDirection.OUTGOING,
            description="corrected description",
            business_classification=BusinessClassification.MIXED,
            business_pct=Decimal("0.50"),
            notes="corrected cash amount",
            actor="operator-B",
            source_command="aeat app ledger update",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )
    reloaded = transaction_repository.load()
    events = tuple(event_repository.load().for_bucket(_BUCKET_ID))
    return _UpdateManualOutcome(created=created, updated=updated, reloaded=reloaded, events=events)


def test_update_manual_transaction_retires_previous_transaction_id_from_catalogue(
    secure_objects: SecureObjectRepository,
) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert outcome.created.ref.transaction_id not in outcome.reloaded.transactions


def test_update_manual_transaction_persists_replacement_transaction_id(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert outcome.updated.ref.transaction_id in outcome.reloaded.transactions


def test_update_manual_transaction_replaces_field(
    secure_objects: SecureObjectRepository,
) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    for attr_path, expected in UPDATED_FIELD_EXPECTATIONS:
        actual: object = outcome.updated.transaction
        for segment in attr_path.split("."):
            actual = getattr(actual, segment)
        assert actual == expected, attr_path


def test_update_manual_transaction_preserves_original_audit_field(
    secure_objects: SecureObjectRepository,
) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    for attr in PRESERVED_CREATE_AUDIT_FIELDS:
        assert getattr(outcome.updated.transaction, attr) == getattr(outcome.created.transaction, attr), attr


def test_update_manual_transaction_records_edit_lineage_entry(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    entry = outcome.updated.transaction.edit_lineage[-1]
    assert entry.previous_transaction_id == outcome.created.ref.transaction_id
    assert entry.actor == "operator-B"
    assert entry.source_command == "aeat app ledger update"
    assert entry.bucket_event_id == outcome.updated.bucket_event_ids[0]


def test_update_manual_transaction_emits_expected_event_chain(secure_objects: SecureObjectRepository) -> None:
    """The created event is chronologically first; the three same-instant
    update events (edit/classification/allocation) are tie-broken by
    content-addressed ``event_id`` per ``bucket_event_order_key``, so their
    relative order is not a meaningful contract — only membership is.
    """
    outcome = _drive_update_manual_transaction(secure_objects)
    assert outcome.events[0].event_type == BucketEventType.LEDGER_TRANSACTION_CREATED
    assert {event.event_type for event in outcome.events[1:]} == {
        BucketEventType.LEDGER_TRANSACTION_UPDATED,
        BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
        BucketEventType.LEDGER_TRANSACTION_ALLOCATED,
    }


def test_update_manual_transaction_links_update_events_to_result(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert {event.event_id for event in outcome.events[1:]} == set(outcome.updated.bucket_event_ids)


def test_update_manual_transaction_event_payload_marks_mutation_kind(
    secure_objects: SecureObjectRepository,
) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    events_by_type = {event.event_type: event for event in outcome.events}
    for event_type, payload_key, expected in POST_UPDATE_EVENT_PAYLOADS:
        assert events_by_type[event_type].payload[payload_key] == expected, (event_type, payload_key)


def test_update_manual_transaction_edit_event_references_previous_transaction(
    secure_objects: SecureObjectRepository,
) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert outcome.events[1].payload["previous_transaction_id"] == outcome.created.ref.transaction_id


def test_update_manual_transaction_post_update_events_target_new_transaction_id(
    secure_objects: SecureObjectRepository,
) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert {event.object_id for event in outcome.events[1:]} == {outcome.updated.ref.transaction_id}
