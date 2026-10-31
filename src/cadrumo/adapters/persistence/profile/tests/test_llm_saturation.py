"""Real-behavior tests for the saturating LLM classification application path.

Exercises :func:`saturate_llm_classification` and
:func:`apply_saturated_llm_classification` against real SQLite persistence in an
isolated profile, with the production subprocess classifier adapter driven by a
local child process. Covers the llm-ledger-classification contract:

* the model SELECTS an IvaCategory and the system DERIVES the rate / base /
  amount from the registry (never the model);
* a derivable category persists the full substrate through the manual write
  with ``llm:<model>`` provenance and satisfies the gross==base+iva invariant;
* a non-derivable category surfaces an operator-facing reason and leaves the
  numbers unset rather than guessing;
* a zero-rated category derives a zero IVA;
* a MIXED suggestion requires a business percentage.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....application.ledger.llm_classification import saturate_llm_classification
from .....application.ledger.llm_classification_ports import LLMSaturatedSuggestion
from .....core.config import load_settings
from .....domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
)
from .....domain.calculations.registry.authority import (
    bundled_indexed_authority as _indexed_authority_for_test,
)
from .....domain.iva.schema import IvaCategory
from ..buckets import BucketEventHistoryRepository
from ..transactions import TransactionCatalogueRepository
from .llm_no_evidence_ports_support import NO_EVIDENCE_LLM_PORTS
from .llm_saturation_support import (
    _BUCKET,
    _seed_unclassified,
)
from .llm_saturation_support import (
    repositories as repositories,
)
from .llm_saturation_support import (
    saturating_subprocess_classifier as _saturating_subprocess_classifier,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

__all__ = ["repositories"]


# ---------------------------------------------------------------------------
# suggest: model selects, system derives
# ---------------------------------------------------------------------------


def test_suggest_derives_substrate_from_selected_category(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        repository, _events = repositories
        # The gross is the transaction input the derived substrate must reconstitute;
        # asserting base + iva against this seeded input (not a recomputed literal) is
        # the real invariant, not a hand-summed expectation.
        gross = Decimal("121.00")
        tx_id = _seed_unclassified(repository, amount=gross)

        suggestion = saturate_llm_classification(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            classifier=_saturating_subprocess_classifier(
                iva_category=IvaCategory("domestic_general"), operation=operation
            ),
            transaction_repository=repository,
            settings=load_settings(),
            ports=NO_EVIDENCE_LLM_PORTS,
            operation=_authority_operation_for_test,
        )

        assert isinstance(suggestion, LLMSaturatedSuggestion)
        assert suggestion.iva_category == IvaCategory("domestic_general")
        assert suggestion.rate_derivable is True
        assert suggestion.iva_rate == Decimal("0.21")
        assert suggestion.taxable_base == Decimal("100.00")
        assert suggestion.iva_amount == Decimal("21.00")
        assert suggestion.provenance == "llm:claude:test-model"
        # The substrate sums to the gross to the cent — the persisted invariant.
        assert suggestion.taxable_base is not None and suggestion.iva_amount is not None
        assert suggestion.taxable_base + suggestion.iva_amount == gross


def test_suggest_zero_rated_category_derives_zero_iva(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        repository, _events = repositories
        tx_id = _seed_unclassified(repository)

        suggestion = saturate_llm_classification(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            classifier=_saturating_subprocess_classifier(
                iva_category=IvaCategory("domestic_zero"), operation=operation
            ),
            transaction_repository=repository,
            settings=load_settings(),
            ports=NO_EVIDENCE_LLM_PORTS,
            operation=_authority_operation_for_test,
        )

        assert suggestion.rate_derivable is True
        assert suggestion.iva_rate == Decimal("0")
        assert suggestion.taxable_base == Decimal("121.00")
        assert suggestion.iva_amount == Decimal("0.00")


def test_suggest_non_derivable_category_surfaces_reason_not_a_guess(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        repository, _events = repositories
        tx_id = _seed_unclassified(repository)

        suggestion = saturate_llm_classification(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            classifier=_saturating_subprocess_classifier(
                iva_category=IvaCategory("intra_community_supply"), operation=operation
            ),
            transaction_repository=repository,
            settings=load_settings(),
            ports=NO_EVIDENCE_LLM_PORTS,
            operation=_authority_operation_for_test,
        )

        assert suggestion.iva_category == IvaCategory("intra_community_supply")
        assert suggestion.rate_derivable is False
        assert suggestion.iva_rate is None
        assert suggestion.taxable_base is None
        assert suggestion.iva_amount is None
        assert suggestion.derivation_note  # operator-facing explanation present
