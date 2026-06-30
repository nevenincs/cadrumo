"""Manual ledger transaction application tests split by workflow."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    _OTHER_BUCKET_ID,
    PROVENANCE_RAW_FIELD_EXPECTATIONS,
    TAXABLE_IVA_EXPECTATIONS,
    UTC,
    BucketEventObjectType,
    BucketEventType,
    BusinessClassification,
    Decimal,
    ManualLedgerTransactionCommand,
    SecureObjectRepository,
    SourceFormat,
    StorageValidationError,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionValidationError,
    _repositories,
    create_manual_transaction,
    date,
    datetime,
    drive_create_manual_transaction,
    secure_objects,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["secure_objects"]


def test_create_manual_transaction_returns_bucket_ref(secure_objects: SecureObjectRepository) -> None:
    outcome = drive_create_manual_transaction(secure_objects)
    assert outcome.result.ref.bucket_id == _BUCKET_ID


def test_create_manual_transaction_persists_source_provenance(secure_objects: SecureObjectRepository) -> None:
    outcome = drive_create_manual_transaction(secure_objects)
    assert outcome.persisted.raw.provenance.source_format is SourceFormat.MANUAL
    assert outcome.persisted.raw.provenance.provider_name == "manual-ledger"


@pytest.mark.parametrize(("field", "expected"), PROVENANCE_RAW_FIELD_EXPECTATIONS)
def test_create_manual_transaction_persists_raw_field(
    secure_objects: SecureObjectRepository,
    field: str,
    expected: str,
) -> None:
    outcome = drive_create_manual_transaction(secure_objects)
    assert outcome.persisted.raw.raw_fields[field] == expected


def test_create_manual_transaction_persists_purchase_invoice_evidence_in_raw_fields(
    secure_objects: SecureObjectRepository,
) -> None:
    outcome = drive_create_manual_transaction(secure_objects)
    assert outcome.persisted.raw.raw_fields["purchase_invoice_evidence_id"] == outcome.purchase_invoice_evidence_id


@pytest.mark.parametrize(("attribute", "expected"), TAXABLE_IVA_EXPECTATIONS)
def test_create_manual_transaction_persists_taxable_iva(
    secure_objects: SecureObjectRepository,
    attribute: str,
    expected: Decimal,
) -> None:
    outcome = drive_create_manual_transaction(secure_objects)
    assert getattr(outcome.persisted, attribute) == expected


def test_create_manual_transaction_links_purchase_invoice_evidence(secure_objects: SecureObjectRepository) -> None:
    outcome = drive_create_manual_transaction(secure_objects)
    assert outcome.persisted.purchase_invoice_evidence_id == outcome.purchase_invoice_evidence_id


def test_create_manual_transaction_records_audit_actor_and_command(secure_objects: SecureObjectRepository) -> None:
    outcome = drive_create_manual_transaction(secure_objects)
    assert outcome.persisted.created_by == "operator-A"
    assert outcome.persisted.source_command == "aeat app ledger add"
    assert outcome.persisted.created_event_id == outcome.result.bucket_event_ids[0]


def test_create_manual_transaction_persists_evidence_provenance(secure_objects: SecureObjectRepository) -> None:
    outcome = drive_create_manual_transaction(secure_objects)
    provenance = outcome.persisted.evidence_provenance[0]
    assert provenance.evidence_id == outcome.purchase_invoice_evidence_id
    assert provenance.evidence_kind == "purchase_invoice_evidence"
    assert provenance.actor == "operator-A"
    assert provenance.bucket_event_id == outcome.result.bucket_event_ids[0]


def test_create_manual_transaction_classifies_as_business(secure_objects: SecureObjectRepository) -> None:
    outcome = drive_create_manual_transaction(secure_objects)
    assert outcome.persisted.business_classification is BusinessClassification.BUSINESS
    assert outcome.persisted.classified_by == "manual"


def test_create_manual_transaction_emits_bucket_event_chain(secure_objects: SecureObjectRepository) -> None:
    outcome = drive_create_manual_transaction(secure_objects)
    assert [event.event_id for event in outcome.events] == list(outcome.result.bucket_event_ids)
    first = outcome.events[0]
    assert first.event_type is BucketEventType.LEDGER_TRANSACTION_CREATED
    assert first.object_type is BucketEventObjectType.LEDGER_TRANSACTION
    assert first.object_id == outcome.result.ref.transaction_id
    assert first.payload["source_command"] == "aeat app ledger add"


def test_create_manual_transaction_rejects_repository_bucket_mismatch(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects, bucket_id=_OTHER_BUCKET_ID)

    with pytest.raises(TransactionValidationError, match="bucket_id"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 2),
                amount=Decimal("10.00"),
                direction=TransactionDirection.OUTGOING,
                description="wrong bucket",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )


def test_create_manual_transaction_default_event_repository_fails_closed_for_inactive_bucket(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository = TransactionCatalogueRepository(bucket_id=_OTHER_BUCKET_ID, objects=secure_objects)

    with pytest.raises(StorageValidationError):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_OTHER_BUCKET_ID,
                booked_date=date(2026, 5, 2),
                amount=Decimal("10.00"),
                direction=TransactionDirection.OUTGOING,
                description="inactive bucket",
                actor="operator-A",
                source_command="aeat app ledger add",
            ),
            transaction_repository=transaction_repository,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )
