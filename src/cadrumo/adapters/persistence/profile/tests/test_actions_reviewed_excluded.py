"""Reviewed-excluded review-state action tests.

Exercises :func:`~cadrumo.application.ledger.actions_lifecycle.mark_transaction_reviewed_excluded`
against real encrypted repositories: the operator marks an active transaction as
deliberately excluded from filing, the uniform mutation quintet reflects the new
``excluded`` review status, the ``ledger.transaction.reviewed_excluded`` lifecycle
event emits, the classification persists across the encrypted boundary, and the
guards refuse a non-active or already-excluded row.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.actions_lifecycle import archive_manual_transaction, mark_transaction_reviewed_excluded
from cadrumo.application.ledger.actions_manual import create_manual_transaction, update_manual_transaction_fields
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from cadrumo.application.ledger.review_projection import ledger_transaction_review_status
from cadrumo.application.review.filter import LedgerReviewStatus
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.errors import TransactionValidationError

from .ledger_action_create_support import ledger_ports_for_test
from .ledger_action_persistence_support import (
    _BUCKET_ID,
    _repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _create_manual_transaction(secure_objects: SecureObjectRepository, command: Any, **kwargs: Any) -> Any:
    transaction_repository = kwargs.pop("transaction_repository")
    bucket_event_repository = kwargs.pop("bucket_event_repository")
    with ledger_ports_for_test(
        bucket_id=command.bucket_id,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=bucket_event_repository,
    ) as ports:
        return create_manual_transaction(
            command,
            ports=ports,
            **kwargs,
        )


def _update_manual_transaction_fields(secure_objects: SecureObjectRepository, **kwargs: Any) -> Any:
    transaction_repository = kwargs.pop("transaction_repository")
    bucket_event_repository = kwargs.pop("bucket_event_repository")
    with ledger_ports_for_test(
        bucket_id=kwargs["bucket_id"],
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=bucket_event_repository,
    ) as ports:
        return update_manual_transaction_fields(ports=ports, **kwargs)


def _archive_manual_transaction(secure_objects: SecureObjectRepository, **kwargs: Any) -> Any:
    transaction_repository = kwargs.pop("transaction_repository")
    bucket_event_repository = kwargs.pop("bucket_event_repository")
    with ledger_ports_for_test(
        bucket_id=kwargs["bucket_id"],
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=bucket_event_repository,
    ) as ports:
        return archive_manual_transaction(ports=ports, **kwargs)


def _load_transactions(transaction_repository: Any) -> Any:
    """Read the stored catalogue back under the pinned authority stored rows decode against."""
    with bundled_indexed_authority().operation():
        return transaction_repository.load()


def _mark_reviewed_excluded(secure_objects: SecureObjectRepository, **kwargs: Any) -> Any:
    """Exclude through the real action, with the finalized-modelo guard's ports wired."""
    with ledger_ports_for_test(
        bucket_id=kwargs["bucket_id"],
        objects=secure_objects,
        transaction_repository=kwargs["transaction_repository"],
        bucket_event_repository=kwargs["bucket_event_repository"],
    ) as ports:
        return mark_transaction_reviewed_excluded(
            work_unit_repository=ports.work_unit_repository,
            calculation_repository=ports.calculation_repository,
            **kwargs,
        )


def _create_business_row(
    secure_objects: SecureObjectRepository,
    *,
    idempotency_key: str = "exclude-row",
    classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
):
    transaction_repository, event_repository = _repositories(secure_objects)
    created = _create_manual_transaction(
        secure_objects,
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

    result = _mark_reviewed_excluded(
        secure_objects,
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
    persisted = _load_transactions(transaction_repository).get(created.ref.transaction_id)
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

    _mark_reviewed_excluded(
        secure_objects,
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    persisted = _load_transactions(transaction_repository).get(created.ref.transaction_id)
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
    _mark_reviewed_excluded(
        secure_objects,
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    reincluded = _update_manual_transaction_fields(
        secure_objects,
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
    _mark_reviewed_excluded(
        secure_objects,
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(TransactionValidationError, match="already reviewed-excluded"):
        _mark_reviewed_excluded(
            secure_objects,
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
    _archive_manual_transaction(
        secure_objects,
        bucket_id=_BUCKET_ID,
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(TransactionValidationError, match="only active ledger transactions"):
        _mark_reviewed_excluded(
            secure_objects,
            bucket_id=_BUCKET_ID,
            transaction_id=created.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 2, 11, 0, tzinfo=UTC),
        )
