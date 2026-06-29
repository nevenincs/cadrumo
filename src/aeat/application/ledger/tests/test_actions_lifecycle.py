"""Manual ledger transaction application tests split by workflow."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    UTC,
    BucketEventHistoryRepository,
    BucketEventType,
    BusinessClassification,
    CalculationRevisionCatalogueRepository,
    Decimal,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionResult,
    SecureObjectRepository,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
    TransactionValidationError,
    WorkUnitCatalogueRepository,
    _repositories,
    archive_manual_transaction,
    create_manual_transaction,
    date,
    datetime,
    persist_verified_revision_citing_transaction,
    purchase_invoice,
    remove_manual_transaction,
    reset_ledger_catalogue,
    restore_manual_transaction,
    stash_manual_transaction,
    summarize_manual_transactions,
    update_manual_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _create_manual_row(
    secure_objects: SecureObjectRepository,
    *,
    description: str,
    idempotency_key: str,
    amount: Decimal | None = None,
    booked_date: date | None = None,
    occurred_at: datetime | None = None,
) -> tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, ManualLedgerTransactionResult]:
    transaction_repository, event_repository = _repositories(secure_objects)
    resolved_booked_date = booked_date if booked_date is not None else date(2026, 5, 2)
    resolved_amount = amount if amount is not None else Decimal("25.00")
    resolved_occurred_at = occurred_at if occurred_at is not None else datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=resolved_booked_date,
            amount=resolved_amount,
            direction=TransactionDirection.OUTGOING,
            description=description,
            idempotency_key=idempotency_key,
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=resolved_occurred_at,
    )
    return transaction_repository, event_repository, created


def test_archive_manual_transaction_records_lifecycle_lineage_and_event(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="wrong account import",
            idempotency_key="archive-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    archived = archive_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="wrong account import",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ARCHIVED
    assert persisted.lifecycle_lineage[-1].previous_state is TransactionLifecycleState.ACTIVE
    assert persisted.lifecycle_lineage[-1].state is TransactionLifecycleState.ARCHIVED
    assert persisted.lifecycle_lineage[-1].reason == "wrong account import"
    assert persisted.lifecycle_lineage[-1].bucket_event_id == archived.bucket_event_ids[0]
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
    ]
    assert events[-1].payload["previous_lifecycle_state"] == "ACTIVE"
    assert events[-1].payload["lifecycle_state"] == "ARCHIVED"
    assert events[-1].payload["reason"] == "wrong account import"


def test_update_manual_transaction_rejects_archived_row_without_reactivating_it(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="wrong account import",
            idempotency_key="archived-edit-refusal",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    archived = archive_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="wrong account import",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(TransactionValidationError, match="can be edited"):
        update_manual_transaction(
            transaction_id=created.ref.transaction_id,
            command=ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 1),
                amount=Decimal("60.00"),
                direction=TransactionDirection.OUTGOING,
                description="attempt to edit archived row",
                actor="operator-B",
                source_command="aeat app ledger update",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 3, 10, 0, tzinfo=UTC),
        )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ARCHIVED
    assert persisted.lifecycle_lineage[-1].bucket_event_id == archived.bucket_event_ids[0]
    assert [event.event_type for event in event_repository.load().for_bucket("bucket-a")] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
    ]


def test_stash_manual_transaction_records_lifecycle_lineage_and_event(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="hold for later classification",
            idempotency_key="stash-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    stashed = stash_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="needs supporting statement",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.STASHED
    assert persisted.lifecycle_lineage[-1].state is TransactionLifecycleState.STASHED
    assert persisted.lifecycle_lineage[-1].bucket_event_id == stashed.bucket_event_ids[0]
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_STASHED,
    ]
    assert events[-1].payload["lifecycle_state"] == "STASHED"


def test_restore_stashed_transaction_returns_it_to_active_with_event_and_lineage(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="stashed by mistake",
            idempotency_key="restore-stash-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    stash_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="needs supporting statement",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    # The row left the active-aggregation set while stashed.
    stashed_summary = summarize_manual_transactions(bucket_id="bucket-a", transaction_repository=transaction_repository)
    assert stashed_summary.active_count == 0
    assert stashed_summary.stashed_count == 1

    restored = restore_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-B",
        reason="stashed by mistake",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 3, 9, 0, tzinfo=UTC),
    )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ACTIVE
    assert persisted.lifecycle_lineage[-1].previous_state is TransactionLifecycleState.STASHED
    assert persisted.lifecycle_lineage[-1].state is TransactionLifecycleState.ACTIVE
    assert persisted.lifecycle_lineage[-1].reason == "stashed by mistake"
    assert persisted.lifecycle_lineage[-1].bucket_event_id == restored.bucket_event_ids[0]

    # The restored row is genuinely active again: it re-enters the
    # active-aggregation set that tax calculations consume.
    restored_summary = summarize_manual_transactions(
        bucket_id="bucket-a",
        transaction_repository=transaction_repository,
    )
    assert restored_summary.active_count == 1
    assert restored_summary.stashed_count == 0

    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_STASHED,
        BucketEventType.LEDGER_TRANSACTION_RESTORED,
    ]
    assert events[-1].payload["previous_lifecycle_state"] == "STASHED"
    assert events[-1].payload["lifecycle_state"] == "ACTIVE"
    assert events[-1].payload["reason"] == "stashed by mistake"


def test_restore_archived_transaction_returns_it_to_active(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("72.50"),
            direction=TransactionDirection.OUTGOING,
            description="archived by mistake",
            idempotency_key="restore-archive-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    archive_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="wrong row archived",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    restored = restore_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-B",
        reason="archived by mistake",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 3, 9, 0, tzinfo=UTC),
    )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ACTIVE
    assert persisted.lifecycle_lineage[-1].previous_state is TransactionLifecycleState.ARCHIVED
    assert persisted.lifecycle_lineage[-1].state is TransactionLifecycleState.ACTIVE
    assert persisted.lifecycle_lineage[-1].bucket_event_id == restored.bucket_event_ids[0]
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
        BucketEventType.LEDGER_TRANSACTION_RESTORED,
    ]
    assert events[-1].payload["previous_lifecycle_state"] == "ARCHIVED"


def test_restore_refuses_an_already_active_transaction(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository, created = _create_manual_row(
        secure_objects,
        description="already active row",
        idempotency_key="restore-active-refusal",
        amount=Decimal("50.00"),
        booked_date=date(2026, 5, 1),
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    with pytest.raises(TransactionValidationError, match="already active"):
        restore_manual_transaction(
            bucket_id="bucket-a",
            transaction_id=created.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
        )

    # No restore event was emitted and the row stays exactly as created.
    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ACTIVE
    assert [event.event_type for event in event_repository.load().for_bucket("bucket-a")] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
    ]


def test_finalized_modelo_reference_blocks_lifecycle_removal_prior_id_and_reset(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository, restore_row = _create_manual_row(
        secure_objects,
        description="modelo source row stashed",
        idempotency_key="restore-blocked",
    )
    stash_manual_transaction(
        bucket_id="bucket-a",
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
            bucket_id="bucket-a",
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
            bucket_id="bucket-a",
            transaction_id=restore_row.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            occurred_at=datetime(2026, 5, 6, 10, 0, tzinfo=UTC),
        )
    dry_run_removal = remove_manual_transaction(
        bucket_id="bucket-a",
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
            bucket_id="bucket-a",
            transaction_id=remove_row.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
        )
    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        archive_manual_transaction(
            bucket_id="bucket-a",
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
            bucket_id="bucket-a",
            transaction_id=updated_prior_row.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
        )
    dry_run_reset = reset_ledger_catalogue(
        bucket_id="bucket-a",
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
            bucket_id="bucket-a",
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
    event_types = [event.event_type for event in event_repository.load().for_bucket("bucket-a")]
    assert BucketEventType.LEDGER_TRANSACTION_RESTORED not in event_types
    assert BucketEventType.LEDGER_TRANSACTION_ARCHIVED not in event_types
    assert BucketEventType.LEDGER_TRANSACTION_REMOVED not in event_types
    assert BucketEventType.LEDGER_CATALOGUE_RESET not in event_types


def test_restore_roundtrip_survives_storage_reload_and_breaks_on_corruption(
    secure_objects: SecureObjectRepository,
) -> None:
    """Anti-tautology proof: the restored ACTIVE state must come from durable
    storage, not the in-memory result. Restore a stashed row, reload it from a
    fresh repository instance, assert ACTIVE; then mutate the on-disk record
    back to STASHED and assert the reload surfaces the corruption rather than
    masking it."""
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="roundtrip restore row",
            idempotency_key="restore-roundtrip",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    stash_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="parked",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )
    restore_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-B",
        reason="restored",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 3, 9, 0, tzinfo=UTC),
    )

    fresh_repository, _ = _repositories(secure_objects)
    reloaded = fresh_repository.load().get(created.ref.transaction_id)
    assert reloaded is not None
    assert reloaded.lifecycle_state is TransactionLifecycleState.ACTIVE

    # Corrupt the persisted record back to STASHED through the real storage
    # boundary and prove a fresh load surfaces the divergence.
    corrupted = reloaded.model_copy(update={"lifecycle_state": TransactionLifecycleState.STASHED})
    catalogue = fresh_repository.load()
    fresh_repository.save(
        TransactionCatalogue.model_validate(
            {"transactions": {**dict(catalogue.transactions), corrupted.transaction_id: corrupted}},
        ),
    )
    poisoned_repository, _ = _repositories(secure_objects)
    poisoned = poisoned_repository.load().get(created.ref.transaction_id)
    assert poisoned is not None
    assert poisoned.lifecycle_state is TransactionLifecycleState.STASHED


def test_archive_and_stash_refuse_invalid_lifecycle_transitions(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="wrong account import",
            idempotency_key="archive-stash-refusal",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    archive_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(TransactionValidationError, match="already archived"):
        archive_manual_transaction(
            bucket_id="bucket-a",
            transaction_id=created.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 3, 10, 0, tzinfo=UTC),
        )
    with pytest.raises(TransactionValidationError, match="cannot be stashed"):
        stash_manual_transaction(
            bucket_id="bucket-a",
            transaction_id=created.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 3, 10, 0, tzinfo=UTC),
        )

    assert [event.event_type for event in event_repository.load().for_bucket("bucket-a")] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
    ]


def test_remove_manual_transaction_deletes_row_detaches_purchase_evidence_and_emits_events(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    purchase_evidence = purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            purchase_invoice_evidence_id=purchase_evidence.invoice_id,
            idempotency_key="remove-linked-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    invoice_repository.save(
        InvoiceCatalogue.from_invoices(
            (purchase_evidence.model_copy(update={"linked_transaction_ids": (created.ref.transaction_id,)}),),
        ),
    )

    removed = remove_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="wrong account import",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert removed.removed is True
    assert removed.cascaded_purchase_invoice_evidence_ids == (purchase_evidence.invoice_id,)
    assert transaction_repository.load().transactions == {}
    detached = invoice_repository.load().get(purchase_evidence.invoice_id)
    assert detached is not None
    assert detached.linked_transaction_ids == ()
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
        BucketEventType.LEDGER_TRANSACTION_REMOVED,
    ]
    assert events[-1].payload["purchase_invoice_evidence_ids"] == purchase_evidence.invoice_id
    assert events[-1].payload["reason"] == "wrong account import"


def test_remove_manual_transaction_dry_run_reports_without_mutation(secure_objects: SecureObjectRepository) -> None:
    transaction_repository, event_repository, created = _create_manual_row(
        secure_objects,
        description="dry run row",
        idempotency_key="remove-dry-run",
    )

    report = remove_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        dry_run=True,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert report.dry_run is True
    assert report.removed is False
    assert transaction_repository.load().get(created.ref.transaction_id) is not None
    assert [event.event_type for event in event_repository.load().for_bucket("bucket-a")] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
    ]


def test_reset_ledger_catalogue_clears_bucket_when_unblocked_and_emits_event(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    purchase_evidence = purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    first = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("25.00"),
            direction=TransactionDirection.OUTGOING,
            description="first reset row",
            purchase_invoice_evidence_id=purchase_evidence.invoice_id,
            idempotency_key="reset-first",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    second = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 3),
            amount=Decimal("30.00"),
            direction=TransactionDirection.OUTGOING,
            description="second reset row",
            idempotency_key="reset-second",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 31, tzinfo=UTC),
    )
    invoice_repository.save(
        InvoiceCatalogue.from_invoices(
            (purchase_evidence.model_copy(update={"linked_transaction_ids": (first.ref.transaction_id,)}),),
        ),
    )

    report = reset_ledger_catalogue(
        bucket_id="bucket-a",
        actor="operator-A",
        reason="contaminated import batch",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert report.reset is True
    assert report.removed_transaction_ids == tuple(sorted((first.ref.transaction_id, second.ref.transaction_id)))
    assert report.cascaded_purchase_invoice_evidence_ids == (purchase_evidence.invoice_id,)
    assert transaction_repository.load().transactions == {}
    detached = invoice_repository.load().get(purchase_evidence.invoice_id)
    assert detached is not None
    assert detached.linked_transaction_ids == ()
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
        BucketEventType.LEDGER_TRANSACTION_REMOVED,
        BucketEventType.LEDGER_TRANSACTION_REMOVED,
        BucketEventType.LEDGER_CATALOGUE_RESET,
    ]
    assert events[-1].event_type is BucketEventType.LEDGER_CATALOGUE_RESET
    assert events[-1].payload["removed_transaction_count"] == "2"
    assert events[-1].payload["reason"] == "contaminated import batch"


def test_reset_ledger_catalogue_clears_a_large_ledger_without_payload_overflow(
    secure_objects: SecureObjectRepository,
) -> None:
    """A reset on a realistic (10+ row) ledger must succeed and clear every row.

    The reset bucket event used to inline every removed id into a single
    joined ``removed_transaction_ids`` payload value capped at 500 chars, so
    a ledger of ~8 or more rows overflowed the cap and the reset raised a
    pydantic ValidationError before any state was cleared. The per-id record
    is carried by the individual ``LEDGER_TRANSACTION_REMOVED`` events and the
    typed ``removed_transaction_ids`` on the report, never the capped payload.
    """
    transaction_repository, event_repository = _repositories(secure_objects)
    row_count = 12
    created_ids: list[str] = []
    for index in range(row_count):
        created = create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 1),
                amount=Decimal("10.00") + Decimal(index),
                direction=TransactionDirection.OUTGOING,
                description=f"bulk reset row {index}",
                idempotency_key=f"bulk-reset-{index}",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 4, 9, index, tzinfo=UTC),
        )
        created_ids.append(created.ref.transaction_id)

    assert len(transaction_repository.load().transactions) == row_count

    report = reset_ledger_catalogue(
        bucket_id="bucket-a",
        actor="operator-A",
        reason="bulk wipe",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert report.reset is True
    assert report.removed_transaction_ids == tuple(sorted(created_ids))
    assert transaction_repository.load().transactions == {}
    reset_events = [
        event
        for event in event_repository.load().for_bucket("bucket-a")
        if event.event_type is BucketEventType.LEDGER_CATALOGUE_RESET
    ]
    assert len(reset_events) == 1
    assert reset_events[0].payload["removed_transaction_count"] == str(row_count)
    removed_events = [
        event
        for event in event_repository.load().for_bucket("bucket-a")
        if event.event_type is BucketEventType.LEDGER_TRANSACTION_REMOVED
    ]
    assert {event.object_id for event in removed_events} == set(created_ids)
