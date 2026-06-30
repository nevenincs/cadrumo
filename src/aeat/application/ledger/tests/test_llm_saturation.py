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
from ....domain.categories import SpendingCategory
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
    OperatorIvaDerivationResult,
    apply_saturated_llm_classification,
    derive_operator_iva_substrate,
    saturate_llm_classification,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
_BUCKET = "17171717-1717-4717-8717-171717171717"


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

    def classify(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMClassificationResponse:
        self.last_evidence_text = evidence_text
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


def _seed_business(
    repository: TransactionCatalogueRepository,
    *,
    amount: Decimal = Decimal("121.00"),
    category: SpendingCategory = SpendingCategory.ARRENDAMIENTO_LOCAL,
) -> str:
    """Persist one ACTIVE BUSINESS transaction (no IVA substrate yet) and return its id."""
    raw = RawTransaction(
        transaction_id="row-derive-1",
        booked_date=date(2026, 5, 1),
        value_date=date(2026, 5, 1),
        amount=amount,
        currency="EUR",
        counterparty="Arrendador SL",
        description="office rent",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=_NOW,
            provider_name="csv",
        ),
        raw_fields={"Concepto": "office rent"},
    )
    tx = Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": category.value,
        },
    )
    repository.save(TransactionCatalogue.from_transactions([tx]))
    return tx.transaction_id


# ---------------------------------------------------------------------------
# operator-initiated derivation: operator selects category, system derives
# ---------------------------------------------------------------------------


def test_operator_derive_persists_substrate_with_derived_provenance(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    # The gross is the seeded BUSINESS input the derived substrate must reconstitute;
    # assert base + iva against this seeded input, not a hand-summed literal.
    gross = Decimal("121.00")
    tx_id = _seed_business(repository, amount=gross)

    derivation = derive_operator_iva_substrate(
        bucket_id=_BUCKET,
        transaction_id=tx_id,
        iva_category=IvaCategory.DOMESTIC_GENERAL_21,
        actor="operator-A",
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

    # Reloaded from storage: substrate persisted with derived: provenance, the
    # business classification + category are untouched, and base + iva reconstitute
    # the gross to the cent.
    reloaded = repository.load().get(tx_id)
    assert reloaded is not None
    assert reloaded.classified_by == "derived:iva-category"
    assert reloaded.business_classification is BusinessClassification.BUSINESS
    assert reloaded.category_id == SpendingCategory.ARRENDAMIENTO_LOCAL.value
    assert reloaded.iva_category is IvaCategory.DOMESTIC_GENERAL_21
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
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    assert derivation.derivable is False
    assert derivation.result is None
    assert derivation.iva_rate is None
    assert derivation.taxable_base is None
    assert derivation.note  # operator-facing explanation present

    # A non-derivable category writes nothing: the row keeps no IVA substrate and
    # is not stamped with derived: provenance.
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
    # An unclassified row (NOT_YET_PROCESSED) is neither BUSINESS nor MIXED.
    tx_id = _seed_unclassified(repository)

    with pytest.raises(TransactionValidationError, match="business transaction"):
        derive_operator_iva_substrate(
            bucket_id=_BUCKET,
            transaction_id=tx_id,
            iva_category=IvaCategory.DOMESTIC_GENERAL_21,
            actor="operator-A",
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
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    assert derivation.derivable is True
    assert derivation.iva_rate == Decimal("0")
    assert derivation.taxable_base == gross
    assert derivation.iva_amount == Decimal("0.00")


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
