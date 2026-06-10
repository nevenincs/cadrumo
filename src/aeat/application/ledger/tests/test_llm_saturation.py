"""Real-behavior tests for the saturating LLM classification application path.

Exercises :func:`saturate_llm_classification` and
:func:`apply_saturated_llm_classification` against real SQLite persistence in an
isolated profile, with a concrete in-process classifier injected by dependency
injection (no mocks). Covers the llm-ledger-classification contract:

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

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.buckets import BucketEventHistoryRepository
from ....domain.iva import IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    LLMClassificationResponse,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionValidationError,
)
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    LLMProvider,
    LLMSaturatedSuggestion,
    apply_saturated_llm_classification,
    saturate_llm_classification,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
_BUCKET = "bucket-a"


class _FixedSaturatingClassifier:
    """Concrete in-process classifier returning a fixed saturated response.

    Implements the :class:`aeat.domain.transactions.LLMClassifier` protocol
    (``decided_by`` + ``classify``) with no subprocess or network I/O, so the
    application + persistence stack runs end to end offline.
    """

    def __init__(
        self,
        *,
        classification: BusinessClassification = BusinessClassification.BUSINESS,
        iva_category: IvaCategory | None = IvaCategory.DOMESTIC_GENERAL_21,
        business_pct: Decimal | None = None,
        model: str = "test-model",
    ) -> None:
        self._classification = classification
        self._iva_category = iva_category
        self._business_pct = business_pct
        self._model = model

    @property
    def decided_by(self) -> str:
        return f"llm:claude:{self._model}"

    def classify(self, transaction: Transaction) -> LLMClassificationResponse:
        return LLMClassificationResponse(
            classification=self._classification,
            confidence=Decimal("0.9"),
            reason="grounded saturation fixture",
            iva_category=self._iva_category,
            business_pct=self._business_pct,
        )


@pytest.fixture
def repositories(tmp_path: Path) -> Iterator[tuple[TransactionCatalogueRepository, BucketEventHistoryRepository]]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        objects = profile.repository
        yield (
            TransactionCatalogueRepository(bucket_id=_BUCKET, objects=objects),
            BucketEventHistoryRepository(objects=objects),
        )


def _seed_unclassified(repository: TransactionCatalogueRepository, *, amount: Decimal = Decimal("121.00")) -> str:
    """Persist one ACTIVE, NOT_YET_PROCESSED transaction and return its id."""
    raw = RawTransaction(
        transaction_id="row-saturate-1",
        booked_date=date(2026, 5, 1),
        value_date=date(2026, 5, 1),
        amount=amount,
        currency="EUR",
        counterparty="Restaurante Sol",
        description="client lunch",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=_NOW,
            provider_name="csv",
        ),
        raw_fields={"Concepto": "client lunch"},
    )
    tx = Transaction.model_validate({"raw": raw, "direction": TransactionDirection.OUTGOING})
    repository.save(TransactionCatalogue.from_transactions([tx]))
    return tx.transaction_id


# ---------------------------------------------------------------------------
# suggest: model selects, system derives
# ---------------------------------------------------------------------------


def test_suggest_derives_substrate_from_selected_category(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, _events = repositories
    # The gross is the transaction input the derived substrate must reconstitute;
    # asserting base + iva against this seeded input (not a recomputed literal) is
    # the real invariant, not a hand-summed expectation.
    gross = Decimal("121.00")
    tx_id = _seed_unclassified(repository, amount=gross)

    suggestion = saturate_llm_classification(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        classifier=_FixedSaturatingClassifier(iva_category=IvaCategory.DOMESTIC_GENERAL_21),
        transaction_repository=repository,
    )

    assert isinstance(suggestion, LLMSaturatedSuggestion)
    assert suggestion.iva_category is IvaCategory.DOMESTIC_GENERAL_21
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
) -> None:
    repository, _events = repositories
    tx_id = _seed_unclassified(repository)

    suggestion = saturate_llm_classification(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        classifier=_FixedSaturatingClassifier(iva_category=IvaCategory.DOMESTIC_ZERO),
        transaction_repository=repository,
    )

    assert suggestion.rate_derivable is True
    assert suggestion.iva_rate == Decimal("0")
    assert suggestion.taxable_base == Decimal("121.00")
    assert suggestion.iva_amount == Decimal("0.00")


def test_suggest_non_derivable_category_surfaces_reason_not_a_guess(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, _events = repositories
    tx_id = _seed_unclassified(repository)

    suggestion = saturate_llm_classification(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        classifier=_FixedSaturatingClassifier(iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY),
        transaction_repository=repository,
    )

    assert suggestion.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY
    assert suggestion.rate_derivable is False
    assert suggestion.iva_rate is None
    assert suggestion.taxable_base is None
    assert suggestion.iva_amount is None
    assert suggestion.derivation_note  # operator-facing explanation present


# ---------------------------------------------------------------------------
# apply: persist via the manual write with llm: provenance + invariant
# ---------------------------------------------------------------------------


def test_apply_persists_derived_substrate_with_llm_provenance(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    # The gross is the seeded transaction input the substrate must reconstitute;
    # assert against it rather than a hand-summed literal.
    gross = Decimal("121.00")
    tx_id = _seed_unclassified(repository, amount=gross)
    suggestion = saturate_llm_classification(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        classifier=_FixedSaturatingClassifier(iva_category=IvaCategory.DOMESTIC_GENERAL_21),
        transaction_repository=repository,
    )

    result = apply_saturated_llm_classification(
        suggestion,
        bucket_id=_BUCKET,
        actor="operator-A",
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    persisted = result.transaction
    assert persisted.business_classification is BusinessClassification.BUSINESS
    assert persisted.classified_by == "llm:claude:test-model"
    assert persisted.iva_category is IvaCategory.DOMESTIC_GENERAL_21
    assert persisted.taxable_base == Decimal("100.00")
    assert persisted.iva_rate == Decimal("0.21")
    assert persisted.iva_amount == Decimal("21.00")
    # Reloaded from storage, the substrate still reconstitutes the gross.
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
        provider=LLMProvider.CLAUDE,
        classifier=_FixedSaturatingClassifier(iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY),
        transaction_repository=repository,
    )

    result = apply_saturated_llm_classification(
        suggestion,
        bucket_id=_BUCKET,
        actor="operator-A",
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
        provider=LLMProvider.CLAUDE,
        classifier=_FixedSaturatingClassifier(
            classification=BusinessClassification.MIXED,
            iva_category=IvaCategory.DOMESTIC_GENERAL_21,
            business_pct=None,
        ),
        transaction_repository=repository,
    )

    with pytest.raises(TransactionValidationError, match="requires a business percentage"):
        apply_saturated_llm_classification(
            suggestion,
            bucket_id=_BUCKET,
            actor="operator-A",
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
        provider=LLMProvider.CLAUDE,
        classifier=_FixedSaturatingClassifier(
            classification=BusinessClassification.MIXED,
            iva_category=IvaCategory.DOMESTIC_GENERAL_21,
            business_pct=Decimal("0.6"),
        ),
        transaction_repository=repository,
    )

    result = apply_saturated_llm_classification(
        suggestion,
        bucket_id=_BUCKET,
        actor="operator-A",
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    assert result.transaction.business_classification is BusinessClassification.MIXED
    assert result.transaction.business_pct == Decimal("0.6")
