"""Apply-path tests for saturated LLM classification suggestions."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import NoReturn

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.tests._llm_saturation_support import (
    _BUCKET,
    _NOW,
    _saturating_subprocess_classifier,
    _seed_unclassified,
)
from cadrumo.adapters.persistence.profile.tests._llm_saturation_support import repositories as repositories
from cadrumo.adapters.persistence.profile.tests.ledger_action_create_support import ledger_ports_for_test
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.application.ledger.evidence_textlayer_ports import EvidenceTextLayerPorts
from cadrumo.application.ledger.llm_classification import (
    apply_saturated_llm_classification,
    saturate_llm_classification,
)
from cadrumo.application.ledger.llm_classification_ports import LLMClassificationPorts
from cadrumo.core.config import load_settings
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.domain.transactions.enums import BusinessClassification
from cadrumo.domain.transactions.errors import TransactionValidationError

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]
__all__ = ["repositories"]


def _unused_llm_port(*_args: object, **_kwargs: object) -> NoReturn:
    """Fail loudly if a no-evidence saturation test reaches a reader port."""
    raise AssertionError("the no-evidence saturation path must not use this reader port")


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


def test_apply_persists_derived_substrate_with_llm_provenance(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    repository, events = repositories
    gross = Decimal("121.00")
    tx_id = _seed_unclassified(repository, amount=gross)
    with bundled_indexed_authority().operation() as operation:
        suggestion = saturate_llm_classification(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            operation=operation,
            classifier=_saturating_subprocess_classifier(
                iva_category=IvaCategory("domestic_general"), operation=operation
            ),
            transaction_repository=repository,
            settings=load_settings(),
            ports=_LLM_PORTS,
        )

    with ledger_ports_for_test(
        bucket_id=_BUCKET,
        objects=repository._objects,
        transaction_repository=repository,
        bucket_event_repository=events,
    ) as ports:
        result = apply_saturated_llm_classification(
            suggestion,
            bucket_id=_BUCKET,
            actor="operator-A",
            source_command="aeat app ledger classify --llm --saturate --apply",
            ports=ports,
            occurred_at=_NOW,
        )

    persisted = result.transaction
    assert persisted.business_classification is BusinessClassification.BUSINESS
    assert persisted.classified_by == "llm:claude:test-model"
    assert persisted.iva_category == IvaCategory("domestic_general")
    assert persisted.taxable_base == Decimal("100.00")
    assert persisted.iva_rate == Decimal("0.21")
    assert persisted.iva_amount == Decimal("21.00")
    reloaded = repository.load().get(tx_id)
    assert reloaded is not None
    assert reloaded.taxable_base is not None and reloaded.iva_amount is not None
    assert reloaded.taxable_base + reloaded.iva_amount == gross


def test_apply_non_derivable_persists_category_without_numbers(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    repository, events = repositories
    tx_id = _seed_unclassified(repository)
    with bundled_indexed_authority().operation() as operation:
        suggestion = saturate_llm_classification(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            operation=operation,
            classifier=_saturating_subprocess_classifier(
                iva_category=IvaCategory("intra_community_supply"), operation=operation
            ),
            transaction_repository=repository,
            settings=load_settings(),
            ports=_LLM_PORTS,
        )

    with ledger_ports_for_test(
        bucket_id=_BUCKET,
        objects=repository._objects,
        transaction_repository=repository,
        bucket_event_repository=events,
    ) as ports:
        result = apply_saturated_llm_classification(
            suggestion,
            bucket_id=_BUCKET,
            actor="operator-A",
            source_command="aeat app ledger classify --llm --saturate --apply",
            ports=ports,
            occurred_at=_NOW,
        )

    persisted = result.transaction
    assert persisted.iva_category == IvaCategory("intra_community_supply")
    assert persisted.taxable_base is None
    assert persisted.iva_amount is None
    assert persisted.classified_by == "llm:claude:test-model"


def test_apply_mixed_without_business_pct_refuses(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    repository, events = repositories
    tx_id = _seed_unclassified(repository)
    with bundled_indexed_authority().operation() as operation:
        suggestion = saturate_llm_classification(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            operation=operation,
            classifier=_saturating_subprocess_classifier(
                classification=BusinessClassification.MIXED,
                iva_category=IvaCategory("domestic_general"),
                business_pct=None,
                operation=operation,
            ),
            transaction_repository=repository,
            settings=load_settings(),
            ports=_LLM_PORTS,
        )

    with (
        pytest.raises(TransactionValidationError, match="requires a business percentage"),
        ledger_ports_for_test(
            bucket_id=_BUCKET,
            objects=repository._objects,
            transaction_repository=repository,
            bucket_event_repository=events,
        ) as ports,
    ):
        apply_saturated_llm_classification(
            suggestion,
            bucket_id=_BUCKET,
            actor="operator-A",
            source_command="aeat app ledger classify --llm --saturate --apply",
            ports=ports,
            occurred_at=_NOW,
        )


def test_apply_mixed_uses_proposed_business_pct(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    repository, events = repositories
    tx_id = _seed_unclassified(repository)
    with bundled_indexed_authority().operation() as operation:
        suggestion = saturate_llm_classification(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            operation=operation,
            classifier=_saturating_subprocess_classifier(
                classification=BusinessClassification.MIXED,
                iva_category=IvaCategory("domestic_general"),
                business_pct=Decimal("0.6"),
                operation=operation,
            ),
            transaction_repository=repository,
            settings=load_settings(),
            ports=_LLM_PORTS,
        )

    with ledger_ports_for_test(
        bucket_id=_BUCKET,
        objects=repository._objects,
        transaction_repository=repository,
        bucket_event_repository=events,
    ) as ports:
        result = apply_saturated_llm_classification(
            suggestion,
            bucket_id=_BUCKET,
            actor="operator-A",
            source_command="aeat app ledger classify --llm --saturate --apply",
            ports=ports,
            occurred_at=_NOW,
        )

    assert result.transaction.business_classification is BusinessClassification.MIXED
    assert result.transaction.business_pct == Decimal("0.6")
