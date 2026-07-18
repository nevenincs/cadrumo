"""Real-behaviour tests for the LLM review workflow dispatch.

Proves ``execute_reviewed_decision`` COMPOSES the canonical ledger persistence
primitives (introducing no write path) and that the durable ``source_command``
audit label is DERIVED from the mandatory invocation origin, not defaulted.
Exercised against real SQLite persistence in an isolated profile, no mocks.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....domain.buckets import BucketEvent, BucketEventType
from ....domain.categories import SpendingCategory
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionValidationError,
)
from ....tests.secure_sql import isolated_runtime_profile
from .. import LLMClassificationSuggestion, LLMProvider
from .._llm_review_workflow import (
    LlmReviewDecision,
    LlmReviewInvocationOrigin,
    execute_reviewed_decision,
)
from .._models import ManualLedgerTransactionResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
_BUCKET = "bucket-review-workflow"


@pytest.fixture
def repositories(tmp_path: Path) -> Iterator[tuple[TransactionCatalogueRepository, BucketEventHistoryRepository]]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        objects = profile.repository
        yield (
            TransactionCatalogueRepository(bucket_id=_BUCKET, objects=objects),
            BucketEventHistoryRepository(objects=objects),
        )


def _seed_parent(repository: TransactionCatalogueRepository) -> str:
    raw = RawTransaction(
        provider_transaction_id="row-review",
        booked_date=date(2026, 5, 1),
        value_date=date(2026, 5, 1),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description="supplier invoice",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=_NOW,
            provider_name="csv",
        ),
        raw_fields={"Concepto": "supplier invoice"},
    )
    tx = Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )
    repository.save(TransactionCatalogue.from_transactions([tx]))
    return tx.transaction_id


def _classification_suggestion(tx_id: str) -> LLMClassificationSuggestion:
    return LLMClassificationSuggestion(
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        provenance="llm:claude:test-model",
        classification=BusinessClassification.BUSINESS,
        category=SpendingCategory.MATERIAL_OFICINA,
        confidence=Decimal("0.9"),
        reason="looks like office supplies",
    )


def _events_of(events: BucketEventHistoryRepository, event_type: BucketEventType) -> tuple[BucketEvent, ...]:
    return events.load().for_bucket(_BUCKET, event_types=(event_type,))


def test_apply_composes_classification_primitive_with_derived_source_command(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    tx_id = _seed_parent(repository)

    result = execute_reviewed_decision(
        _classification_suggestion(tx_id),
        origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
        decision=LlmReviewDecision.APPLY,
        bucket_id=_BUCKET,
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    # Delegation happened: the transaction is now classified in real storage.
    assert isinstance(result, ManualLedgerTransactionResult)
    assert result.transaction.transaction_id == tx_id
    assert result.transaction.business_classification is BusinessClassification.BUSINESS

    # Provenance is the DERIVED origin label, never an application default.
    classified = _events_of(events, BucketEventType.LEDGER_TRANSACTION_CLASSIFIED)
    assert len(classified) == 1
    assert classified[0].payload["source_command"] == "aeat app ledger classify --llm --apply"
    assert classified[0].payload["source_command"] == LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY.source_command


def test_reject_composes_reject_primitive_and_mutates_nothing(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    tx_id = _seed_parent(repository)

    execute_reviewed_decision(
        _classification_suggestion(tx_id),
        origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT,
        decision=LlmReviewDecision.REJECT,
        bucket_id=_BUCKET,
        reason="wrong category, this is personal",
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    rejected = _events_of(events, BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED)
    assert len(rejected) == 1
    assert rejected[0].payload["source_command"] == "aeat app ledger classify --llm --reject"
    # Reject mutates nothing: it emits no classification event.
    assert _events_of(events, BucketEventType.LEDGER_TRANSACTION_CLASSIFIED) == ()


def test_split_decision_on_classification_suggestion_refuses() -> None:
    with pytest.raises(TransactionValidationError):
        execute_reviewed_decision(
            _classification_suggestion("tx-1"),
            origin=LlmReviewInvocationOrigin.SPLIT_LLM,
            decision=LlmReviewDecision.SPLIT,
            bucket_id=_BUCKET,
        )


@pytest.mark.parametrize("decision", [LlmReviewDecision.SUGGEST, LlmReviewDecision.NO_SPLIT])
def test_non_persisting_terminals_refuse_durable_execution(decision: LlmReviewDecision) -> None:
    with pytest.raises(TransactionValidationError):
        execute_reviewed_decision(
            _classification_suggestion("tx-1"),
            origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
            decision=decision,
            bucket_id=_BUCKET,
        )
