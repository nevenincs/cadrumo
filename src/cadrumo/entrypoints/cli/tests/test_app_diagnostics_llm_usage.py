"""Real-behavior CLI tests for ``aeat app diagnostics llm-usage``.

Exercises the verb end to end against the real CLI, the real
:func:`~cadrumo.application.diagnostics_run_health.build_llm_usage_report`
aggregator, and real encrypted SQLite persistence in an isolated storage
root. No test doubles: LLM run telemetry is seeded through its production
writer (:class:`~cadrumo.adapters.outbound.llm.LLMRunTelemetryRecorder`) and the
verb reports the run-count/duration/success-rate summary back typed, grouped
by provider and, within each provider, by model.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from click.testing import Result

from ....adapters.outbound.llm._run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.cli_envelope import unwrap_cli_result as _json_result
from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "33333333-4444-4555-8666-777777777777"

_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id=_BUCKET_ID,
    autouse=False,
    settings_overrides={"cadrumo_output_language": "en"},
)


def _invoke(args: list[str]) -> Result:
    return invoke_cached_cli(args)


def _seed_runs() -> None:
    """Write six real run-timing records across two providers and three models.

    ``llm:claude:test-model-a`` gets two succeeded runs (100ms, 300ms);
    ``llm:claude:test-model-b`` gets one succeeded (200ms) and one failed
    (400ms) run; ``llm:codex:test-model-a`` gets two succeeded runs (50ms,
    150ms). This exercises both the provider-level fold and the nested
    per-model fold within a provider that uses more than one model.
    """
    recorder = LLMRunTelemetryRecorder()
    seeds = (
        ("run-1", "llm:claude:test-model", "model-a", 100, True, ""),
        ("run-2", "llm:claude:test-model", "model-a", 300, True, ""),
        ("run-3", "llm:claude:test-model", "model-b", 200, True, ""),
        ("run-4", "llm:claude:test-model", "model-b", 400, False, "LLMClassifierError"),
        ("run-5", "llm:codex:test-model", "model-a", 50, True, ""),
        ("run-6", "llm:codex:test-model", "model-a", 150, True, ""),
    )
    for index, (run_id, provenance, model, duration_ms, succeeded, error_kind) in enumerate(seeds, start=1):
        recorder.record(
            LLMRunRecord(
                run_id=run_id,
                provider=provenance,
                caller="cadrumo.application.ledger.llm_classification",
                model=model,
                duration_ms=duration_ms,
                succeeded=succeeded,
                error_kind=error_kind,
                started_at=datetime(2026, 6, index, 9, 0, tzinfo=UTC),
            ),
        )


def test_llm_usage_aggregates_by_provider_and_model(_isolated_backend: None) -> None:
    """The verb groups real recorded runs by provider, then by model within each provider."""
    _seed_runs()

    result = _invoke(["--format", "json", "app", "diagnostics", "llm-usage"])
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["has_run_data"] is True
    assert payload["total_runs"] == 6
    assert payload["total_succeeded"] == 5
    assert payload["total_failed"] == 1

    providers = {row["provider"]: row for row in payload["by_provider"]}
    assert set(providers) == {"llm:claude:test-model", "llm:codex:test-model"}

    claude = providers["llm:claude:test-model"]
    assert claude["runs"] == 4
    assert claude["succeeded"] == 3
    assert claude["failed"] == 1
    assert claude["min_duration_ms"] == 100
    assert claude["max_duration_ms"] == 400
    assert claude["total_duration_ms"] == 1000

    claude_models = {row["model"]: row for row in claude["models"]}
    assert set(claude_models) == {"model-a", "model-b"}
    assert claude_models["model-a"]["runs"] == 2
    assert claude_models["model-a"]["succeeded"] == 2
    assert claude_models["model-a"]["failed"] == 0
    assert claude_models["model-a"]["total_duration_ms"] == 400
    assert claude_models["model-a"]["success_rate"] == "1.0000"

    claude_model_b = claude_models["model-b"]
    assert claude_model_b["runs"] == 2
    assert claude_model_b["succeeded"] == 1
    assert claude_model_b["failed"] == 1
    assert claude_model_b["success_rate"] == "0.5000"

    codex = providers["llm:codex:test-model"]
    assert codex["runs"] == 2
    assert codex["succeeded"] == 2
    assert codex["failed"] == 0
    assert codex["success_rate"] == "1.0000"
    assert len(codex["models"]) == 1
    assert codex["models"][0]["model"] == "model-a"
    assert codex["models"][0]["runs"] == 2

    assert payload["overall_success_rate"] == "0.8333"


def test_llm_usage_empty_is_instructive(_isolated_backend: None) -> None:
    """With no LLM run telemetry the verb reports empty and surfaces a guidance notice."""
    result = _invoke(["--format", "json", "app", "diagnostics", "llm-usage"])
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    payload = envelope["result"]

    assert payload["has_run_data"] is False
    assert payload["by_provider"] == []
    assert payload["total_runs"] == 0
    assert payload["total_succeeded"] == 0
    assert payload["total_failed"] == 0
    assert payload["overall_success_rate"] == "0"

    codes = {notice["code"] for notice in envelope.get("notices", [])}
    assert "diagnostics.llm_usage.no_run_data" in codes


def test_llm_usage_provider_filter_scopes_the_summary(_isolated_backend: None) -> None:
    """``--provider`` restricts the summary to one provider label."""
    _seed_runs()

    result = _invoke(
        ["--format", "json", "app", "diagnostics", "llm-usage", "--provider", "llm:codex:test-model"],
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert len(payload["by_provider"]) == 1
    assert payload["by_provider"][0]["provider"] == "llm:codex:test-model"
    assert payload["total_runs"] == 2
    assert payload["total_succeeded"] == 2
    assert payload["total_failed"] == 0


def test_llm_usage_since_until_scopes_by_date(_isolated_backend: None) -> None:
    """``--since``/``--until`` narrow the usage summary by date."""
    _seed_runs()

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "diagnostics",
            "llm-usage",
            "--since",
            "2026-06-01",
            "--until",
            "2026-06-01",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["total_runs"] == 1
    assert len(payload["by_provider"]) == 1
    assert payload["by_provider"][0]["provider"] == "llm:claude:test-model"
    assert payload["by_provider"][0]["runs"] == 1
    assert payload["by_provider"][0]["models"][0]["model"] == "model-a"


def test_llm_usage_rejects_malformed_date(_isolated_backend: None) -> None:
    """A malformed ``--since`` value is refused instructively with a non-zero exit."""
    result = _invoke(["--format", "json", "app", "diagnostics", "llm-usage", "--since", "01/04/2026"])
    assert result.exit_code != 0
    assert "ISO date" in result.output


def test_llm_usage_human_text_reports_provider_and_model_lines(_isolated_backend: None) -> None:
    """The human-readable text output lists per-provider and nested per-model rows."""
    _seed_runs()

    result = _invoke(["app", "diagnostics", "llm-usage"])
    assert result.exit_code == 0, result.output
    assert "llm:claude:test-model" in result.output
    assert "llm:codex:test-model" in result.output
    assert "model-a" in result.output
    assert "model-b" in result.output
