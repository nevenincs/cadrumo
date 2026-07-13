"""Manual ledger lifecycle guards for finalized Modelo references."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    BucketEventType,
    CalculationRevisionCatalogueRepository,
    Decimal,
    ManualLedgerTransactionCommand,
    SecureObjectRepository,
    TransactionDirection,
    TransactionLifecycleState,
    TransactionValidationError,
    WorkUnitCatalogueRepository,
    _create_manual_row,
    archive_manual_transaction,
    date,
    datetime,
    persist_verified_revision_citing_transaction,
    remove_manual_transaction,
    reset_ledger_catalogue,
    restore_manual_transaction,
    stash_manual_transaction,
    update_manual_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_finalized_modelo_reference_blocks_lifecycle_removal_prior_id_and_reset(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository, restore_row = _create_manual_row(
        secure_objects,
        description="modelo source row stashed",
        idempotency_key="restore-blocked",
    )
    stash_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=restore_row.ref.transaction_id,
        actor="operator-A",
        reason="parked pending review",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 9, 0, tzinfo=UTC),
    )
    _, _, remove_row = _create_manual_row(
        secure_objects,
        description="modelo source row",
        idempotency_key="remove-blocked",
    )
    _, _, lifecycle_row = _create_manual_row(
        secure_objects,
        description="modelo source row",
        idempotency_key="lifecycle-blocked",
    )
    _, _, prior_source_row = _create_manual_row(
        secure_objects,
        description="modelo source row",
        idempotency_key="prior-id",
    )
    updated_prior_row = update_manual_transaction(
        transaction_id=prior_source_row.ref.transaction_id,
        command=ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 2),
            amount=Decimal("35.00"),
            direction=TransactionDirection.OUTGOING,
            description="modelo source row corrected",
            idempotency_key="prior-id",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )
    assert updated_prior_row.ref.transaction_id != prior_source_row.ref.transaction_id
    persist_verified_revision_citing_transaction(
        secure_objects,
        transaction_id=restore_row.ref.transaction_id,
        additional_transaction_ids=(
            remove_row.ref.transaction_id,
            lifecycle_row.ref.transaction_id,
            prior_source_row.ref.transaction_id,
        ),
    )
    work_unit_repository = WorkUnitCatalogueRepository(objects=secure_objects)
    calculation_repository = CalculationRevisionCatalogueRepository(objects=secure_objects)

    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        restore_manual_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id=restore_row.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            occurred_at=datetime(2026, 5, 6, 10, 0, tzinfo=UTC),
        )
    dry_run_removal = remove_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=remove_row.ref.transaction_id,
        actor="operator-A",
        dry_run=True,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    assert dry_run_removal.blocking_modelo_references[0].modelo == "303"
    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        remove_manual_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id=remove_row.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
        )
    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        archive_manual_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id=lifecycle_row.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
        )
    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        remove_manual_transaction(
            bucket_id=_BUCKET_ID,
            transaction_id=updated_prior_row.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
        )
    dry_run_reset = reset_ledger_catalogue(
        bucket_id=_BUCKET_ID,
        actor="operator-A",
        dry_run=True,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
    )
    assert dry_run_reset.blocking_modelo_references[0].modelo == "303"
    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        reset_ledger_catalogue(
            bucket_id=_BUCKET_ID,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
        )

    persisted = transaction_repository.load()
    persisted_restore_row = persisted.get(restore_row.ref.transaction_id)
    persisted_lifecycle_row = persisted.get(lifecycle_row.ref.transaction_id)
    assert persisted_restore_row is not None
    assert persisted_restore_row.lifecycle_state is TransactionLifecycleState.STASHED
    assert persisted.get(remove_row.ref.transaction_id) is not None
    assert persisted_lifecycle_row is not None
    assert persisted_lifecycle_row.lifecycle_state is TransactionLifecycleState.ACTIVE
    assert persisted.get(updated_prior_row.ref.transaction_id) is not None
    event_types = [event.event_type for event in event_repository.load().for_bucket(_BUCKET_ID)]
    assert BucketEventType.LEDGER_TRANSACTION_RESTORED not in event_types
    assert BucketEventType.LEDGER_TRANSACTION_ARCHIVED not in event_types
    assert BucketEventType.LEDGER_TRANSACTION_REMOVED not in event_types
    assert BucketEventType.LEDGER_CATALOGUE_RESET not in event_types
