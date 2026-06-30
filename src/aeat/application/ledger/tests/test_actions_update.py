"""Manual ledger transaction application tests split by workflow."""

from __future__ import annotations

import pytest

from ._action_test_support import (
    _BUCKET_ID,
    POST_UPDATE_EVENT_PAYLOADS,
    PRESERVED_CREATE_AUDIT_FIELDS,
    UPDATED_FIELD_EXPECTATIONS,
    UTC,
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    BusinessClassification,
    CalculationRevisionCatalogueRepository,
    Decimal,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
    SecureObjectRepository,
    SpendingCategory,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionValidationError,
    UsageRatioProfile,
    WorkUnitCatalogueRepository,
    _repositories,
    attach_manual_transaction_evidence,
    create_manual_transaction,
    dataclass,
    date,
    datetime,
    persist_verified_revision_citing_transaction,
    purchase_invoice,
    update_manual_transaction,
    update_manual_transaction_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True, slots=True)
class _UpdateManualOutcome:
    """Bundle returned by _drive_update_manual_transaction.

    Captures the create + update results, the post-update catalogue
    state, and the loaded bucket events for the focused tests to
    share without duplicating the two-command scenario.
    """

    created: ManualLedgerTransactionResult
    updated: ManualLedgerTransactionResult
    reloaded: TransactionCatalogue
    events: tuple[BucketEvent, ...]


def _drive_update_manual_transaction(secure_objects: SecureObjectRepository) -> _UpdateManualOutcome:
    """Run the canonical create -> update scenario and bundle the observable state."""
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="draft description",
            idempotency_key="cash-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    updated = update_manual_transaction(
        transaction_id=created.ref.transaction_id,
        command=ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("60.00"),
            direction=TransactionDirection.OUTGOING,
            description="corrected description",
            business_classification=BusinessClassification.MIXED,
            business_pct=Decimal("0.50"),
            notes="corrected cash amount",
            actor="operator-B",
            source_command="aeat app ledger update",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )
    reloaded = transaction_repository.load()
    events = tuple(event_repository.load().for_bucket(_BUCKET_ID))
    return _UpdateManualOutcome(created=created, updated=updated, reloaded=reloaded, events=events)


def test_update_manual_transaction_retires_previous_transaction_id_from_catalogue(
    secure_objects: SecureObjectRepository,
) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert outcome.created.ref.transaction_id not in outcome.reloaded.transactions


