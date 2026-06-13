"""Manual ledger transaction application tests split by workflow."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _PROVENANCE_RAW_FIELD_EXPECTATIONS,
    _TAXABLE_IVA_EXPECTATIONS,
    UTC,
    Attachment,
    AttachmentKind,
    AttachmentSource,
    AttachmentStore,
    BucketEventObjectType,
    BucketEventType,
    BusinessClassification,
    Decimal,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    ManualLedgerTransactionCommand,
    SecureObjectRepository,
    SourceFormat,
    SpendingCategory,
    StorageValidationError,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionValidationError,
    UsageRatioProfile,
    _drive_create_manual_transaction,
    _purchase_invoice,
    _repositories,
    create_manual_transaction,
    date,
    datetime,
    hashlib,
    secure_objects,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["secure_objects"]


def test_create_manual_transaction_returns_bucket_ref(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_create_manual_transaction(secure_objects)
    assert outcome.result.ref.bucket_id == "bucket-a"


def test_create_manual_transaction_persists_source_provenance(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_create_manual_transaction(secure_objects)
    assert outcome.persisted.raw.provenance.source_format is SourceFormat.MANUAL
    assert outcome.persisted.raw.provenance.provider_name == "manual-ledger"


@pytest.mark.parametrize(("field", "expected"), _PROVENANCE_RAW_FIELD_EXPECTATIONS)
def test_create_manual_transaction_persists_raw_field(
    secure_objects: SecureObjectRepository,
    field: str,
    expected: str,
) -> None:
    outcome = _drive_create_manual_transaction(secure_objects)
    assert outcome.persisted.raw.raw_fields[field] == expected


def test_create_manual_transaction_persists_purchase_invoice_evidence_in_raw_fields(
    secure_objects: SecureObjectRepository,
) -> None:
    outcome = _drive_create_manual_transaction(secure_objects)
    assert outcome.persisted.raw.raw_fields["purchase_invoice_evidence_id"] == outcome.purchase_invoice_evidence_id


@pytest.mark.parametrize(("attribute", "expected"), _TAXABLE_IVA_EXPECTATIONS)
def test_create_manual_transaction_persists_taxable_iva(
    secure_objects: SecureObjectRepository,
    attribute: str,
    expected: Decimal,
) -> None:
    outcome = _drive_create_manual_transaction(secure_objects)
    assert getattr(outcome.persisted, attribute) == expected


def test_create_manual_transaction_links_purchase_invoice_evidence(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_create_manual_transaction(secure_objects)
    assert outcome.persisted.purchase_invoice_evidence_id == outcome.purchase_invoice_evidence_id


def test_create_manual_transaction_records_audit_actor_and_command(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_create_manual_transaction(secure_objects)
    assert outcome.persisted.created_by == "operator-A"
    assert outcome.persisted.source_command == "aeat app ledger add"
    assert outcome.persisted.created_event_id == outcome.result.bucket_event_ids[0]


def test_create_manual_transaction_persists_evidence_provenance(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_create_manual_transaction(secure_objects)
    provenance = outcome.persisted.evidence_provenance[0]
    assert provenance.evidence_id == outcome.purchase_invoice_evidence_id
    assert provenance.evidence_kind == "purchase_invoice_evidence"
    assert provenance.actor == "operator-A"
    assert provenance.bucket_event_id == outcome.result.bucket_event_ids[0]


def test_create_manual_transaction_classifies_as_business(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_create_manual_transaction(secure_objects)
    assert outcome.persisted.business_classification is BusinessClassification.BUSINESS
    assert outcome.persisted.classified_by == "manual"


def test_create_manual_transaction_emits_bucket_event_chain(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_create_manual_transaction(secure_objects)
    assert [event.event_id for event in outcome.events] == list(outcome.result.bucket_event_ids)
    first = outcome.events[0]
    assert first.event_type is BucketEventType.LEDGER_TRANSACTION_CREATED
    assert first.object_type is BucketEventObjectType.LEDGER_TRANSACTION
    assert first.object_id == outcome.result.ref.transaction_id
    assert first.payload["source_command"] == "aeat app ledger add"


def test_create_manual_transaction_validates_and_persists_usage_ratio_reference(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    category = SpendingCategory.TELEFONIA_MOVIL
    profile = UsageRatioProfile(ratios={category: Decimal("0.60")})

    result = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="telefono movil",
            business_classification=BusinessClassification.MIXED,
            business_pct=Decimal("0.60"),
            category_id=category.value,
            usage_ratio_id=category.value,
            idempotency_key="phone-usage-ratio",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        usage_ratio_profile=profile,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )

    persisted = transaction_repository.load().get(result.ref.transaction_id)
    assert persisted is not None
    assert persisted.usage_ratio_id == category.value
    assert persisted.business_pct == Decimal("0.60")
    assert persisted.raw.raw_fields["usage_ratio_id"] == category.value
    events = event_repository.load().for_bucket("bucket-a")
    assert events[0].payload["usage_ratio_id"] == category.value
    assert events[0].payload["business_pct"] == "0.60"


def test_create_manual_transaction_rejects_usage_ratio_reference_missing_from_profile(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    category = SpendingCategory.TELEFONIA_MOVIL

    with pytest.raises(TransactionValidationError, match="not configured"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("50.00"),
                direction=TransactionDirection.OUTGOING,
                description="telefono movil",
                business_classification=BusinessClassification.MIXED,
                business_pct=Decimal("0.60"),
                category_id=category.value,
                usage_ratio_id=category.value,
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            usage_ratio_profile=UsageRatioProfile(),
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_usage_ratio_alias_and_category_mismatch(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    category = SpendingCategory.TELEFONIA_MOVIL
    profile = UsageRatioProfile(ratios={category: Decimal("0.60")})

    with pytest.raises(TransactionValidationError, match="concrete eligible spending category"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("50.00"),
                direction=TransactionDirection.OUTGOING,
                description="telefono movil",
                business_classification=BusinessClassification.MIXED,
                business_pct=Decimal("0.60"),
                category_id=category.value,
                usage_ratio_id="home_office_area",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            usage_ratio_profile=profile,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    with pytest.raises(TransactionValidationError, match="must match"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("50.00"),
                direction=TransactionDirection.OUTGOING,
                description="telefono movil",
                business_classification=BusinessClassification.MIXED,
                business_pct=Decimal("0.60"),
                category_id=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ.value,
                usage_ratio_id=category.value,
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            usage_ratio_profile=profile,
            occurred_at=datetime(2026, 5, 4, 9, 31, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_usage_ratio_business_pct_drift(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    category = SpendingCategory.TELEFONIA_MOVIL
    profile = UsageRatioProfile(ratios={category: Decimal("0.60")})

    with pytest.raises(TransactionValidationError, match="does not match"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("50.00"),
                direction=TransactionDirection.OUTGOING,
                description="telefono movil",
                business_classification=BusinessClassification.MIXED,
                business_pct=Decimal("0.50"),
                category_id=category.value,
                usage_ratio_id=category.value,
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            usage_ratio_profile=profile,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_missing_purchase_evidence(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    invoice_repository.save(InvoiceCatalogue())

    with pytest.raises(TransactionValidationError, match="purchase_invoice_evidence_id"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description="material oficina",
                purchase_invoice_evidence_id="missing-purchase-evidence",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            invoice_repository=invoice_repository,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_missing_attachment_manifest(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    objects = secure_objects

    with pytest.raises(TransactionValidationError, match="attachment_ids"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description="material oficina",
                attachment_ids=("a" * 64,),
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            attachment_store=AttachmentStore(objects=objects),
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_purchase_evidence_from_other_bucket(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    other_bucket_invoice = _purchase_invoice().model_copy(update={"bucket_id": "bucket-b"})
    invoice_repository.save(InvoiceCatalogue.from_invoices((other_bucket_invoice,)))

    with pytest.raises(TransactionValidationError, match="command bucket"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description="material oficina",
                purchase_invoice_evidence_id=other_bucket_invoice.invoice_id,
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            invoice_repository=invoice_repository,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_attachment_from_other_bucket(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    objects = secure_objects
    store = AttachmentStore(objects=objects)
    body = b"%PDF-1.4\nother bucket evidence\n%%EOF"
    attachment_id = store.put_bytes(body)
    store.write_manifest(
        Attachment(
            attachment_id=attachment_id,
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="other-bucket.pdf",
            sha256=hashlib.sha256(body).hexdigest(),
            mime_type="application/pdf",
            bytes_size=len(body),
            captured_at=datetime(2026, 5, 4, 9, 0, tzinfo=UTC),
            bucket_id="bucket-b",
            captured_by="operator-B",
            source_command="aeat app ledger attach",
        ),
    )

    with pytest.raises(TransactionValidationError, match="command bucket"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description="material oficina",
                attachment_ids=(attachment_id,),
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            attachment_store=store,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_repository_bucket_mismatch(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects, bucket_id="bucket-b")

    with pytest.raises(TransactionValidationError, match="bucket_id"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
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
    transaction_repository = TransactionCatalogueRepository(bucket_id="bucket-b", objects=secure_objects)

    with pytest.raises(StorageValidationError):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-b",
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
