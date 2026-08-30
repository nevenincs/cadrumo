"""Split-suggestion rejection tests for ledger LLM decisions."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.buckets import BucketEventType
from ....domain.categories.spending_category import SpendingCategory
from ....domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from ....domain.transactions.errors import TransactionValidationError
from ....llm.suggestions import LLMClassificationSuggestion
from ..llm_classification import apply_evidence_split, reject_llm_suggestion, suggest_evidence_split
from ._llm_evidence_split_support import (
    _BUCKET,
    _NOW,
    _seed_parent,
    _split_subprocess_proposer,
    _two_line_proposal,
)
from ._llm_evidence_split_support import repositories as repositories

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["repositories"]


def _classification_suggestion(tx_id: str) -> LLMClassificationSuggestion:
    return LLMClassificationSuggestion(
        transaction_id=tx_id,
        provenance="llm:claude:test-model",
        classification=BusinessClassification.BUSINESS,
        category=SpendingCategory.MATERIAL_OFICINA,
        confidence=Decimal("0.9"),
        reason="looks like office supplies",
    )


def test_reject_split_suggestion_records_kind_split(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, _objects = repositories
    tx_id = _seed_parent(repository)
    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        proposer=_split_subprocess_proposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )

    result = reject_llm_suggestion(
        suggestion,
        bucket_id=_BUCKET,
        reason="do not split this",
        source_command="aeat app ledger classify --llm --reject",
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    assert result.suggestion_kind == "split"
    recorded = events.load().for_bucket(
        _BUCKET,
        event_types=(BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED,),
    )
    payload = recorded[0].payload
    assert payload["suggestion_kind"] == "split"
    assert payload["child_count"] == "2"
    txn = repository.load().get(tx_id)
    assert txn is not None
    assert txn.lifecycle_state is TransactionLifecycleState.ACTIVE


def test_reject_non_active_transaction_raises(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, _objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))
    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        proposer=_split_subprocess_proposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )
    apply_evidence_split(
        suggestion,
        bucket_id=_BUCKET,
        source_command="aeat app ledger split --llm --apply",
        transaction_repository=repository,
        bucket_event_repository=events,
    )

    with pytest.raises(TransactionValidationError, match="active"):
        reject_llm_suggestion(
            _classification_suggestion(tx_id),
            bucket_id=_BUCKET,
            source_command="aeat app ledger classify --llm --reject",
            transaction_repository=repository,
            bucket_event_repository=events,
        )
