"""Real encrypted-profile worker tests for ``app ledger llm-diagnostics``."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import typer
from click.testing import Result
from pydantic import ValidationError

from ....adapters.outbound.llm.models import LLMResponse
from ....adapters.persistence.llm.usage import UsageRecorder
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....application.workflow.profile_bucket_scan import read_profile_bucket
from ....core.config import override_settings
from ....core.config_support import LLMProvider
from ....core.i18n.render import clear_output_language_cache, tr
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.transactions.service import set_classification
from ....tests.cli_envelope import require_error_document, unwrap_envelope_notices
from ....tests.cli_envelope import unwrap_cli_result as _json_result
from .._ledger_rule_payloads import (
    LedgerLlmDiagnosticsResult,
    LlmConfidenceProviderPayload,
    LlmUsageCostProviderPayload,
)
from .diagnostics_native_support import diagnostics_native_profile, invoke_diagnostics_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture

# Seeded rows and stored records decode against registry facts, so the test
# body holds the same authority lease a CLI invocation holds.
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

__all__ = ["diagnostics_native_profile"]


def _invoke(args: list[str]) -> Result:
    return invoke_diagnostics_cli(args)


def _registered_bucket_id(profile: NativeCliProfileFixture) -> str:
    """Resolve the fixture's published label through the public profile catalogue."""
    if profile.label is None:
        raise AssertionError("native diagnostics profile was not registered")
    pointer = read_profile_bucket(profile.label)
    if pointer is None:
        raise AssertionError("registered diagnostics profile is missing from the public catalogue")
    return str(pointer.bucket_id)


def seed_ledger_llm_usage_records() -> None:
    """Write priced, cache-hit, and unpriced records through the encrypted writer."""
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
    unpriced = LLMResponse(
        text="ok",
        provider=LLMProvider.OPENAI,
        model="gpt-4.1-mini",
        input_tokens=20,
        output_tokens=5,
        cost_estimate_usd=None,
        cache_hit=False,
        created_at=datetime(2026, 4, 3, 9, 0, tzinfo=UTC),
        request_id="req-3",
    )
    for response in (first, second, unpriced):
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


def seed_ledger_llm_classified_transactions(bucket_id: str) -> None:
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
    TransactionCatalogueRepository(bucket_id=bucket_id).save(catalogue)


def test_llm_diagnostics_reports_seeded_usage_and_confidence(
    diagnostics_native_profile: NativeCliProfileFixture,
) -> None:
    """The registered worker reports both encrypted stores, including unpriced cost."""
    seed_ledger_llm_usage_records()
    seed_ledger_llm_classified_transactions(_registered_bucket_id(diagnostics_native_profile))

    result = _invoke(["--format", "json", "app", "ledger", "llm-diagnostics"])
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["has_data"] is True
    assert payload["low_confidence_threshold"] == "0.5"

    # Usage/cost section: two ANTHROPIC calls, one a cache hit.
    usage = {row["provider"]: row for row in payload["usage_providers"]}
    assert set(usage) == {LLMProvider.ANTHROPIC.value, LLMProvider.OPENAI.value}
    anthropic = usage[LLMProvider.ANTHROPIC.value]
    assert anthropic["calls"] == 2
    assert anthropic["cache_hits"] == 1
    assert anthropic["input_tokens"] == 160
    assert anthropic["output_tokens"] == 50
    assert anthropic["total_tokens"] == 210
    assert Decimal(anthropic["cost_estimate_usd"]) == Decimal("0.0015")
    assert anthropic["unpriced_calls"] == 0
    openai = usage[LLMProvider.OPENAI.value]
    assert openai["calls"] == 1
    assert openai["cost_estimate_usd"] is None
    assert openai["unpriced_calls"] == 1
    assert payload["total_calls"] == 3
    assert payload["total_input_tokens"] == 180
    assert payload["total_output_tokens"] == 55
    assert payload["total_unpriced_calls"] == 1
    assert payload["total_cost_estimate_usd"] is None

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


