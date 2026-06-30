"""Apply-path tests for evidence-driven LLM split suggestions."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.iva import IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    TransactionCatalogueRepository,
    TransactionLifecycleState,
)
from .. import (
    LLMProvider,
    LLMSplitApplyResult,
    apply_evidence_split,
    suggest_evidence_split,
)
from ._llm_evidence_split_support import (
    _BUCKET,
    _NOW,
    _FixedSplitProposer,
    _seed_parent,
    _seed_received_invoice,
    _two_line_proposal,
)
from ._llm_evidence_split_support import repositories as repositories

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["repositories"]


def test_apply_splits_parent_and_classifies_children(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, _objects = repositories
    gross = Decimal("121.00")
    tx_id = _seed_parent(repository, amount=gross)

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        proposer=_FixedSplitProposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )
    result = apply_evidence_split(
        suggestion,
        bucket_id=_BUCKET,
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    assert isinstance(result, LLMSplitApplyResult)
    assert result.classified_child_count == 2
    assert len(result.child_transaction_ids) == 2

    catalogue = repository.load()
    parent = catalogue.get(tx_id)
    assert parent is not None
    assert parent.lifecycle_state is TransactionLifecycleState.SPLIT

    persisted_sum = Decimal("0")
    for child_id in result.child_transaction_ids:
        child = catalogue.get(child_id)
        assert child is not None
        assert child.lifecycle_state is TransactionLifecycleState.ACTIVE
        assert child.business_classification is BusinessClassification.BUSINESS
        assert child.iva_category is IvaCategory.DOMESTIC_GENERAL_21
        assert child.iva_rate == Decimal("0.21")
        assert child.classified_by == "llm:claude:test-model"
        assert child.taxable_base is not None and child.iva_amount is not None
        assert child.taxable_base + child.iva_amount == child.raw.amount
        persisted_sum += child.raw.amount
    assert persisted_sum == gross


def test_apply_links_parent_invoice_evidence_to_each_child(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, objects = repositories
    evidence_id = _seed_received_invoice(objects)
    tx_id = _seed_parent(repository, evidence_id=evidence_id)

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        proposer=_FixedSplitProposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )
    result = apply_evidence_split(
        suggestion,
        bucket_id=_BUCKET,
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    catalogue = repository.load()
    for child_id in result.child_transaction_ids:
        child = catalogue.get(child_id)
        assert child is not None
        assert child.purchase_invoice_evidence_id == evidence_id


def test_apply_child_numbers_are_registry_derived_not_model(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, _objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("242.00"))

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        proposer=_FixedSplitProposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )
    result = apply_evidence_split(
        suggestion,
        bucket_id=_BUCKET,
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    catalogue = repository.load()
    children = []
    for child_id in result.child_transaction_ids:
        child = catalogue.get(child_id)
        assert child is not None
        children.append(child)
    assert sorted(child.raw.amount for child in children) == [Decimal("96.80"), Decimal("145.20")]
    for child in children:
        assert child.iva_rate == Decimal("0.21")
