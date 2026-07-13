"""Manual ledger transaction update tests for purchase evidence attachment."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    BucketEventObjectType,
    BucketEventType,
    BusinessClassification,
    Decimal,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    ManualLedgerTransactionCommand,
    SecureObjectRepository,
    TransactionDirection,
    _repositories,
    attach_manual_transaction_evidence,
    create_manual_transaction,
    date,
    datetime,
    purchase_invoice,
    update_manual_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_update_manual_transaction_emits_purchase_evidence_attachment_event(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    purchase_evidence = purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            idempotency_key="evidence-attach",
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
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            purchase_invoice_evidence_id=purchase_evidence.invoice_id,
            actor="operator-B",
            source_command="aeat app ledger attach",
            idempotency_key="evidence-attach",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert updated.transaction.purchase_invoice_evidence_id == purchase_evidence.invoice_id
    assert updated.transaction.evidence_provenance[-1].evidence_id == purchase_evidence.invoice_id
    assert updated.transaction.evidence_provenance[-1].bucket_event_id == updated.bucket_event_ids[0]
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
    ]
    assert events[-1].object_type is BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE
    assert events[-1].object_id == purchase_evidence.invoice_id
    assert events[-1].payload["transaction_id"] == updated.ref.transaction_id
    assert events[-1].payload["mutation_kind"] == "purchase_invoice_evidence_attached"


def test_attach_manual_transaction_evidence_delegates_to_validated_backend_patch(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    purchase_evidence = purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            idempotency_key="evidence-helper-attach",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    attached = attach_manual_transaction_evidence(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        purchase_invoice_evidence_id=purchase_evidence.invoice_id,
        actor="operator-B",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert attached.transaction.purchase_invoice_evidence_id == purchase_evidence.invoice_id
    assert attached.transaction.evidence_provenance[-1].evidence_kind == "purchase_invoice_evidence"
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
    ]


def test_update_manual_transaction_mixed_edit_and_evidence_lineage_uses_evidence_event(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    purchase_evidence = purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            idempotency_key="mixed-evidence-attach",
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
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina corrected",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            purchase_invoice_evidence_id=purchase_evidence.invoice_id,
            actor="operator-B",
            source_command="aeat app ledger attach",
            idempotency_key="mixed-evidence-attach",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    events = event_repository.load().for_bucket(_BUCKET_ID)
    attach_event = next(
        event for event in events if event.event_type is BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED
    )
    assert updated.transaction.edit_lineage[-1].bucket_event_id != attach_event.event_id
    assert updated.transaction.evidence_provenance[-1].bucket_event_id == attach_event.event_id
