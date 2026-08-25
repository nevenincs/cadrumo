"""Evidence-authority tests: attach is the sole evidence-write door.

Generic manual-field updates (``update_manual_transaction`` command replacement
and ``update_manual_transaction_fields`` patch) must refuse every evidence field;
evidence catalogue and provenance mutation are reserved for
``attach_manual_transaction_evidence`` (``aeat app ledger attach``). Real secure
storage, real repositories, real bucket-event history — no mocks or stubs.
"""

from __future__ import annotations

import pytest

from ....domain.invoices import InvoiceLinkError
from ..actions_manual import link_manual_transaction_invoice
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
    ManualLedgerTransactionPatch,
    SecureObjectRepository,
    TransactionDirection,
    TransactionValidationError,
    _repositories,
    attach_manual_transaction_evidence,
    create_manual_transaction,
    date,
    datetime,
    purchase_invoice,
    update_manual_transaction,
    update_manual_transaction_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _seed_transaction_and_invoice(
    secure_objects: SecureObjectRepository,
    *,
    idempotency_key: str,
):
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
            idempotency_key=idempotency_key,
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    return transaction_repository, event_repository, invoice_repository, purchase_evidence, created


def test_attach_manual_transaction_evidence_attaches_and_emits_event(
    secure_objects: SecureObjectRepository,
) -> None:
    (
        transaction_repository,
        event_repository,
        invoice_repository,
        purchase_evidence,
        created,
    ) = _seed_transaction_and_invoice(secure_objects, idempotency_key="attach-emits")

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
    assert attached.transaction.evidence_provenance[-1].evidence_id == purchase_evidence.invoice_id
    assert attached.transaction.evidence_provenance[-1].bucket_event_id == attached.bucket_event_ids[0]
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
    ]
    assert events[-1].object_type is BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE
    assert events[-1].object_id == purchase_evidence.invoice_id
    assert events[-1].payload["transaction_id"] == attached.ref.transaction_id
    assert events[-1].payload["mutation_kind"] == "purchase_invoice_evidence_attached"


def test_update_manual_transaction_refuses_direct_evidence_change(
    secure_objects: SecureObjectRepository,
) -> None:
    (
        transaction_repository,
        event_repository,
        invoice_repository,
        purchase_evidence,
        created,
    ) = _seed_transaction_and_invoice(secure_objects, idempotency_key="direct-evidence-refused")

    with pytest.raises(TransactionValidationError) as exc_info:
        update_manual_transaction(
            transaction_id=created.ref.transaction_id,
            command=ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 1),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description="material oficina",
                purchase_invoice_evidence_id=purchase_evidence.invoice_id,
                actor="operator-B",
                source_command="aeat app ledger update",
                idempotency_key="direct-evidence-refused",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            invoice_repository=invoice_repository,
            occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
        )

    assert "aeat app ledger attach" in str(exc_info.value)
    # On-disk state unchanged: still evidence-free, no attach event emitted.
    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.purchase_invoice_evidence_id is None
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [BucketEventType.LEDGER_TRANSACTION_CREATED]


def test_update_manual_transaction_fields_refuses_evidence_patch(
    secure_objects: SecureObjectRepository,
) -> None:
    (
        transaction_repository,
        event_repository,
        _invoice_repository,
        purchase_evidence,
        created,
    ) = _seed_transaction_and_invoice(secure_objects, idempotency_key="patch-evidence-refused")

    with pytest.raises(TransactionValidationError) as exc_info:
        update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=created.ref.transaction_id,
            patch=ManualLedgerTransactionPatch(purchase_invoice_evidence_id=purchase_evidence.invoice_id),
            actor="operator-B",
            source_command="aeat app ledger update",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
        )

    assert "aeat app ledger attach" in str(exc_info.value)
    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.purchase_invoice_evidence_id is None


def test_generic_field_edit_preserves_existing_evidence(
    secure_objects: SecureObjectRepository,
) -> None:
    # A non-evidence edit on a row that already carries evidence must succeed and
    # preserve the evidence verbatim (the guard fires only on an evidence change).
    (
        transaction_repository,
        event_repository,
        invoice_repository,
        purchase_evidence,
        created,
    ) = _seed_transaction_and_invoice(secure_objects, idempotency_key="edit-preserves-evidence")
    attach_manual_transaction_evidence(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        purchase_invoice_evidence_id=purchase_evidence.invoice_id,
        actor="operator-B",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    edited = update_manual_transaction_fields(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        patch=ManualLedgerTransactionPatch(business_classification=BusinessClassification.BUSINESS),
        actor="operator-B",
        source_command="aeat app ledger classify",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 3, 10, 0, tzinfo=UTC),
    )

    assert edited.transaction.purchase_invoice_evidence_id == purchase_evidence.invoice_id
    persisted = transaction_repository.load().get(edited.ref.transaction_id)
    assert persisted is not None
    assert persisted.purchase_invoice_evidence_id == purchase_evidence.invoice_id