def test_update_manual_transaction_persists_replacement_transaction_id(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert outcome.updated.ref.transaction_id in outcome.reloaded.transactions


@pytest.mark.parametrize(("attr_path", "expected"), UPDATED_FIELD_EXPECTATIONS)
def test_update_manual_transaction_replaces_field(
    secure_objects: SecureObjectRepository,
    attr_path: str,
    expected: object,
) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    actual: object = outcome.updated.transaction
    for segment in attr_path.split("."):
        actual = getattr(actual, segment)
    assert actual == expected


@pytest.mark.parametrize("attr", PRESERVED_CREATE_AUDIT_FIELDS)
def test_update_manual_transaction_preserves_original_audit_field(
    secure_objects: SecureObjectRepository,
    attr: str,
) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert getattr(outcome.updated.transaction, attr) == getattr(outcome.created.transaction, attr)


def test_update_manual_transaction_records_edit_lineage_entry(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    entry = outcome.updated.transaction.edit_lineage[-1]
    assert entry.previous_transaction_id == outcome.created.ref.transaction_id
    assert entry.actor == "operator-B"
    assert entry.source_command == "aeat app ledger update"
    assert entry.bucket_event_id == outcome.updated.bucket_event_ids[0]


def test_update_manual_transaction_emits_expected_event_chain(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert [event.event_type for event in outcome.events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_UPDATED,
        BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
        BucketEventType.LEDGER_TRANSACTION_ALLOCATED,
    ]


def test_update_manual_transaction_links_update_events_to_result(secure_objects: SecureObjectRepository) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert [event.event_id for event in outcome.events[1:]] == list(outcome.updated.bucket_event_ids)


@pytest.mark.parametrize(("event_index", "payload_key", "expected"), POST_UPDATE_EVENT_PAYLOADS)
def test_update_manual_transaction_event_payload_marks_mutation_kind(
    secure_objects: SecureObjectRepository,
    event_index: int,
    payload_key: str,
    expected: str,
) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert outcome.events[event_index].payload[payload_key] == expected


def test_update_manual_transaction_edit_event_references_previous_transaction(
    secure_objects: SecureObjectRepository,
) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert outcome.events[1].payload["previous_transaction_id"] == outcome.created.ref.transaction_id


def test_update_manual_transaction_post_update_events_target_new_transaction_id(
    secure_objects: SecureObjectRepository,
) -> None:
    outcome = _drive_update_manual_transaction(secure_objects)
    assert {event.object_id for event in outcome.events[1:]} == {outcome.updated.ref.transaction_id}


def test_update_manual_transaction_fields_applies_typed_patch_through_backend(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("75.00"),
            direction=TransactionDirection.OUTGOING,
            description="pending row",
            idempotency_key="typed-patch",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    updated = update_manual_transaction_fields(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        patch=ManualLedgerTransactionPatch(
            description="classified row",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            # 75.00 gross inverse-split at 21% -> 61.98 base + 13.02 IVA
            # (keeps the gross == base + iva Transaction invariant).
            taxable_base=Decimal("61.98"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("13.02"),
        ),
        actor="operator-C",
        source_command="aeat app ledger classify",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
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
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 7, 15, 8, 0, tzinfo=UTC),
    )

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
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 7, 16, 10, 0, tzinfo=UTC),
    )

    assert created.transaction.source_jurisdiction == "FR"
    assert updated.transaction.source_jurisdiction == "FR"
    assert transaction_repository.load().transactions[updated.ref.transaction_id].source_jurisdiction == "FR"


def test_update_manual_transaction_fields_clears_tax_facts_for_personal_reclassification(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
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
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    updated = update_manual_transaction_fields(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        patch=ManualLedgerTransactionPatch(business_classification=BusinessClassification.PERSONAL),
        actor="operator-C",
        source_command="aeat app ledger classify",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
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


def test_update_manual_transaction_emits_purchase_evidence_attachment_event(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    purchase_evidence = purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            idempotency_key="evidence-attach",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    updated = update_manual_transaction(
        transaction_id=created.ref.transaction_id,
        command=ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            purchase_invoice_evidence_id=purchase_evidence.invoice_id,
            actor="operator-B",
            source_command="aeat app ledger attach",
            idempotency_key="evidence-attach",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert updated.transaction.purchase_invoice_evidence_id == purchase_evidence.invoice_id
    assert updated.transaction.evidence_provenance[-1].evidence_id == purchase_evidence.invoice_id
    assert updated.transaction.evidence_provenance[-1].bucket_event_id == updated.bucket_event_ids[0]
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
    ]
    assert events[-1].object_type is BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE
    assert events[-1].object_id == purchase_evidence.invoice_id
    assert events[-1].payload["transaction_id"] == updated.ref.transaction_id
    assert events[-1].payload["mutation_kind"] == "purchase_invoice_evidence_attached"


def test_attach_manual_transaction_evidence_delegates_to_validated_backend_patch(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    purchase_evidence = purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            idempotency_key="evidence-helper-attach",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    attached = attach_manual_transaction_evidence(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        purchase_invoice_evidence_id=purchase_evidence.invoice_id,
        actor="operator-B",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert attached.transaction.purchase_invoice_evidence_id == purchase_evidence.invoice_id
    assert attached.transaction.evidence_provenance[-1].evidence_kind == "purchase_invoice_evidence"
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
    ]


def test_update_manual_transaction_mixed_edit_and_evidence_lineage_uses_evidence_event(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    purchase_evidence = purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            idempotency_key="mixed-evidence-attach",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    updated = update_manual_transaction(
        transaction_id=created.ref.transaction_id,
        command=ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina corrected",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            purchase_invoice_evidence_id=purchase_evidence.invoice_id,
            actor="operator-B",
            source_command="aeat app ledger attach",
            idempotency_key="mixed-evidence-attach",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    events = event_repository.load().for_bucket(_BUCKET_ID)
    attach_event = next(
        event for event in events if event.event_type is BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED
    )
    assert updated.transaction.edit_lineage[-1].bucket_event_id != attach_event.event_id
    assert updated.transaction.evidence_provenance[-1].bucket_event_id == attach_event.event_id


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
    """Patching ``business_classification`` with the same value the record
    already carries (reaffirm=False, the default) must return the stored
    transaction unchanged and emit no new bucket events.

    This is the contract re-affirmation no-op bypass: ``_command_matches_current``
    detects the identity and ``_result`` returns the stored value directly
    rather than routing through ``update_manual_transaction``."""

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

    # The guard returned the stored transaction; the transaction_id must be
    # unchanged and no new events must have been written.
    assert result.transaction.transaction_id == created.ref.transaction_id
    assert result.bucket_event_ids == ()
    event_count_after = len(list(event_repository.load().for_bucket(_BUCKET_ID)))
    assert event_count_after == event_count_before


def test_update_manual_transaction_fields_reaffirm_true_bypasses_outer_guard_but_inner_guard_still_applies(
    secure_objects: SecureObjectRepository,
) -> None:
    """``reaffirm=True`` bypasses the outer ``_command_matches_current`` no-op
    guard but does NOT bypass the inner ``update_manual_transaction`` mutation
    guard.  A field-for-field-identical command therefore still raises
    ``TransactionValidationError`` because no observable mutation is produced.

    The distinction: ``reaffirm=False`` (default) silently returns the stored
    transaction; ``reaffirm=True`` raises loudly from the inner domain layer,
    making the operator's intent explicit while still enforcing the mutation
    invariant.  The CLI ``--reaffirm`` flag is designed for the case where the
    operator wants to re-apply a classification that includes at least one net
    change (e.g. the same classification with updated tax fields)."""

    transaction_repository, event_repository = _repositories(secure_objects)
    created = _create_classified_transaction(transaction_repository, event_repository)

    # Identical-command re-affirmation: outer guard skipped but inner guard fires.
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
    """``reaffirm=True`` with a net-change patch (same classification, updated
    notes) skips the outer guard and succeeds through the inner guard.

    This is the intended ``--reaffirm`` workflow: the operator re-applies a
    classification while simultaneously correcting another field."""

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
    """Anti-tautology: when the patched ``business_classification`` differs
    from the stored value the no-op guard must NOT fire, even with
    ``reaffirm=False``.

    A BUSINESS row re-classified as PERSONAL must result in a persisted
    mutation with new events regardless of the reaffirm flag."""

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

    # The classification must have changed — the guard correctly saw the
    # values differ and let the mutation proceed.
    assert result.transaction.business_classification is BusinessClassification.PERSONAL
    assert result.bucket_event_ids != ()
