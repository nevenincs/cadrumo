"""Manual ledger transaction field-patch update tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.actions_manual import create_manual_transaction, update_manual_transaction_fields
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection

from .ledger_action_create_support import ledger_ports_for_test
from .ledger_action_persistence_support import (
    BUCKET_ID as _BUCKET_ID,
)
from .ledger_action_persistence_support import (
    repositories as _repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_update_manual_transaction_fields_applies_typed_patch_through_backend(
    secure_objects: SecureObjectRepository,
) -> None:
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
                amount=Decimal("75.00"),
                direction=TransactionDirection.OUTGOING,
                description="pending row",
                idempotency_key="typed-patch",
            ),
            ports=ports,
            occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
        )

    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        updated = update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=created.ref.transaction_id,
            patch=ManualLedgerTransactionPatch(
                description="classified row",
                business_classification=BusinessClassification.BUSINESS,
                category_id="office-supplies",
                taxable_base=Decimal("61.98"),
                iva_rate=Decimal("0.21"),
                iva_amount=Decimal("13.02"),
            ),
            actor="operator-C",
            source_command="aeat app ledger classify",
            ports=ports,
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
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
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
            ports=ports,
            occurred_at=datetime(2026, 7, 15, 8, 0, tzinfo=UTC),
        )

    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
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
            ports=ports,
            occurred_at=datetime(2026, 7, 16, 10, 0, tzinfo=UTC),
        )

    assert created.transaction.source_jurisdiction == "FR"
    assert updated.transaction.source_jurisdiction == "FR"
    assert transaction_repository.load().transactions[updated.ref.transaction_id].source_jurisdiction == "FR"


def test_update_manual_transaction_fields_clears_tax_facts_for_personal_reclassification(
    secure_objects: SecureObjectRepository,
) -> None:
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
            ports=ports,
            occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
        )

    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        updated = update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=created.ref.transaction_id,
            patch=ManualLedgerTransactionPatch(business_classification=BusinessClassification.PERSONAL),
            actor="operator-C",
            source_command="aeat app ledger classify",
            ports=ports,
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
