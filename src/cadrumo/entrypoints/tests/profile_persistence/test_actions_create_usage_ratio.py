"""Manual ledger transaction create tests for usage-ratio validation."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.actions_manual import create_manual_transaction
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.errors import TransactionValidationError
from cadrumo.domain.usage_ratios.model import UsageRatioProfile
from cadrumo.entrypoints.ledger_action_composition import compose_ledger_action_ports

from ....adapters.persistence.profile.tests.ledger_action_persistence_support import (
    BUCKET_ID as _BUCKET_ID,
    repositories as _repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@contextmanager
def _ledger_ports(transaction_repository, event_repository, profile):
    with bundled_indexed_authority().operation() as operation:
        base = compose_ledger_action_ports(bucket_id=_BUCKET_ID, operation=operation)
        yield replace(
            base,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            usage_ratio_profile=profile,
        )


def test_create_manual_transaction_validates_and_persists_usage_ratio_reference(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    category = SpendingCategory.from_registry("telefonia_movil")
    profile = UsageRatioProfile(ratios={category: Decimal("0.60")})

    with _ledger_ports(transaction_repository, event_repository, profile) as ports:
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
            ports=ports,
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
    category = SpendingCategory.from_registry("telefonia_movil")

    with (
        pytest.raises(TransactionValidationError, match="not configured"),
        _ledger_ports(transaction_repository, event_repository, UsageRatioProfile()) as ports,
    ):
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
            ports=ports,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_usage_ratio_alias_and_category_mismatch(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    category = SpendingCategory.from_registry("telefonia_movil")
    profile = UsageRatioProfile(ratios={category: Decimal("0.60")})

    with (
        pytest.raises(TransactionValidationError, match="concrete eligible spending category"),
        _ledger_ports(transaction_repository, event_repository, profile) as ports,
    ):
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
            ports=ports,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    with (
        pytest.raises(TransactionValidationError, match="must match"),
        _ledger_ports(transaction_repository, event_repository, profile) as ports,
    ):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 2),
                amount=Decimal("50.00"),
                direction=TransactionDirection.OUTGOING,
                description="telefono movil",
                business_classification=BusinessClassification.MIXED,
                business_pct=Decimal("0.60"),
                category_id=SpendingCategory.from_registry("suministros_home_office_luz").value,
                usage_ratio_id=category.value,
            ),
            ports=ports,
            occurred_at=datetime(2026, 5, 4, 9, 31, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_usage_ratio_business_pct_drift(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    category = SpendingCategory.from_registry("telefonia_movil")
    profile = UsageRatioProfile(ratios={category: Decimal("0.60")})

    with (
        pytest.raises(TransactionValidationError, match="does not match"),
        _ledger_ports(transaction_repository, event_repository, profile) as ports,
    ):
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
            ports=ports,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}
