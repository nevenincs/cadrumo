"""No-split verdict tests for evidence-driven LLM split suggestions."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import NoReturn

import pytest

from .....application.ledger.evidence_textlayer_ports import EvidenceTextLayerPorts
from .....application.ledger.llm_classification import (
    apply_evidence_classification,
    apply_evidence_split,
    suggest_evidence_split,
)
from .....application.ledger.llm_classification_ports import LLMClassificationPorts
from .....core.config import load_settings
from .....core.model_catalogue import ModelRole
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.categories.spending_category import SpendingCategory
from .....domain.iva.schema import IvaCategory
from .....domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from .....domain.transactions.errors import TransactionValidationError
from ...storage.sql.secure_objects import SecureObjectRepository
from ..buckets import BucketEventHistoryRepository
from ..transactions import TransactionCatalogueRepository
from .ledger_action_create_support import ledger_ports_for_test
from .llm_evidence_split_support import (
    _BUCKET,
    _NOW,
    _seed_parent,
)
from .llm_evidence_split_support import (
    repositories as repositories,
)
from .llm_evidence_split_support import (
    single_line_proposal as _single_line_proposal,
)
from .llm_evidence_split_support import (
    split_subprocess_proposer as _split_subprocess_proposer,
)
from .llm_evidence_split_support import (
    two_line_proposal as _two_line_proposal,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

__all__ = ["repositories"]


def _unused_llm_port(*_args: object, **_kwargs: object) -> NoReturn:
    """Fail loudly if a no-evidence split test reaches an unused reader port."""
    raise AssertionError("the no-evidence split path must not use this reader port")


def _run_reader(_role: ModelRole, run: Callable[[], object]) -> object:
    return run()


def _record_classifier_run(run: Callable[[], object], _provider: str) -> object:
    return run()


_LLM_PORTS = LLMClassificationPorts(
    resolve_evidence_input=_unused_llm_port,
    text_layer_ports=EvidenceTextLayerPorts(extract_pages_text=_unused_llm_port),
    rasterise_pdf=_unused_llm_port,
    make_text_classifier=_unused_llm_port,
    make_vision_classifier=_unused_llm_port,
    run_reader=_run_reader,
    record_classifier_run=_record_classifier_run,
)


def test_single_child_suggestion_does_not_recommend_split(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    repository, _events, _objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))

    with bundled_indexed_authority().operation() as operation:
        suggestion = suggest_evidence_split(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            operation=operation,
            proposer=_split_subprocess_proposer(response=_single_line_proposal(), operation=operation),
            transaction_repository=repository,
            read_evidence=False,
            settings=load_settings(),
            ports=_LLM_PORTS,
        )

    assert suggestion.recommends_split is False
    assert len(suggestion.children) == 1
    assert suggestion.children[0].amount == Decimal("121.00")
    assert suggestion.children[0].iva_rate == Decimal("0.21")


def test_apply_evidence_split_refuses_a_no_split_verdict(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    repository, events, objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))
    with bundled_indexed_authority().operation() as operation:
        suggestion = suggest_evidence_split(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            operation=operation,
            proposer=_split_subprocess_proposer(response=_single_line_proposal(), operation=operation),
            transaction_repository=repository,
            read_evidence=False,
            settings=load_settings(),
            ports=_LLM_PORTS,
        )
    with (
        ledger_ports_for_test(
            bucket_id=_BUCKET,
            objects=objects,
            transaction_repository=repository,
            bucket_event_repository=events,
        ) as ports,
        pytest.raises(TransactionValidationError, match="no-split verdict"),
    ):
        apply_evidence_split(
            suggestion,
            bucket_id=_BUCKET,
            source_command="aeat app ledger split --llm --apply",
            ports=ports,
            occurred_at=_NOW,
        )


def test_apply_evidence_classification_writes_in_place_from_the_lone_child(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    repository, events, objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))
    with bundled_indexed_authority().operation() as operation:
        suggestion = suggest_evidence_split(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            operation=operation,
            proposer=_split_subprocess_proposer(response=_single_line_proposal(), operation=operation),
            transaction_repository=repository,
            read_evidence=False,
            settings=load_settings(),
            ports=_LLM_PORTS,
        )

    with ledger_ports_for_test(
        bucket_id=_BUCKET,
        objects=objects,
        transaction_repository=repository,
        bucket_event_repository=events,
    ) as ports:
        result = apply_evidence_classification(
            suggestion,
            bucket_id=_BUCKET,
            source_command="aeat app ledger classify --read-evidence --auto-split --apply",
            ports=ports,
            occurred_at=_NOW,
        )

    catalogue = repository.load()
    parent = catalogue.get(tx_id)
    assert parent is not None
    assert parent.lifecycle_state is TransactionLifecycleState.ACTIVE
    assert parent.business_classification is BusinessClassification.BUSINESS
    assert parent.category_id == SpendingCategory.from_registry("material_oficina").value
    assert parent.iva_category == IvaCategory("domestic_general")
    assert parent.iva_rate == Decimal("0.21")
    assert parent.taxable_base is not None and parent.iva_amount is not None
    assert parent.taxable_base + parent.iva_amount == Decimal("121.00")
    assert result.transaction.classified_by == "llm:claude:test-model"


def test_apply_evidence_classification_refuses_a_multi_child_split(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    repository, events, objects = repositories
    tx_id = _seed_parent(repository, amount=Decimal("121.00"))
    with bundled_indexed_authority().operation() as operation:
        suggestion = suggest_evidence_split(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            operation=operation,
            proposer=_split_subprocess_proposer(response=_two_line_proposal(), operation=operation),
            transaction_repository=repository,
            read_evidence=False,
            settings=load_settings(),
            ports=_LLM_PORTS,
        )
    with (
        ledger_ports_for_test(
            bucket_id=_BUCKET,
            objects=objects,
            transaction_repository=repository,
            bucket_event_repository=events,
        ) as ports,
        pytest.raises(TransactionValidationError, match="recommends a split"),
    ):
        apply_evidence_classification(
            suggestion,
            bucket_id=_BUCKET,
            source_command="aeat app ledger classify --read-evidence --auto-split --apply",
            ports=ports,
        )
