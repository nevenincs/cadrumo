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
    ManualLedgerTransactionPatch,
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
    update_manual_transaction_fields,
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


@pytest.mark.parametrize(("attr_path", "expected"), UPDATED_FIELD_EXPECTATIONS)
def test_update_manual_transaction_replaces_field(
    secure_objects: SecureObjectRepository,
    attr_path: str,
    expected: object,
) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    actual: object = outcome.updated.transaction
    for segment in attr_path.split("."):
        actual = getattr(actual, segment)
    assert actual == expected


@pytest.mark.parametrize("attr", PRESERVED_CREATE_AUDIT_FIELDS)
def test_update_manual_transaction_preserves_original_audit_field(
    secure_objects: SecureObjectRepository,
    attr: str,
) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert getattr(outcome.updated.transaction, attr) == getattr(outcome.created.transaction, attr)


def test_update_manual_transaction_records_edit_lineage_entry(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    entry = outcome.updated.transaction.edit_lineage[-1]
    assert entry.previous_transaction_id == outcome.created.ref.transaction_id
    assert entry.actor == "operator-B"
    assert entry.source_command == "aeat app ledger update"
    assert entry.bucket_event_id == outcome.updated.bucket_event_ids[0]


def test_update_manual_transaction_emits_expected_event_chain(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert [event.event_type for event in outcome.events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_UPDATED,
        BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
        BucketEventType.LEDGER_TRANSACTION_ALLOCATED,
    ]


def test_update_manual_transaction_links_update_events_to_result(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert [event.event_id for event in outcome.events[1:]] == list(outcome.updated.bucket_event_ids)


@pytest.mark.parametrize(("event_index", "payload_key", "expected"), POST_UPDATE_EVENT_PAYLOADS)
def test_update_manual_transaction_event_payload_marks_mutation_kind(
    secure_objects: SecureObjectRepository,
    event_index: int,
    payload_key: str,
    expected: str,
) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert outcome.events[event_index].payload[payload_key] == expected


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


def test_update_manual_transaction_fields_applies_typed_patch_through_backend(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("75.00"),
            direction=TransactionDirection.OUTGOING,
            description="pending row",
            idempotency_key="typed-patch",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    updated = update_manual_transaction_fields(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        patch=ManualLedgerTransactionPatch(
            description="classified row",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            # 75.00 gross inverse-split at 21% -> 61.98 base + 13.02 IVA
            # (keeps the gross == base + iva Transaction invariant).
            taxable_base=Decimal("61.98"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("13.02"),
        ),
        actor="operator-C",
        source_command="aeat app ledger classify",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert updated.transaction.raw.description == "classified row"
    assert updated.transaction.business_classification is BusinessClassification.BUSINESS
    assert updated.transaction.category_id == "office-supplies"
    assert updated.transaction.taxable_base == Decimal("61.98")
    assert updated.transaction.edit_lineage[-1].source_command == "aeat app ledger classify"
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_UPDATED,
        BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
    ]


def test_update_manual_transaction_fields_preserves_imported_source_jurisdiction(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 7, 15),
            amount=Decimal("250.00"),
            direction=TransactionDirection.OUTGOING,
            description="EU supplier statement row",
            source_jurisdiction="FR",
            idempotency_key="source-jurisdiction-classify",
            source_command="aeat app ledger import",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 7, 15, 8, 0, tzinfo=UTC),
    )

    updated = update_manual_transaction_fields(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        patch=ManualLedgerTransactionPatch(
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            taxable_base=Decimal("250.00"),
            iva_rate=Decimal("0"),
            iva_amount=Decimal("0"),
        ),
        actor="operator-C",
        source_command="aeat app ledger classify",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 7, 16, 10, 0, tzinfo=UTC),
    )

    assert created.transaction.source_jurisdiction == "FR"
    assert updated.transaction.source_jurisdiction == "FR"
    assert transaction_repository.load().transactions[updated.ref.transaction_id].source_jurisdiction == "FR"


def test_update_manual_transaction_fields_clears_tax_facts_for_personal_reclassification(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="office supplies",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("21.00"),
            irpf_category="activity-expense",
            prorrata_reference="iva-prorrata-2026",
            idempotency_key="personal-reclassification",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    updated = update_manual_transaction_fields(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        patch=ManualLedgerTransactionPatch(business_classification=BusinessClassification.PERSONAL),
        actor="operator-C",
        source_command="aeat app ledger classify",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert updated.transaction.business_classification is BusinessClassification.PERSONAL
    assert updated.transaction.business_pct is None
    assert updated.transaction.category_id is None
    assert updated.transaction.taxable_base is None
    assert updated.transaction.iva_rate is None
    assert updated.transaction.iva_amount is None
    assert updated.transaction.irpf_category is None
    assert updated.transaction.usage_ratio_id is None
    assert updated.transaction.prorrata_reference is None
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events[1:]] == [
        BucketEventType.LEDGER_TRANSACTION_UPDATED,
        BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
        BucketEventType.LEDGER_TRANSACTION_ALLOCATED,
    ]


