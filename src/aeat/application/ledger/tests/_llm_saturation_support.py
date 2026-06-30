"""Shared support for saturating LLM classification tests."""

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
)
from ....tests.secure_sql import isolated_runtime_profile

_NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
_BUCKET = "17171717-1717-4717-8717-171717171717"


class _FixedSaturatingClassifier:
    """Concrete in-process classifier returning a fixed saturated response."""

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
    tx = Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )
    repository.save(TransactionCatalogue.from_transactions([tx]))
    return tx.transaction_id


def _seed_business(
    repository: TransactionCatalogueRepository,
    *,
    amount: Decimal = Decimal("121.00"),
    category: SpendingCategory = SpendingCategory.ARRENDAMIENTO_LOCAL,
) -> str:
    """Persist one ACTIVE BUSINESS transaction with no IVA substrate and return its id."""
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
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "category_id": category.value,
        },
    )
    repository.save(TransactionCatalogue.from_transactions([tx]))
    return tx.transaction_id
