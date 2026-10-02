"""Encrypted, full-row fixtures for review read operation conformance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...application.review.enums import ReviewSeverity, ReviewState
from ...application.review.read_operation import (
    REVIEW_QUEUE_OPERATION_DEFINITION_ID,
    REVIEW_VIEW_OPERATION_DEFINITION_ID,
    ReviewQueueReadProjection,
    ReviewQueueReadRequest,
    ReviewQueueRowProjection,
    ReviewViewReadProjection,
    ReviewViewReadRequest,
)
from ...core.config import override_settings
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat


@dataclass(frozen=True, slots=True)
class ReviewReadConformanceCase:
    """Typed request and independently assembled encrypted-read expectation."""

    request: BaseModel
    expected_read: BaseModel


def _transaction() -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="review-read-native-row-1",
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=Decimal("12.34"),
        currency="EUR",
        counterparty="Fixture supplier",
        description="Review queue native row",
        provenance=RawProvenance(
            source_path=Path(__file__).resolve(),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            provider_name="review-read-fixture",
        ),
        raw_fields={"Concepto": "Review queue native row"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "classified_at": None,
            "classification_confidence": None,
        }
    )


def _expected_row(
    *,
    transaction: Transaction,
    profile_id: UUID,
    state: ReviewState,
    output_language: OutputLanguage,
) -> ReviewQueueRowProjection:
    with override_settings(cadrumo_output_language=output_language):
        summary = tr("review.transaction.summary") or "review.transaction.summary"
    effective_date = transaction.raw.value_date or transaction.raw.booked_date
    return ReviewQueueRowProjection(
        item_id=transaction.transaction_id,
        kind="ledger_transaction",
        source_kind="ledger_transaction",
        affected_object_id=transaction.transaction_id,
        bucket_id=str(profile_id),
        modelo=None,
        period=effective_date.isoformat()[:7],
        severity=ReviewSeverity.NORMAL,
        state=state,
        blocking=False,
        reason=summary,
        current_owner_surface="app ledger",
        canonical_next_command=f"aeat app ledger review {transaction.transaction_id}",
        since=transaction.classified_at or datetime.combine(effective_date, datetime.min.time(), tzinfo=UTC),
        summary=summary,
        legal_refs=(),
    )


def prepare_review_read_conformance_case(
    definition_id: str,
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    output_language: OutputLanguage = OutputLanguage.EN,
) -> ReviewReadConformanceCase:
    """Persist one real encrypted pending transaction and assemble each read result."""
    del operation  # This fixture writes a transaction; operation pinning is exercised by the worker reader.
    bucket_id = str(profile_id)
    repository = TransactionCatalogueRepository(bucket_id=bucket_id)
    source = _transaction()
    repository.save(TransactionCatalogue.from_transactions((source,)))
    persisted = repository.load().get(source.transaction_id)
    if persisted is None:
        raise AssertionError("encrypted transaction fixture did not survive canonical repository readback")

    if definition_id == REVIEW_QUEUE_OPERATION_DEFINITION_ID:
        request: BaseModel = ReviewQueueReadRequest(
            profile_id=profile_id,
            kinds=("ledger_transaction",),
            source_kinds=("ledger_transaction",),
            state=ReviewState.PENDING,
            output_language=output_language,
        )
        expected: BaseModel = ReviewQueueReadProjection(
            profile_id=profile_id,
            request=request,
            rows=(
                _expected_row(
                    transaction=persisted,
                    profile_id=profile_id,
                    state=ReviewState.PENDING,
                    output_language=output_language,
                ),
            ),
        )
    elif definition_id == REVIEW_VIEW_OPERATION_DEFINITION_ID:
        request = ReviewViewReadRequest(
            profile_id=profile_id,
            item_id=persisted.transaction_id,
            output_language=output_language,
        )
        expected = ReviewViewReadProjection(
            profile_id=profile_id,
            request=request,
            row=_expected_row(
                transaction=persisted,
                profile_id=profile_id,
                state=ReviewState.ALL,
                output_language=output_language,
            ),
        )
    else:
        raise ValueError(f"unsupported review read operation: {definition_id}")

    return ReviewReadConformanceCase(request=request, expected_read=expected)


__all__ = ["ReviewReadConformanceCase", "prepare_review_read_conformance_case"]
