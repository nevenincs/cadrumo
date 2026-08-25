"""Apply-path tests for evidence-driven LLM split suggestions."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.iva import IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    SplitRole,
    TransactionLifecycleState,
    TransactionValidationError,
)
from ....llm.suggestions import LLMSplitApplyResult
from ..actions_split_merge import split_transaction_with_classified_children
from ..llm_classification import apply_evidence_split, suggest_evidence_split
from ..models import ManualLedgerTransactionPatch, SplitChildCommand
from ._llm_evidence_split_support import (
    _BUCKET,
    _NOW,
    _seed_parent,
    _seed_received_invoice,
    _split_subprocess_proposer,
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
        proposer=_split_subprocess_proposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )
    result = apply_evidence_split(
        suggestion,
        bucket_id=_BUCKET,
        source_command="aeat app ledger split --llm --apply",
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
        assert child.iva_category is IvaCategory.DOMESTIC_GENERAL
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
        proposer=_split_subprocess_proposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )
    result = apply_evidence_split(
        suggestion,
        bucket_id=_BUCKET,
        source_command="aeat app ledger split --llm --apply",
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
        proposer=_split_subprocess_proposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )
    result = apply_evidence_split(
        suggestion,
        bucket_id=_BUCKET,
        source_command="aeat app ledger split --llm --apply",
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


def test_split_children_retain_lineage_and_evidence_provenance(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    # The atomic writer persists classification AND split lineage AND inherited
    # evidence provenance for every child in one transaction: no child is left
    # split-but-unclassified or lineage-less.
    repository, events, objects = repositories
    evidence_id = _seed_received_invoice(objects)
    tx_id = _seed_parent(repository, evidence_id=evidence_id)

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        proposer=_split_subprocess_proposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )
    result = apply_evidence_split(
        suggestion,
        bucket_id=_BUCKET,
        source_command="aeat app ledger split --llm --apply",
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    catalogue = repository.load()
    parent = catalogue.get(tx_id)
    assert parent is not None
    assert parent.lifecycle_state is TransactionLifecycleState.SPLIT
    assert parent.split_lineage is not None
    assert parent.split_lineage.role is SplitRole.PARENT
    for child_id in result.child_transaction_ids:
        child = catalogue.get(child_id)
        assert child is not None
        assert child.business_classification is BusinessClassification.BUSINESS
        assert child.split_lineage is not None
        assert child.split_lineage.role is SplitRole.CHILD
        assert child.split_lineage.split_group_id == result.split_group_id
        assert tx_id in child.split_lineage.sibling_transaction_ids
        assert child.purchase_invoice_evidence_id == evidence_id
        provenance_ids = {entry.evidence_id for entry in child.evidence_provenance}
        assert evidence_id in provenance_ids


def test_split_child_evidence_failure_leaves_everything_unchanged(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    # A parent carrying an evidence id whose record does not exist forces the
    # per-child evidence validation to fail during the atomic build. Because the
    # single save never runs, the parent stays ACTIVE, no child is persisted, and
    # the event history is unchanged.
    repository, events, _objects = repositories
    tx_id = _seed_parent(repository, evidence_id="nonexistent-evidence-record")
    events_before = dict(events.load().events)

    suggestion = suggest_evidence_split(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        proposer=_split_subprocess_proposer(response=_two_line_proposal()),
        transaction_repository=repository,
        read_evidence=False,
    )

    with pytest.raises(TransactionValidationError):
        apply_evidence_split(
            suggestion,
            bucket_id=_BUCKET,
            source_command="aeat app ledger split --llm --apply",
            transaction_repository=repository,
            bucket_event_repository=events,
            occurred_at=_NOW,
        )

    catalogue = repository.load()
    parent = catalogue.get(tx_id)
    assert parent is not None
    assert parent.lifecycle_state is TransactionLifecycleState.ACTIVE
    assert parent.split_lineage is None
    # Only the parent row exists: no split children were persisted.
    assert tuple(catalogue.transactions) == (tx_id,)
    assert events.load().events == events_before


def test_split_child_classification_that_changes_raw_id_is_refused(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    # A per-child classification patch that alters a raw movement field (here the
    # amount) would re-address the child under a new content-addressed id while
    # its siblings, lineage, and the result still name the stale id. The atomic
    # writer must refuse before persisting anything.
    repository, events, _objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))
    children = (
        SplitChildCommand(amount=Decimal("72.60"), description="child a"),
        SplitChildCommand(amount=Decimal("48.40"), description="child b"),
    )
    classifications = (
        ManualLedgerTransactionPatch(business_classification=BusinessClassification.BUSINESS),
        ManualLedgerTransactionPatch(
            business_classification=BusinessClassification.BUSINESS,
            amount=Decimal("40.00"),
        ),
    )

    with pytest.raises(TransactionValidationError, match="transaction id"):
        split_transaction_with_classified_children(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            children=children,
            child_classifications=classifications,
            classified_by="llm:test-model",
            actor="operator",
            source_command="aeat app ledger split --llm --apply",
            transaction_repository=repository,
            bucket_event_repository=events,
            occurred_at=_NOW,
        )

    catalogue = repository.load()
    parent = catalogue.get(tx_id)
    assert parent is not None
    assert parent.lifecycle_state is TransactionLifecycleState.ACTIVE
    assert tuple(catalogue.transactions) == (tx_id,)
