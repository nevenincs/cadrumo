"""Real-behaviour tests for the audit-trailed LLM reject terminal.

Rejecting an LLM suggestion is the fourth decision terminal (after approve =
apply and update = manual override). It records *what* the model proposed plus
the operator's reason as a ``ledger.transaction.llm_suggestion.rejected`` bucket
event and **mutates nothing** — the row stays unclassified. Exercised against
real SQLite persistence in an isolated profile, no mocks.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.buckets import BucketEvent, BucketEventHistoryRepository, BucketEventType
from ....domain.categories import SpendingCategory
from ....domain.iva import IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
    TransactionNotFoundError,
)
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    LLMClassificationSuggestion,
    LLMProvider,
    LLMSaturatedSuggestion,
    LLMSuggestionRejectionResult,
    reject_llm_suggestion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
_BUCKET = "bucket-reject"


@pytest.fixture
def repositories(
    tmp_path: Path,
) -> Iterator[tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository]]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        objects = profile.repository
        yield (
            TransactionCatalogueRepository(bucket_id=_BUCKET, objects=objects),
            BucketEventHistoryRepository(objects=objects),
            objects,
        )


def _seed_parent(repository: TransactionCatalogueRepository, *, amount: Decimal = Decimal("121.00")) -> str:
    raw = RawTransaction(
        transaction_id="row-reject",
        booked_date=date(2026, 5, 1),
        value_date=date(2026, 5, 1),
        amount=amount,
        currency="EUR",
        counterparty="Proveedor SL",
        description="supplier invoice",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=_NOW,
            provider_name="csv",
        ),
        raw_fields={"Concepto": "supplier invoice"},
    )
    tx = Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )
    repository.save(TransactionCatalogue.from_transactions([tx]))
    return tx.transaction_id


def _classification_suggestion(tx_id: str) -> LLMClassificationSuggestion:
    return LLMClassificationSuggestion(
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        provenance="llm:claude:test-model",
        classification=BusinessClassification.BUSINESS,
        category=SpendingCategory.MATERIAL_OFICINA,
        confidence=Decimal("0.9"),
        reason="looks like office supplies",
    )


def _rejection_events(events: BucketEventHistoryRepository) -> tuple[BucketEvent, ...]:
    return events.load().for_bucket(
        _BUCKET,
        event_types=(BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED,),
    )


def test_reject_records_event_and_does_not_mutate(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, _objects = repositories
    tx_id = _seed_parent(repository)

    result = reject_llm_suggestion(
        _classification_suggestion(tx_id),
        bucket_id=_BUCKET,
        reason="wrong category, this is personal",
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    assert isinstance(result, LLMSuggestionRejectionResult)
    assert result.suggestion_kind == "classification"
    assert result.provenance == "llm:claude:test-model"

    # The transaction is UNCHANGED: still unclassified, still active.
    txn = repository.load().get(tx_id)
    assert txn is not None
    assert txn.business_classification is BusinessClassification.NOT_YET_PROCESSED
    assert txn.lifecycle_state is TransactionLifecycleState.ACTIVE

    # The rejection rides the bucket-event history with the captured proposal + reason.
    recorded = _rejection_events(events)
    assert len(recorded) == 1
    payload = recorded[0].payload
    assert payload["suggestion_kind"] == "classification"
    assert payload["classification"] == BusinessClassification.BUSINESS.value
    assert payload["category"] == SpendingCategory.MATERIAL_OFICINA.value
    assert payload["operator_reason"] == "wrong category, this is personal"
    assert payload["mutation_kind"] == "llm_suggestion_rejected"


def test_reject_saturated_suggestion_captures_iva_category(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, _objects = repositories
    tx_id = _seed_parent(repository)
    saturated = LLMSaturatedSuggestion(
        transaction_id=tx_id,
        provider=LLMProvider.CLAUDE,
        provenance="llm:claude:test-model",
        classification=BusinessClassification.BUSINESS,
        category=SpendingCategory.MATERIAL_OFICINA,
        confidence=Decimal("0.8"),
        reason="domestic purchase",
        iva_category=IvaCategory.DOMESTIC_GENERAL_21,
    )

    reject_llm_suggestion(
        saturated,
        bucket_id=_BUCKET,
        reason="rate looks wrong",
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    payload = _rejection_events(events)[0].payload
    assert payload["iva_category"] == IvaCategory.DOMESTIC_GENERAL_21.value


def test_reject_unknown_transaction_raises(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, SecureObjectRepository],
) -> None:
    repository, events, _objects = repositories
    with pytest.raises(TransactionNotFoundError):
        reject_llm_suggestion(
            _classification_suggestion("tx_does_not_exist"),
            bucket_id=_BUCKET,
            transaction_repository=repository,
            bucket_event_repository=events,
        )
