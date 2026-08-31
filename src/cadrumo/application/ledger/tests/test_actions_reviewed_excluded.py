"""Reviewed-excluded review-state action tests.

Exercises :func:`~cadrumo.application.ledger.actions_lifecycle.mark_transaction_reviewed_excluded`
against real encrypted repositories: the operator marks an active transaction as
deliberately excluded from filing, the uniform mutation quintet reflects the new
``excluded`` review status, the ``ledger.transaction.reviewed_excluded`` lifecycle
event emits, the classification persists across the encrypted boundary, and the
guards refuse a non-active or already-excluded row.
"""

from __future__ import annotations

import pytest

from ...review.filter import LedgerReviewStatus
from ..actions_lifecycle import mark_transaction_reviewed_excluded
from ..actions_manual import update_manual_transaction_fields
from ..models import ManualLedgerTransactionPatch
from ..review_projection import ledger_transaction_review_status
from ._action_test_support import (
    _BUCKET_ID,
    UTC,
    BucketEventType,
    BusinessClassification,
    Decimal,
    ManualLedgerTransactionCommand,
    SecureObjectRepository,
    TransactionDirection,
    TransactionValidationError,
    _repositories,
    archive_manual_transaction,
    create_manual_transaction,
    date,
    datetime,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _create_business_row(
    secure_objects: SecureObjectRepository,
    *,
    idempotency_key: str = "exclude-row",
    classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
):
    transaction_repository, event_repository = _repositories(secure_objects)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2026, 5, 1),
            amount=Decimal("50.00"),
            direction=TransactionDirection.OUTGOING,
            description="reimbursed personal card charge",
            business_classification=classification,
            business_pct=business_pct,
            idempotency_key=idempotency_key,
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    return transaction_repository, event_repository, created


def test_mark_reviewed_excluded_persists_state_quintet_and_event(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository, created = _create_business_row(secure_objects)

    result = mark_transaction_reviewed_excluded(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="not a business expense",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    # Uniform mutation quintet reflects the exclusion.
    assert result.ref.bucket_id == _BUCKET_ID
    assert result.ref.transaction_id == created.ref.transaction_id
    assert len(result.bucket_event_ids) == 1
    assert result.transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED
    assert ledger_transaction_review_status(result.transaction) is LedgerReviewStatus.EXCLUDED

    # Persisted across the encrypted boundary (roundtrip).
    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.business_classification is BusinessClassification.REVIEWED_EXCLUDED
    assert persisted.classified_by == "manual"
    assert ledger_transaction_review_status(persisted) is LedgerReviewStatus.EXCLUDED

    # Dedicated lifecycle event emitted with typed provenance payload.
    events = event_repository.load().for_bucket(_BUCKET_ID)
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_REVIEWED_EXCLUDED,
    ]
    assert events[-1].event_id == result.bucket_event_ids[0]
    assert events[-1].payload["previous_classification"] == BusinessClassification.BUSINESS.value
    assert events[-1].payload["business_classification"] == BusinessClassification.REVIEWED_EXCLUDED.value
    assert events[-1].payload["reason"] == "not a business expense"


def test_mark_reviewed_excluded_clears_business_pct_and_survives_roundtrip(
    secure_objects: SecureObjectRepository,
) -> None:
    """A MIXED row carries business_pct; excluding it must clear the coupled field.

    The business_pct-vs-MIXED coupling validator runs on load, so a persisted
    reviewed-excluded row that still carried a business_pct would fail to
    reload. The exclusion clears it, and the roundtrip proves the record loads.
    """
    transaction_repository, event_repository, created = _create_business_row(
        secure_objects,
        idempotency_key="exclude-mixed-row",
        classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.40"),
    )

    mark_transaction_reviewed_excluded(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.business_classification is BusinessClassification.REVIEWED_EXCLUDED
    assert persisted.business_pct is None


def test_mark_reviewed_excluded_is_reversible_by_reclassify(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository, created = _create_business_row(
        secure_objects,
        idempotency_key="exclude-reversible-row",
    )
    mark_transaction_reviewed_excluded(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    reincluded = update_manual_transaction_fields(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        patch=ManualLedgerTransactionPatch(business_classification=BusinessClassification.BUSINESS),
        actor="operator-A",
        source_command="aeat app ledger classify",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )

    assert reincluded.transaction.business_classification is BusinessClassification.BUSINESS
    assert ledger_transaction_review_status(reincluded.transaction) is LedgerReviewStatus.REVIEWED


def test_mark_reviewed_excluded_refuses_already_excluded(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository, created = _create_business_row(
        secure_objects,
        idempotency_key="exclude-idempotent-row",
    )
    mark_transaction_reviewed_excluded(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(TransactionValidationError, match="already reviewed-excluded"):
        mark_transaction_reviewed_excluded(
            bucket_id=_BUCKET_ID,
            transaction_id=created.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 2, 11, 0, tzinfo=UTC),
        )


def test_mark_reviewed_excluded_refuses_non_active_row(
    secure_objects: SecureObjectRepository,
) -> None:
    transaction_repository, event_repository, created = _create_business_row(
        secure_objects,
        idempotency_key="exclude-archived-row",
    )
    archive_manual_transaction(
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(TransactionValidationError, match="only active ledger transactions"):
        mark_transaction_reviewed_excluded(
            bucket_id=_BUCKET_ID,
            transaction_id=created.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 2, 11, 0, tzinfo=UTC),
        )