def test_llm_diagnostics_usage_window_and_threshold_keep_confidence_independent(
    diagnostics_native_profile: NativeCliProfileFixture,
) -> None:
    """Date bounds filter usage while the caller's threshold folds all classifications."""
    seed_ledger_llm_usage_records()
    seed_ledger_llm_classified_transactions(_registered_bucket_id(diagnostics_native_profile))

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "llm-diagnostics",
            "--since",
            "2026-04-02",
            "--until",
            "2026-04-02",
            "--low-confidence-below",
            "0.99",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    claude = {row["provider"]: row for row in payload["confidence_providers"]}["claude"]
    assert payload["since"] == "2026-04-02"
    assert payload["until"] == "2026-04-02"
    assert payload["total_calls"] == 1
    only_usage = payload["usage_providers"]
    assert len(only_usage) == 1
    assert only_usage[0]["provider"] == LLMProvider.ANTHROPIC.value
    assert only_usage[0]["cache_hits"] == 1
    # Both 0.30 and 0.95 fall below 0.99 despite the usage date window.
    assert claude["low_confidence_count"] == 2
    assert payload["total_low_confidence"] == 2
    assert payload["low_confidence_threshold"] == "0.99"


def test_llm_diagnostics_reversed_usage_window_keeps_confidence(
    diagnostics_native_profile: NativeCliProfileFixture,
) -> None:
    """Reversed dates preserve the empty usage window and unbounded confidence scan."""
    seed_ledger_llm_usage_records()
    seed_ledger_llm_classified_transactions(_registered_bucket_id(diagnostics_native_profile))
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "llm-diagnostics",
            "--since",
            "2026-04-03",
            "--until",
            "2026-04-01",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)
    assert payload["since"] == "2026-04-03"
    assert payload["until"] == "2026-04-01"
    assert payload["usage_providers"] == []
    assert payload["total_calls"] == 0
    assert payload["total_cost_estimate_usd"] == "0"
    assert payload["total_classified"] == 2
    assert payload["total_low_confidence"] == 1


def test_llm_diagnostics_empty_is_instructive(diagnostics_native_profile: NativeCliProfileFixture) -> None:
    """JSON notices and human text explain that neither metric store has data."""
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
    (notice,) = [
        notice
        for notice in unwrap_envelope_notices(result.output)
        if notice["code"] == "ledger.llm_diagnostics.no_data"
    ]
    assert notice.get("action") is None
    assert notice["context"] == {}
    text_result = _invoke(["app", "ledger", "llm-diagnostics"])
    assert text_result.exit_code == 0, text_result.output
    assert tr("cli.ledger.llm_diagnostics.no_data_message", locale="en") in text_result.output


def test_llm_diagnostics_rejects_bad_date_and_out_of_range_threshold(
    diagnostics_native_profile: NativeCliProfileFixture,
) -> None:
    """The command keeps its localized date refusal and inclusive unit interval."""
    bad_date = _invoke(["--format", "json", "app", "ledger", "llm-diagnostics", "--since", "not-a-date"])
    assert bad_date.exit_code != 0
    assert (
        tr(
            "cli.ledger.llm_diagnostics.bad_date",
            option="--since",
            value="not-a-date",
            locale="en",
        )
        in require_error_document(bad_date.output)["error"]["message"]
    )

    result = _invoke(
        ["--format", "json", "app", "ledger", "llm-diagnostics", "--low-confidence-below", "1.5"],
    )
    assert result.exit_code != 0
    assert "0..1" in result.output


@pytest.mark.parametrize("locale", ("ca", "en", "es", "hu"))
def test_llm_diagnostics_date_parser_uses_catalogue_leaf(locale: str) -> None:
    """The command's existing date parser retains the localized message leaf."""
    from .._ledger_read_cli import _parse_iso_date

    with override_settings(cadrumo_output_language=locale):
        clear_output_language_cache()
        expected = tr(
            "cli.ledger.llm_diagnostics.bad_date",
            option="--since",
            value="not-a-date",
        )
        with pytest.raises(typer.BadParameter) as error:
            _parse_iso_date("not-a-date", "--since")
    clear_output_language_cache()

    assert error.value.message == expected


