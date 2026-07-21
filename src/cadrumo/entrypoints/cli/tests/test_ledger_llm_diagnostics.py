"""Real-behavior CLI tests for ``aeat app ledger llm-diagnostics``.

Exercises the diagnostics verb end to end against the real CLI, the real
:func:`~cadrumo.application.ledger.build_llm_diagnostics_report` aggregator, and
real encrypted SQLite persistence in an isolated storage root. No test doubles:
the two existing metric stores are seeded through their production writers —
:class:`~cadrumo.adapters.outbound.llm.UsageRecorder` for the usage/cost log and
:func:`~cadrumo.domain.transactions.set_classification` +
:class:`~cadrumo.domain.transactions.TransactionCatalogueRepository` for the
classification-confidence stamped on ledger transactions — and the verb reports
them back typed.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.outbound.llm import LLMProvider, LLMResponse, UsageRecorder
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....core.config import override_settings
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    set_classification,
)
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from .envelope_helpers import unwrap_cli_result as _json_result
from .envelope_helpers import unwrap_envelope_notices

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "00000000-0000-4000-8000-000000000000"


def _invoke(args: list[str]) -> Result:
    return invoke_cached_cli(args)


@pytest.fixture
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_BUCKET_ID),
    ):
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id=_BUCKET_ID))
        yield


def _seed_usage() -> None:
    """Write two real usage records (one cache hit) for provider ANTHROPIC."""
    recorder = UsageRecorder()
    first = LLMResponse(
        text="ok",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=40,
        cost_estimate_usd=Decimal("0.0012"),
        cache_hit=False,
        created_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
        request_id="req-1",
    )
    second = LLMResponse(
        text="ok",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        input_tokens=60,
        output_tokens=10,
        cost_estimate_usd=Decimal("0.0003"),
        cache_hit=True,
        created_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
        request_id="req-2",
    )
    for response in (first, second):
        recorder.record(recorder.build_record(response, prompt_id="translation_v1", caller="test-suite"))


def _raw(provider_id: str, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=amount,
        currency="EUR",
        counterparty="Supplier SL",
        description=f"row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def _seed_two_llm_classified() -> None:
    """Persist two LLM-classified transactions: one low, one high confidence."""
    high = Transaction.model_validate(
        {
            "raw": _raw("row-high", Decimal("100.00")),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": "ES",
            "group_label": None,
        },
    )
    low = Transaction.model_validate(
        {
            "raw": _raw("row-low", Decimal("25.50")),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": "ES",
            "group_label": None,
        },
    )
    catalogue = TransactionCatalogue.from_transactions([high, low])
    catalogue = set_classification(
        catalogue,
        high.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="llm:claude:test-model",
        confidence=Decimal("0.95"),
    )
    catalogue = set_classification(
        catalogue,
        low.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="llm:claude:test-model",
        confidence=Decimal("0.30"),
    )
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID).save(catalogue)


def test_llm_diagnostics_reports_seeded_usage_and_confidence(_isolated_backend: None) -> None:
    """The verb reports the seeded usage/cost and confidence metrics typed."""
    _seed_usage()
    _seed_two_llm_classified()

    result = _invoke(["--format", "json", "app", "ledger", "llm-diagnostics"])
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["has_data"] is True
    assert payload["low_confidence_threshold"] == "0.5"

    # Usage/cost section: two ANTHROPIC calls, one a cache hit.
    usage = {row["provider"]: row for row in payload["usage_providers"]}
    assert set(usage) == {LLMProvider.ANTHROPIC.value}
    anthropic = usage[LLMProvider.ANTHROPIC.value]
    assert anthropic["calls"] == 2
    assert anthropic["cache_hits"] == 1
    assert anthropic["input_tokens"] == 160
    assert anthropic["output_tokens"] == 50
    assert anthropic["total_tokens"] == 210
    assert Decimal(anthropic["cost_estimate_usd"]) == Decimal("0.0015")
    assert payload["total_calls"] == 2
    assert payload["total_input_tokens"] == 160
    assert Decimal(payload["total_cost_estimate_usd"]) == Decimal("0.0015")

    # Confidence section: two claude classifications, one below the 0.5 floor.
    confidence = {row["provider"]: row for row in payload["confidence_providers"]}
    assert set(confidence) == {"claude"}
    claude = confidence["claude"]
    assert claude["classified_count"] == 2
    assert claude["low_confidence_count"] == 1
    assert claude["high_confidence_count"] == 1
    assert claude["medium_confidence_count"] == 0
    assert Decimal(claude["min_confidence"]) == Decimal("0.30")
    assert Decimal(claude["max_confidence"]) == Decimal("0.95")
    assert payload["total_classified"] == 2
    assert payload["total_low_confidence"] == 1


def test_llm_diagnostics_custom_threshold_shifts_low_count(_isolated_backend: None) -> None:
    """A higher threshold reclassifies the 0.95 decision above/within the floor."""
    _seed_two_llm_classified()

    result = _invoke(
        ["--format", "json", "app", "ledger", "llm-diagnostics", "--low-confidence-below", "0.99"],
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    claude = {row["provider"]: row for row in payload["confidence_providers"]}["claude"]
    # Both 0.30 and 0.95 now fall below 0.99.
    assert claude["low_confidence_count"] == 2
    assert payload["total_low_confidence"] == 2
    assert payload["low_confidence_threshold"] == "0.99"


def test_llm_diagnostics_empty_is_instructive(_isolated_backend: None) -> None:
    """With no LLM activity the verb reports empty and surfaces a guidance notice."""
    result = _invoke(["--format", "json", "app", "ledger", "llm-diagnostics"])
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["has_data"] is False
    assert payload["usage_providers"] == []
    assert payload["confidence_providers"] == []
    assert payload["total_calls"] == 0
    assert payload["total_classified"] == 0

    codes = {notice["code"] for notice in unwrap_envelope_notices(result.output)}
    assert "ledger.llm_diagnostics.no_data" in codes


def test_llm_diagnostics_rejects_out_of_range_threshold(_isolated_backend: None) -> None:
    """An out-of-range threshold is refused instructively with a non-zero exit."""
    result = _invoke(
        ["--format", "json", "app", "ledger", "llm-diagnostics", "--low-confidence-below", "1.5"],
    )
    assert result.exit_code != 0
    assert "0..1" in result.output
