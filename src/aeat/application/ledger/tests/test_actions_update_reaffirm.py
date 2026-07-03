"""Manual ledger transaction update tests for reaffirm/no-op handling."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    BucketEventHistoryRepository,
    BucketEventType,
    BusinessClassification,
    Decimal,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
    SecureObjectRepository,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionValidationError,
    _repositories,
    create_manual_transaction,
    date,
    datetime,
    update_manual_transaction_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _create_classified_transaction(
    transaction_repository: TransactionCatalogueRepository,
    event_repository: BucketEventHistoryRepository,
) -> ManualLedgerTransactionResult:
    """Create a BUSINESS transaction with typical tax fields set."""
    return create_manual_transaction(
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
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )


def test_update_manual_transaction_fields_reaffirmation_noop_returns_stored_transaction(
    secure_objects: SecureObjectRepository,
) -> None:
    """Same-value classification patching returns the stored transaction."""

    transaction_repository, event_repository = _repositories(secure_objects)
    created = _create_classified_transaction(transaction_repository, event_repository)
    event_count_before = len(list(event_repository.load().for_bucket(_BUCKET_ID)))

    result = update_manual_transaction_fields(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        patch=ManualLedgerTransactionPatch(
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("21.00"),
        ),
        actor="operator-C",
        source_command="aeat app ledger classify",
        reaffirm=False,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert result.transaction.transaction_id == created.ref.transaction_id
    assert result.bucket_event_ids == ()
    event_count_after = len(list(event_repository.load().for_bucket(_BUCKET_ID)))
    assert event_count_after == event_count_before


def test_update_manual_transaction_fields_reaffirm_true_bypasses_outer_guard_but_inner_guard_still_applies(
    secure_objects: SecureObjectRepository,
) -> None:
    """Identical reaffirm patching still raises from the inner mutation guard."""

    transaction_repository, event_repository = _repositories(secure_objects)
    created = _create_classified_transaction(transaction_repository, event_repository)

    with pytest.raises(TransactionValidationError, match="must change at least one"):
        update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=created.ref.transaction_id,
            patch=ManualLedgerTransactionPatch(
                business_classification=BusinessClassification.BUSINESS,
                category_id="office-supplies",
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("0.21"),
                iva_amount=Decimal("21.00"),
            ),
            actor="operator-C",
            source_command="aeat app ledger classify",
            reaffirm=True,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
        )


def test_update_manual_transaction_fields_reaffirm_true_with_net_change_emits_event(
    secure_objects: SecureObjectRepository,
) -> None:
    """Reaffirming with a net-change patch succeeds and emits events."""

    transaction_repository, event_repository = _repositories(secure_objects)
    created = _create_classified_transaction(transaction_repository, event_repository)

    result = update_manual_transaction_fields(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        patch=ManualLedgerTransactionPatch(
            business_classification=BusinessClassification.BUSINESS,
            notes="reaffirmed with corrected notes",
        ),
        actor="operator-C",
        source_command="aeat app ledger classify",
        reaffirm=True,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert result.bucket_event_ids != ()
    assert result.transaction.notes == "reaffirmed with corrected notes"
    events = list(event_repository.load().for_bucket(_BUCKET_ID))
    new_event_types = [e.event_type for e in events[1:]]
    assert BucketEventType.LEDGER_TRANSACTION_CLASSIFIED in new_event_types


def test_update_manual_transaction_fields_different_classification_bypasses_noop_guard(
    secure_objects: SecureObjectRepository,
) -> None:
    """Different classification patching must bypass the no-op guard."""

    transaction_repository, event_repository = _repositories(secure_objects)
    created = _create_classified_transaction(transaction_repository, event_repository)

    result = update_manual_transaction_fields(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        patch=ManualLedgerTransactionPatch(business_classification=BusinessClassification.PERSONAL),
        actor="operator-C",
        source_command="aeat app ledger classify",
        reaffirm=False,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert result.transaction.business_classification is BusinessClassification.PERSONAL
    assert result.bucket_event_ids != ()
