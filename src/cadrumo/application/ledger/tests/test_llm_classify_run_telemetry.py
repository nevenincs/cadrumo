"""Real-behaviour tests for LLM run-timing telemetry on the subprocess classify path.

Exercises :func:`suggest_llm_classification` against a REAL subprocess CLI
(``python -c <script>``, no mocks) and asserts one
:class:`~cadrumo.adapters.outbound.llm.LLMRunRecord` is persisted per call, on
both the success and the hallucination-refusal (failure) branches -- the
run-timing capture that backs the local-only run-health diagnostic surface.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.outbound.llm import LLMRunTelemetryRecorder
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.llm import LLMClassifierError
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ..llm_classification import suggest_llm_classification
from ._subprocess_classifier_support import SubprocessLLMClassifier

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "43434343-4343-4343-8343-434343434343"

_SUCCESS_SCRIPT = """
import json
print(json.dumps({"classification": "BUSINESS", "confidence": 0.8, "reason": "office supplies"}))
"""

_FAILURE_SCRIPT = """
print("not valid json at all")
"""


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as p:
        yield p


def _transaction() -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="row-telemetry",
        booked_date=date(2025, 3, 1),
        value_date=date(2025, 3, 1),
        amount=Decimal("50.00"),
        currency="EUR",
        counterparty="Office SL",
        description="office supplies",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="manual",
        ),
        raw_fields={"Concepto": "office supplies"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "source_jurisdiction": "ES",
            "group_label": None,
        },
    )


def test_suggest_llm_classification_records_one_run_on_success(profile: TestRuntimeProfile) -> None:
    """A successful subprocess classify call records exactly one succeeded run."""
    txn = _transaction()
    repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
    repository.save(TransactionCatalogue.from_transactions((txn,)))
    classifier = SubprocessLLMClassifier(
        name="test-provider",
        command=(sys.executable, "-c", _SUCCESS_SCRIPT),
        model="test-model",
    )

    run_recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)
    assert run_recorder.load_records() == ()

    suggestion = suggest_llm_classification(
        bucket_id=_BUCKET_ID,
        transaction_id=txn.transaction_id,
        classifier=classifier,
        transaction_repository=repository,
        settings=profile.settings,
    )
    assert suggestion.provenance == "llm:test-provider:test-model"

    records = run_recorder.load_records()
    assert len(records) == 1
    record = records[0]
    assert record.succeeded is True
    assert record.error_kind == ""
    assert record.provider == "llm:test-provider:test-model"
    assert record.duration_ms >= 0


def test_suggest_llm_classification_records_one_run_on_failure(profile: TestRuntimeProfile) -> None:
    """A subprocess call whose output fails schema parsing records one failed run."""
    txn = _transaction()
    repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
    repository.save(TransactionCatalogue.from_transactions((txn,)))
    classifier = SubprocessLLMClassifier(
        name="test-provider",
        command=(sys.executable, "-c", _FAILURE_SCRIPT),
        model="test-model",
    )

    run_recorder = LLMRunTelemetryRecorder(root_dir=profile.settings.cadrumo_llm_run_telemetry_dir)

    with pytest.raises(LLMClassifierError):
        suggest_llm_classification(
            bucket_id=_BUCKET_ID,
            transaction_id=txn.transaction_id,
            classifier=classifier,
            transaction_repository=repository,
            settings=profile.settings,
        )

    records = run_recorder.load_records()
    assert len(records) == 1
    record = records[0]
    assert record.succeeded is False
    assert record.error_kind == "LLMClassifierError"
    assert record.provider == "llm:test-provider:test-model"