def test_llm_diagnostics_payloads_mirror_their_canonical_bounds() -> None:
    """The transport must refuse what the canonical diagnostics models refuse.

    ``LlmUsageCostProviderMetrics`` and ``LlmConfidenceProviderMetrics`` require a
    non-empty provider and non-negative counters, and ``LlmDiagnosticsReport``
    requires non-negative totals plus a real decimal threshold. The CLI rows
    redeclared all of them as bare strings and ints, so an empty provider, a
    negative counter, and non-decimal text could cross the
    ``ledger.llm_diagnostics`` envelope.

    The decimal fields carry the canonical grammar but NO range: the canonical
    models declare ``cost_estimate_usd`` and the confidence figures as plain
    ``Decimal`` / ``Decimal | None``, so bounding them here would make the
    transport stricter than the contract it mirrors.
    """
    usage_base = {
        "provider": "claude",
        "calls": 1,
        "cache_hits": 0,
        "input_tokens": 5,
        "output_tokens": 5,
        "total_tokens": 10,
        "cost_estimate_usd": "0.01",
    }
    confidence_base = {
        "provider": "claude",
        "classified_count": 1,
        "low_confidence_count": 0,
        "high_confidence_count": 1,
        "medium_confidence_count": 0,
        "mean_confidence": "0.9",
    }

    for label, model, base, override in (
        ("empty usage provider", LlmUsageCostProviderPayload, usage_base, {"provider": ""}),
        ("negative calls", LlmUsageCostProviderPayload, usage_base, {"calls": -1}),
        ("negative cache hits", LlmUsageCostProviderPayload, usage_base, {"cache_hits": -1}),
        ("negative total tokens", LlmUsageCostProviderPayload, usage_base, {"total_tokens": -1}),
        ("non-decimal cost", LlmUsageCostProviderPayload, usage_base, {"cost_estimate_usd": "bogus"}),
        ("empty confidence provider", LlmConfidenceProviderPayload, confidence_base, {"provider": ""}),
        ("negative classified", LlmConfidenceProviderPayload, confidence_base, {"classified_count": -1}),
        ("negative low confidence", LlmConfidenceProviderPayload, confidence_base, {"low_confidence_count": -1}),
        ("non-decimal mean", LlmConfidenceProviderPayload, confidence_base, {"mean_confidence": "bogus"}),
    ):
        model.model_validate(base)  # positive control: the base must be accepted
        try:
            model.model_validate(base | override)
        except ValidationError:
            continue
        pytest.fail(f"{label} was accepted by the transport row")

    # Decimal magnitudes stay unbounded, matching the canonical models.
    LlmUsageCostProviderPayload.model_validate(usage_base | {"cost_estimate_usd": "-1.00"})
    LlmConfidenceProviderPayload.model_validate(confidence_base | {"mean_confidence": "-1"})


def test_llm_diagnostics_result_refuses_negative_totals() -> None:
    """``LlmDiagnosticsReport`` bounds every total at zero; the envelope must too."""
    base = {
        "low_confidence_threshold": "0.5",
        "usage_providers": [],
        "total_calls": 0,
        "total_cache_hits": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost_estimate_usd": "0",
        "confidence_providers": [],
        "total_classified": 0,
        "total_low_confidence": 0,
        "has_data": False,
    }
    LedgerLlmDiagnosticsResult.model_validate(base)

    for label, override in (
        ("negative total calls", {"total_calls": -1}),
        ("negative total classified", {"total_classified": -1}),
        ("non-decimal threshold", {"low_confidence_threshold": "bogus"}),
    ):
        try:
            LedgerLlmDiagnosticsResult.model_validate(base | override)
        except ValidationError:
            continue
        pytest.fail(f"{label} was accepted by the diagnostics envelope")
