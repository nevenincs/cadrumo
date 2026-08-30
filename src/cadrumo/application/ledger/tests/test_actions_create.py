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


def test_create_manual_transaction_persists_raw_field(
    secure_objects: SecureObjectRepository,
) -> None:
    outcome = drive_create_manual_transaction(secure_objects)
    for field, expected in PROVENANCE_RAW_FIELD_EXPECTATIONS:
        assert outcome.persisted.raw.raw_fields[field] == expected, field


def test_create_manual_transaction_persists_purchase_invoice_evidence_in_raw_fields(
    secure_objects: SecureObjectRepository,
) -> None:
    outcome = drive_create_manual_transaction(secure_objects)
    assert outcome.persisted.raw.raw_fields["purchase_invoice_evidence_id"] == outcome.purchase_invoice_evidence_id


def test_create_manual_transaction_persists_taxable_iva(
    secure_objects: SecureObjectRepository,
) -> None:
    outcome = drive_create_manual_transaction(secure_objects)
    for attribute, expected in TAXABLE_IVA_EXPECTATIONS:
        assert getattr(outcome.persisted, attribute) == expected, attribute


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


def test_manual_foreign_currency_row_converts_at_entry(
    secure_objects: SecureObjectRepository,
) -> None:
    """A manually entered GBP row carries fx_rate and value_in_eur.

    Without conversion at entry the row persists with ``value_in_eur = None``
    and every aggregation gate withholds it, so a manually entered foreign
    invoice never reaches the modelo at all.
    """
    from datetime import date as _date

    from ....adapters.outbound.fx import EcbReferenceRateProvider
    from ....domain.currency.service import CurrencyNormalizationService
    from ....tests.ecb_stub import ecb_csv_fetch

    transaction_repository, event_repository = _repositories(secure_objects)
    # ECB EXR.D.GBP.EUR.SP00.A 2026-05-02 stubbed at the real 2025-03-14 quote.
    quote = Decimal("0.84183")
    normalizer = CurrencyNormalizationService(
        rate_provider=EcbReferenceRateProvider(fetch=ecb_csv_fetch({"GBP": {_date(2026, 5, 2): quote}})),
    )

    result = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 2),
            amount=Decimal("1000.00"),
            currency="GBP",
            direction=TransactionDirection.INCOMING,
            description="UK client invoice",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        currency_normalizer=normalizer,
    )

    expected_eur = (Decimal("1000.00") * (Decimal("1") / quote)).quantize(Decimal("0.01"))
    assert result.transaction.fx_rate == Decimal("1") / quote
    assert result.transaction.value_in_eur == expected_eur
    assert result.transaction.raw.currency == "GBP"
    # The native amount is untouched; only the euro equivalent is added.
    assert result.transaction.raw.amount == Decimal("1000.00")


def test_manual_eur_row_carries_no_conversion_stamp(
    secure_objects: SecureObjectRepository,
) -> None:
    """A euro row is already euro: stamping it would imply a conversion that never happened."""
    transaction_repository, event_repository = _repositories(secure_objects)

    result = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 2),
            amount=Decimal("100.00"),
            direction=TransactionDirection.INCOMING,
            description="Domestic invoice",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )

    assert result.transaction.raw.currency == "EUR"
    assert result.transaction.fx_rate is None
    assert result.transaction.value_in_eur is None
