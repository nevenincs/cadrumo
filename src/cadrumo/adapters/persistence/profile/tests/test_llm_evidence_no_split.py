"""No-split verdict tests for evidence-driven LLM split suggestions."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.tests._llm_evidence_split_support import (
    _BUCKET,
    _NOW,
    _seed_parent,
    _single_line_proposal,
    _split_subprocess_proposer,
    _two_line_proposal,
)
from cadrumo.adapters.persistence.profile.tests._llm_evidence_split_support import (
    repositories as repositories,
)
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.llm_classification import (
    apply_evidence_classification,
    apply_evidence_split,
    suggest_evidence_split,
)
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from cadrumo.domain.transactions.errors import TransactionValidationError

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

__all__ = ["repositories"]


def test_single_child_suggestion_does_not_recommend_split(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, _events, _objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        proposer=_split_subprocess_proposer(response=_single_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )

    assert suggestion.recommends_split is False
    assert len(suggestion.children) == 1
    assert suggestion.children[0].amount == Decimal("121.00")
    assert suggestion.children[0].iva_rate == Decimal("0.21")


def test_apply_evidence_split_refuses_a_no_split_verdict(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, _objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))
    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        proposer=_split_subprocess_proposer(response=_single_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )
    with pytest.raises(TransactionValidationError, match="no-split verdict"):
        apply_evidence_split(
            suggestion,
            bucket_id=_BUCKET,
            source_command="aeat app ledger split --llm --apply",
            transaction_repository=repository,
            bucket_event_repository=events,
            occurred_at=_NOW,
        )


def test_apply_evidence_classification_writes_in_place_from_the_lone_child(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, _objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))
    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        proposer=_split_subprocess_proposer(response=_single_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )

    result = apply_evidence_classification(
        suggestion,
        bucket_id=_BUCKET,
        source_command="aeat app ledger classify --read-evidence --auto-split --apply",
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    catalogue = repository.load()
    parent = catalogue.get(tx_id)
    assert parent is not None
    assert parent.lifecycle_state is TransactionLifecycleState.ACTIVE
    assert parent.business_classification is BusinessClassification.BUSINESS
    assert parent.category_id == SpendingCategory.MATERIAL_OFICINA.value
    assert parent.iva_category is IvaCategory.DOMESTIC_GENERAL
    assert parent.iva_rate == Decimal("0.21")
    assert parent.taxable_base is not None and parent.iva_amount is not None
    assert parent.taxable_base + parent.iva_amount == Decimal("121.00")
    assert result.transaction.classified_by == "llm:claude:test-model"


def test_apply_evidence_classification_refuses_a_multi_child_split(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, _events, _objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))
    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        proposer=_split_subprocess_proposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )
    with pytest.raises(TransactionValidationError, match="recommends a split"):
        apply_evidence_classification(
            suggestion,
            bucket_id=_BUCKET,
            source_command="aeat app ledger classify --read-evidence --auto-split --apply",
            transaction_repository=repository,
        )
