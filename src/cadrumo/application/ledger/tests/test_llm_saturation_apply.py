"""Apply-path tests for saturated LLM classification suggestions."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....domain.iva import IvaCategory
from ....domain.transactions import BusinessClassification, TransactionValidationError
from ..llm_classification import apply_saturated_llm_classification, saturate_llm_classification
from ._llm_saturation_support import (
    _BUCKET,
    _NOW,
    _saturating_subprocess_classifier,
    _seed_unclassified,
)
from ._llm_saturation_support import repositories as repositories

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["repositories"]


def test_apply_persists_derived_substrate_with_llm_provenance(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    gross = Decimal("121.00")
    tx_id = _seed_unclassified(repository, amount=gross)
    suggestion = saturate_llm_classification(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        classifier=_saturating_subprocess_classifier(iva_category=IvaCategory.DOMESTIC_GENERAL),
        transaction_repository=repository,
    )

    result = apply_saturated_llm_classification(
        suggestion,
        bucket_id=_BUCKET,
        actor="operator-A",
        source_command="aeat app ledger classify --llm --saturate --apply",
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    persisted = result.transaction
    assert persisted.business_classification is BusinessClassification.BUSINESS
    assert persisted.classified_by == "llm:claude:test-model"
    assert persisted.iva_category is IvaCategory.DOMESTIC_GENERAL
    assert persisted.taxable_base == Decimal("100.00")
    assert persisted.iva_rate == Decimal("0.21")
    assert persisted.iva_amount == Decimal("21.00")
    reloaded = repository.load().get(tx_id)
    assert reloaded is not None
    assert reloaded.taxable_base is not None and reloaded.iva_amount is not None
    assert reloaded.taxable_base + reloaded.iva_amount == gross


def test_apply_non_derivable_persists_category_without_numbers(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    tx_id = _seed_unclassified(repository)
    suggestion = saturate_llm_classification(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        classifier=_saturating_subprocess_classifier(iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY),
        transaction_repository=repository,
    )

    result = apply_saturated_llm_classification(
        suggestion,
        bucket_id=_BUCKET,
        actor="operator-A",
        source_command="aeat app ledger classify --llm --saturate --apply",
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    persisted = result.transaction
    assert persisted.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY
    assert persisted.taxable_base is None
    assert persisted.iva_amount is None
    assert persisted.classified_by == "llm:claude:test-model"


def test_apply_mixed_without_business_pct_refuses(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    tx_id = _seed_unclassified(repository)
    suggestion = saturate_llm_classification(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        classifier=_saturating_subprocess_classifier(
            classification=BusinessClassification.MIXED,
            iva_category=IvaCategory.DOMESTIC_GENERAL,
            business_pct=None,
        ),
        transaction_repository=repository,
    )

    with pytest.raises(TransactionValidationError, match="requires a business percentage"):
        apply_saturated_llm_classification(
            suggestion,
            bucket_id=_BUCKET,
            actor="operator-A",
            source_command="aeat app ledger classify --llm --saturate --apply",
            transaction_repository=repository,
            bucket_event_repository=events,
            occurred_at=_NOW,
        )


def test_apply_mixed_uses_proposed_business_pct(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    tx_id = _seed_unclassified(repository)
    suggestion = saturate_llm_classification(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        classifier=_saturating_subprocess_classifier(
            classification=BusinessClassification.MIXED,
            iva_category=IvaCategory.DOMESTIC_GENERAL,
            business_pct=Decimal("0.6"),
        ),
        transaction_repository=repository,
    )

    result = apply_saturated_llm_classification(
        suggestion,
        bucket_id=_BUCKET,
        actor="operator-A",
        source_command="aeat app ledger classify --llm --saturate --apply",
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    assert result.transaction.business_classification is BusinessClassification.MIXED
    assert result.transaction.business_pct == Decimal("0.6")
