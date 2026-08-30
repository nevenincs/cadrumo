"""Operator IVA substrate derivation tests for LLM saturation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....domain.categories import SpendingCategory
from ....domain.iva import IvaCategory
from ....domain.transactions.enums import BusinessClassification
from ....domain.transactions.errors import TransactionValidationError
from ....llm.suggestions import OperatorIvaDerivationResult
from ..llm_classification import derive_operator_iva_substrate
from ._llm_saturation_support import (
    _BUCKET,
    _NOW,
    _seed_business,
    _seed_unclassified,
)
from ._llm_saturation_support import (
    repositories as repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["repositories"]


def test_operator_derive_persists_substrate_with_derived_provenance(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    gross = Decimal("121.00")
    tx_id = _seed_business(repository, amount=gross)

    derivation = derive_operator_iva_substrate(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        iva_category=IvaCategory.DOMESTIC_GENERAL,
        actor="operator-A",
        source_command="aeat app ledger classify --iva-category --saturate",
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    assert isinstance(derivation, OperatorIvaDerivationResult)
    assert derivation.derivable is True
    assert derivation.iva_rate == Decimal("0.21")
    assert derivation.taxable_base == Decimal("100.00")
    assert derivation.iva_amount == Decimal("21.00")
    assert derivation.result is not None

    reloaded = repository.load().get(tx_id)
    assert reloaded is not None
    assert reloaded.classified_by == "derived:iva-category"
    assert reloaded.business_classification is BusinessClassification.BUSINESS
    assert reloaded.category_id == SpendingCategory.ARRENDAMIENTO_LOCAL.value
    assert reloaded.iva_category is IvaCategory.DOMESTIC_GENERAL
    assert reloaded.taxable_base is not None and reloaded.iva_amount is not None
    assert reloaded.taxable_base + reloaded.iva_amount == gross


def test_operator_derive_non_derivable_returns_reason_and_leaves_row_unmutated(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    tx_id = _seed_business(repository)

    derivation = derive_operator_iva_substrate(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        actor="operator-A",
        source_command="aeat app ledger classify --iva-category --saturate",
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    assert derivation.derivable is False
    assert derivation.result is None
    assert derivation.iva_rate is None
    assert derivation.taxable_base is None
    assert derivation.note

    reloaded = repository.load().get(tx_id)
    assert reloaded is not None
    assert reloaded.iva_category is None
    assert reloaded.taxable_base is None
    assert reloaded.iva_amount is None
    assert reloaded.classified_by != "derived:iva-category"


def test_operator_derive_refuses_non_business_row(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    tx_id = _seed_unclassified(repository)

    with pytest.raises(TransactionValidationError, match="business transaction"):
        derive_operator_iva_substrate(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            iva_category=IvaCategory.DOMESTIC_GENERAL,
            actor="operator-A",
            source_command="aeat app ledger classify --iva-category --saturate",
            transaction_repository=repository,
            bucket_event_repository=events,
            occurred_at=_NOW,
        )


def test_operator_derive_zero_rated_category_derives_zero_iva(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    gross = Decimal("121.00")
    tx_id = _seed_business(repository, amount=gross)

    derivation = derive_operator_iva_substrate(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        iva_category=IvaCategory.DOMESTIC_ZERO,
        actor="operator-A",
        source_command="aeat app ledger classify --iva-category --saturate",
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    assert derivation.derivable is True
    assert derivation.iva_rate == Decimal("0")
    assert derivation.taxable_base == gross
    assert derivation.iva_amount == Decimal("0.00")
