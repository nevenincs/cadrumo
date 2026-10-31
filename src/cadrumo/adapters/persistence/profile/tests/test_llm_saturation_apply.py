"""Apply-path tests for saturated LLM classification suggestions."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....application.ledger.llm_classification import (
    apply_saturated_llm_classification,
    saturate_llm_classification,
)
from .....core.config import load_settings
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.iva.schema import IvaCategory
from .....domain.transactions.enums import BusinessClassification
from .....domain.transactions.errors import TransactionValidationError
from ..buckets import BucketEventHistoryRepository
from ..transactions import TransactionCatalogueRepository
from .ledger_action_create_support import ledger_ports_for_test
from .llm_no_evidence_ports_support import NO_EVIDENCE_LLM_PORTS
from .llm_saturation_support import (
    _BUCKET,
    _NOW,
    _seed_unclassified,
)
from .llm_saturation_support import repositories as repositories
from .llm_saturation_support import (
    saturating_subprocess_classifier as _saturating_subprocess_classifier,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]
__all__ = ["repositories"]


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
            ports=NO_EVIDENCE_LLM_PORTS,
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
            ports=NO_EVIDENCE_LLM_PORTS,
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
            ports=NO_EVIDENCE_LLM_PORTS,
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
            ports=NO_EVIDENCE_LLM_PORTS,
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
