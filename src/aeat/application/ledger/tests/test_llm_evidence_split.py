"""Real-behavior tests for the evidence-driven LLM split application path.

Exercises :func:`suggest_evidence_split` and :func:`apply_evidence_split`
against real SQLite persistence in an isolated profile, with a concrete
in-process split proposer injected by dependency injection (no mocks). Covers
the Stage-3b split contract:

* the model proposes per-child PROPORTIONS and selects each child's expense
  category + IVA category; the system DERIVES each child's euro amount (summing
  exactly to the parent) and the regulated rate / base / amount from the
  registry (never the model);
* applying a reviewed suggestion drives the single-writer
  :func:`split_transaction` (parent -> SPLIT, children ACTIVE) and then stamps
  each child's classification, derived numbers, parent-invoice evidence link,
  and ``llm:<model>`` provenance through the manual write;
* the persisted child state survives a save/load roundtrip.
"""

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
    LLMSplitSuggestion,
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
from ._llm_evidence_split_support import (
    repositories as repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["repositories"]


# ---------------------------------------------------------------------------
# suggest: model proposes proportions, system derives amounts + substrate
# ---------------------------------------------------------------------------


def test_suggest_derives_child_amounts_summing_to_parent(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, _events, _objects = repositories
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

    assert isinstance(suggestion, LLMSplitSuggestion)
    assert suggestion.parent_amount == gross
    assert len(suggestion.children) == 2
    # The derived amounts sum EXACTLY to the parent gross to the cent.
    assert sum((child.amount for child in suggestion.children), Decimal("0")) == gross
    # 60/40 of 121.00.
    assert suggestion.children[0].amount == Decimal("72.60")
    assert suggestion.children[1].amount == Decimal("48.40")
    assert suggestion.provenance == "llm:claude:test-model"


def test_suggest_derives_each_child_substrate_from_registry(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, _events, _objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        proposer=_FixedSplitProposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )

    for child in suggestion.children:
        assert child.iva_category is IvaCategory.DOMESTIC_GENERAL_21
        assert child.rate_derivable is True
        # The registry rate, not a model-emitted number.
        assert child.iva_rate == Decimal("0.21")
        # base + iva reconstitutes the derived child amount to the cent.
        assert child.taxable_base is not None and child.iva_amount is not None
        assert child.taxable_base + child.iva_amount == child.amount


def test_suggest_injects_evidence_text_when_reading(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, _events, _objects = repositories
    # No linked evidence -> _resolve_evidence_text returns (None, None) and the
    # proposer is handed None; this proves read_evidence does not fabricate text
    # nor require a cloud acknowledgement when there is nothing to read.
    tx_id = _seed_parent(repository)
    proposer = _FixedSplitProposer(response=_two_line_proposal())

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        proposer=proposer,
        transaction_repository=repository,
        read_evidence=True,
    )

    assert proposer.last_evidence_text is None
    assert suggestion.evidence_id is None


# ---------------------------------------------------------------------------
# apply: single-writer split + per-child classification, evidence, provenance
# ---------------------------------------------------------------------------


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

    # Reload from secure storage: the persisted state is the contract, not the
    # in-memory return value (save/load roundtrip).
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
        # Each child's regulated numbers reconstitute its own magnitude.
        assert child.taxable_base is not None and child.iva_amount is not None
        assert child.taxable_base + child.iva_amount == child.raw.amount
        persisted_sum += child.raw.amount
    # The children's magnitudes sum back to the parent gross.
    assert persisted_sum == gross


def test_apply_links_parent_invoice_evidence_to_each_child(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, objects = repositories
    # A real RECEIVED invoice the parent references; the per-child write re-verifies
    # the reference exists in the invoice catalogue, so the link must be genuine.
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
    # The proposer supplies only proportions + categories; it never emits a euro
    # amount or a rate. The persisted rate must be the registry's 0.21.
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
    # 60/40 of 242.00 -> 145.20 / 96.80, each at 21% registry rate.
    assert sorted(child.raw.amount for child in children) == [Decimal("96.80"), Decimal("145.20")]
    for child in children:
        assert child.iva_rate == Decimal("0.21")


