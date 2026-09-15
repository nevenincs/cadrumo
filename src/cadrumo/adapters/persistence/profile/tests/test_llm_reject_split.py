"""Split-suggestion rejection tests for ledger LLM decisions."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import NoReturn

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.tests._llm_evidence_split_support import (
    _BUCKET,
    _NOW,
    _seed_parent,
    _split_subprocess_proposer,
    _two_line_proposal,
)
from cadrumo.adapters.persistence.profile.tests._llm_evidence_split_support import repositories as repositories
from cadrumo.adapters.persistence.profile.tests.ledger_action_create_support import ledger_ports_for_test
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.evidence_textlayer_ports import EvidenceTextLayerPorts
from cadrumo.application.ledger.llm_classification import (
    apply_evidence_split,
    reject_llm_suggestion,
    suggest_evidence_split,
)
from cadrumo.application.ledger.llm_classification_ports import LLMClassificationPorts, LLMClassificationSuggestion
from cadrumo.core.config import load_settings
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
)
from cadrumo.domain.calculations.registry.authority import (
    bundled_indexed_authority as _indexed_authority_for_test,
)
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from cadrumo.domain.transactions.errors import TransactionValidationError

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]
__all__ = ["repositories"]


def _unused_llm_port(*_args: object, **_kwargs: object) -> NoReturn:
    """Fail loudly if a no-evidence split test reaches an unused reader port."""
    raise AssertionError("the no-evidence split path must not use this reader port")


def _run_reader(run: Callable[[], object]) -> object:
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


def _classification_suggestion(tx_id: str) -> LLMClassificationSuggestion:
    return LLMClassificationSuggestion(
        transaction_id=tx_id,
        provenance="llm:claude:test-model",
        classification=BusinessClassification.BUSINESS,
        category=SpendingCategory._from_registry("material_oficina"),
        confidence=Decimal("0.9"),
        reason="looks like office supplies",
    )


def test_reject_split_suggestion_records_kind_split(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        repository, events, _objects = repositories
        tx_id = _seed_parent(repository)
        suggestion = suggest_evidence_split(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            proposer=_split_subprocess_proposer(response=_two_line_proposal(), operation=operation),
            transaction_repository=repository,
            read_evidence=False,
            operation=_authority_operation_for_test,
            settings=load_settings(),
            ports=_LLM_PORTS,
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
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        repository, events, _objects = repositories
        tx_id = _seed_parent(repository, amount=Decimal("121.00"))
        suggestion = suggest_evidence_split(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            proposer=_split_subprocess_proposer(response=_two_line_proposal(), operation=operation),
            transaction_repository=repository,
            read_evidence=False,
            operation=_authority_operation_for_test,
            settings=load_settings(),
            ports=_LLM_PORTS,
        )
        with ledger_ports_for_test(
            bucket_id=_BUCKET,
            objects=_objects,
            transaction_repository=repository,
            bucket_event_repository=events,
        ) as ports:
            apply_evidence_split(
                suggestion,
                bucket_id=_BUCKET,
                source_command="aeat app ledger split --llm --apply",
                ports=ports,
            )

        with pytest.raises(TransactionValidationError, match="active"):
            reject_llm_suggestion(
                _classification_suggestion(tx_id),
                bucket_id=_BUCKET,
                source_command="aeat app ledger classify --llm --reject",
                transaction_repository=repository,
                bucket_event_repository=events,
            )