def test_bulk_classify_columns_never_carry_evidence_fields() -> None:
    # bulk_classify_from_csv reaches _prepare_manual_transaction_update (the
    # builder) directly, bypassing the wrapper's evidence guard. That is safe
    # ONLY because the bulk CSV column allowlist excludes every evidence field.
    # This gate keeps the two sets disjoint so a future column addition cannot
    # open an unguarded evidence-write door through the bulk path.
    from ..actions_manual import _EVIDENCE_PATCH_FIELDS
    from ..models import BULK_CLASSIFY_ALLOWED_COLUMNS

    assert not (BULK_CLASSIFY_ALLOWED_COLUMNS & _EVIDENCE_PATCH_FIELDS)


def test_invoice_linkage_does_not_mutate_evidence(
    secure_objects: SecureObjectRepository,
) -> None:
    # link_manual_transaction_invoice establishes an invoice-only relationship;
    # it must leave the transaction's evidence link untouched.
    (
        transaction_repository,
        event_repository,
        invoice_repository,
        purchase_evidence,
        created,
    ) = _seed_transaction_and_invoice(secure_objects, idempotency_key="link-no-evidence-mutation")
    attach_manual_transaction_evidence(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        purchase_invoice_evidence_id=purchase_evidence.invoice_id,
        actor="operator-B",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )
    events_before = [event.event_type for event in event_repository.load().for_bucket(_BUCKET_ID)]

    linked = link_manual_transaction_invoice(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        invoice_id=purchase_evidence.invoice_id,
        actor="operator-B",
        transaction_repository=transaction_repository,
        invoice_repository=invoice_repository,
    )

    assert linked.invoice_id == purchase_evidence.invoice_id
    assert created.ref.transaction_id in linked.invoice.linked_transaction_ids
    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    # Evidence preserved verbatim.
    assert persisted.purchase_invoice_evidence_id == purchase_evidence.invoice_id
    events_after = [event.event_type for event in event_repository.load().for_bucket(_BUCKET_ID)]
    # The link emits its own audit event and nothing else: no evidence event is
    # added or removed, so the evidence history is byte-identical either side.
    assert [event for event in events_after if event is not BucketEventType.LEDGER_TRANSACTION_INVOICE_LINKED] == (
        events_before
    )
    assert events_after.count(BucketEventType.LEDGER_TRANSACTION_INVOICE_LINKED) == 1


def test_failed_attach_leaves_transaction_and_history_unchanged(
    secure_objects: SecureObjectRepository,
) -> None:
    # An attach naming an unknown evidence id must refuse BEFORE any write: the
    # transaction stays evidence-free, provenance stays empty, and no attach event
    # is appended.
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            idempotency_key="failed-attach-unchanged",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    with pytest.raises(TransactionValidationError):
        attach_manual_transaction_evidence(
            bucket_id=_BUCKET_ID,
            transaction_id=created.ref.transaction_id,
            purchase_invoice_evidence_id="deadbeefdeadbeef",
            actor="operator-B",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
        )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.purchase_invoice_evidence_id is None
    assert persisted.evidence_provenance == ()
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [BucketEventType.LEDGER_TRANSACTION_CREATED]


def test_failed_invoice_link_leaves_transaction_and_history_unchanged(
    secure_objects: SecureObjectRepository,
) -> None:
    # A link naming an unknown invoice must refuse BEFORE any catalogue write.
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            idempotency_key="failed-link-unchanged",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    with pytest.raises(InvoiceLinkError):
        link_manual_transaction_invoice(
            bucket_id=_BUCKET_ID,
            transaction_id=created.ref.transaction_id,
            invoice_id="unknown-invoice-id",
            actor="operator-B",
            transaction_repository=transaction_repository,
            invoice_repository=invoice_repository,
        )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.purchase_invoice_evidence_id is None
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [BucketEventType.LEDGER_TRANSACTION_CREATED]
