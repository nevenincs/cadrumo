"""Manual ledger transaction create tests for usage-ratio validation."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    BusinessClassification,
    Decimal,
    ManualLedgerTransactionCommand,
    SecureObjectRepository,
    SpendingCategory,
    TransactionDirection,
    TransactionValidationError,
    UsageRatioProfile,
    _repositories,
    create_manual_transaction,
    date,
    datetime,
    secure_objects,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["secure_objects"]


def test_create_manual_transaction_validates_and_persists_usage_ratio_reference(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    category = SpendingCategory.TELEFONIA_MOVIL
    profile = UsageRatioProfile(ratios={category: Decimal("0.60")})

    result = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
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
    events = event_repository.load().for_bucket(_BUCKET_ID)
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
                bucket_id=_BUCKET_ID,
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
                bucket_id=_BUCKET_ID,
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
                bucket_id=_BUCKET_ID,
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
                bucket_id=_BUCKET_ID,
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
