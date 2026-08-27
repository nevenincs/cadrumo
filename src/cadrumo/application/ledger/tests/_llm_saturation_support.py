"""Shared support for saturating LLM classification tests."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....domain.categories import SpendingCategory
from ....domain.iva import IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    prompt_spec_with_saturation_fields,
)
from ....tests.secure_sql import isolated_runtime_profile
from ._subprocess_classifier_support import SubprocessLLMClassifier

_NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
_BUCKET = "17171717-1717-4717-8717-171717171717"


def _saturating_subprocess_classifier(
    *,
    classification: BusinessClassification = BusinessClassification.BUSINESS,
    iva_category: IvaCategory | None = IvaCategory.DOMESTIC_GENERAL,
    business_pct: Decimal | None = None,
    model: str = "test-model",
) -> SubprocessLLMClassifier:
    payload = {
        "classification": classification.value,
        "confidence": "0.9",
        "reason": "grounded saturation fixture",
    }
    if iva_category is not None:
        payload["iva_category"] = iva_category.value
    if business_pct is not None:
        payload["business_pct"] = format(business_pct, "f")
    response_json = json.dumps(payload, sort_keys=True)
    script = f"""
import sys

sys.stdin.read()
print({response_json!r})
"""
    return SubprocessLLMClassifier(
        name="claude",
        command=(sys.executable, "-c", script),
        model=model,
        spec=prompt_spec_with_saturation_fields(year=2025),
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
        provider_transaction_id="row-saturate-1",
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
        provider_transaction_id="row-derive-1",
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
