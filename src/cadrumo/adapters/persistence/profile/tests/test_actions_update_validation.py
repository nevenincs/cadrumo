"""Manual ledger transaction update validation guard tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.ledger_action_create_support import ledger_ports_for_test
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.actions_manual import create_manual_transaction, update_manual_transaction
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.errors import TransactionValidationError
from cadrumo.domain.usage_ratios.model import UsageRatioProfile

from .ledger_action_persistence_support import (
    _BUCKET_ID,
    _repositories,
    persist_verified_revision_citing_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_update_manual_transaction_refuses_finalized_modelo_reference(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 2),
                amount=Decimal("25.00"),
                direction=TransactionDirection.OUTGOING,
                description="modelo source row",
                idempotency_key="update-blocked",
            ),
            ports=ports,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )
    persist_verified_revision_citing_transaction(secure_objects, transaction_id=created.ref.transaction_id)

    with (
        pytest.raises(TransactionValidationError, match="finalized modelo"),
        ledger_ports_for_test(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
            bucket_event_repository=event_repository,
            calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
            transaction_repository=transaction_repository,
            work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
        ) as ports,
    ):
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
            ports=ports,
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
    category = SpendingCategory._from_registry("telefonia_movil")
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 1),
                amount=Decimal("50.00"),
                direction=TransactionDirection.OUTGOING,
                description="telefono movil",
                idempotency_key="usage-ratio-update",
            ),
            ports=ports,
            occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
        )
    profile = UsageRatioProfile(ratios={category: Decimal("0.60")})

    with (
        pytest.raises(TransactionValidationError, match="does not match"),
        ledger_ports_for_test(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
            bucket_event_repository=event_repository,
            transaction_repository=transaction_repository,
            usage_ratio_profile=profile,
        ) as ports,
    ):
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
            ports=ports,
            occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
        )

    reloaded = transaction_repository.load()
    assert tuple(reloaded.transactions) == (created.ref.transaction_id,)
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [BucketEventType.LEDGER_TRANSACTION_CREATED]


def test_update_manual_transaction_rejects_provenance_only_correction(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=_BUCKET_ID,
                booked_date=date(2026, 5, 1),
                amount=Decimal("50.00"),
                direction=TransactionDirection.OUTGOING,
                description="same row",
                idempotency_key="same-row",
            ),
            ports=ports,
            occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
        )

    with (
        pytest.raises(TransactionValidationError, match="must change at least one ledger field"),
        ledger_ports_for_test(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
            bucket_event_repository=event_repository,
            transaction_repository=transaction_repository,
        ) as ports,
    ):
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
            ports=ports,
            occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
        )
