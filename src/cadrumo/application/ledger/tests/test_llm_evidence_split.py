"""Real-behavior tests for the evidence-driven LLM split application path.

Exercises :func:`suggest_evidence_split` and :func:`apply_evidence_split`
against real SQLite persistence in an isolated profile, with a concrete
subprocess split proposer driven through the production classifier adapter.
Covers the Stage-3b split contract:

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

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.iva.schema import IvaCategory
from ....llm.suggestions import LLMSplitSuggestion
from ..llm_classification import suggest_evidence_split
from ._llm_evidence_split_support import (
    _BUCKET,
    _seed_parent,
    _split_subprocess_proposer,
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
        proposer=_split_subprocess_proposer(response=_two_line_proposal()),
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
        proposer=_split_subprocess_proposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )

    for child in suggestion.children:
        assert child.iva_category is IvaCategory.DOMESTIC_GENERAL
        assert child.rate_derivable is True
        # The registry rate, not a model-emitted number.
        assert child.iva_rate == Decimal("0.21")
        # base + iva reconstitutes the derived child amount to the cent.
        assert child.taxable_base is not None and child.iva_amount is not None
        assert child.taxable_base + child.iva_amount == child.amount


def test_suggest_no_linked_evidence_does_not_require_cloud_acknowledgement(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, _events, _objects = repositories
    # No linked evidence -> _resolve_evidence_text returns (None, None) and the
    # suggestion carries no evidence id; read_evidence does not require cloud
    # acknowledgement when there is nothing to read.
    tx_id = _seed_parent(repository)

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        proposer=_split_subprocess_proposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=True,
    )

    assert suggestion.evidence_id is None
