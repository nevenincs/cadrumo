"""Manual ledger transaction update validation guard tests."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    BucketEventType,
    BusinessClassification,
    CalculationRevisionCatalogueRepository,
    Decimal,
    ManualLedgerTransactionCommand,
    SecureObjectRepository,
    SpendingCategory,
    TransactionDirection,
    TransactionValidationError,
    UsageRatioProfile,
    WorkUnitCatalogueRepository,
    _repositories,
    create_manual_transaction,
    date,
    datetime,
    persist_verified_revision_citing_transaction,
    update_manual_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_update_manual_transaction_refuses_finalized_modelo_reference(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 2),
            amount=Decimal("25.00"),
            direction=TransactionDirection.OUTGOING,
            description="modelo source row",
            idempotency_key="update-blocked",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    persist_verified_revision_citing_transaction(secure_objects, transaction_id=created.ref.transaction_id)

    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        update_manual_transaction(
            transaction_id=created.ref.transaction_id,
            command=ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 2),
                amount=Decimal("35.00"),
                direction=TransactionDirection.OUTGOING,
                description="mutated modelo source row",
                idempotency_key="update-blocked",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
            calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
            occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
        )

    assert tuple(transaction_repository.load().transactions) == (created.ref.transaction_id,)
    assert [event.event_type for event in event_repository.load().for_bucket(_BUCKET_ID)] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
    ]


def test_update_manual_transaction_rejects_usage_ratio_drift_without_event_or_save(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    category = SpendingCategory.TELEFONIA_MOVIL
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="telefono movil",
            idempotency_key="usage-ratio-update",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    profile = UsageRatioProfile(ratios={category: Decimal("0.60")})

    with pytest.raises(TransactionValidationError, match="does not match"):
        update_manual_transaction(
            transaction_id=created.ref.transaction_id,
            command=ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 1),
                amount=Decimal("50.00"),
                direction=TransactionDirection.OUTGOING,
                description="telefono movil corrected",
                business_classification=BusinessClassification.MIXED,
                business_pct=Decimal("0.50"),
                category_id=category.value,
                usage_ratio_id=category.value,
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            usage_ratio_profile=profile,
            occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
        )

    reloaded = transaction_repository.load()
    assert tuple(reloaded.transactions) == (created.ref.transaction_id,)
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [BucketEventType.LEDGER_TRANSACTION_CREATED]


def test_update_manual_transaction_rejects_provenance_only_correction(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="same row",
            idempotency_key="same-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    with pytest.raises(TransactionValidationError, match="must change at least one ledger field"):
        update_manual_transaction(
            transaction_id=created.ref.transaction_id,
            command=ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 1),
                amount=Decimal("50.00"),
                direction=TransactionDirection.OUTGOING,
                description="same row",
                idempotency_key="same-row",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
        )
