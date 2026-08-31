"""Real-behavior CLI tests for ``aeat app diagnostics latency`` and ``errors``.

Exercises both verbs end to end against the real CLI, the real
:func:`~cadrumo.application.diagnostics_run_health.build_latency_report` and
:func:`~cadrumo.application.diagnostics_run_health.build_error_breakdown`
aggregators, and real encrypted SQLite persistence in an isolated storage
root. No test doubles: LLM run telemetry is seeded through its production
writer (:class:`~cadrumo.adapters.outbound.llm.LLMRunTelemetryRecorder`) and both
verbs report it back typed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from click.testing import Result

from ....adapters.outbound.llm.run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder
from ....tests.cli_envelope import unwrap_cli_result as _json_result
from ....tests.cli_runner import invoke_cached_cli
from ._strict_cli_fixture_support import diagnostics_isolated_backend

__all__ = ["diagnostics_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "22222222-3333-4444-8555-666666666666"


def _invoke(args: list[str]) -> Result:
    return invoke_cached_cli(args)


def _seed_latency_runs() -> None:
    """Write ten real claude runs with known ascending durations 100..1000ms."""
    recorder = LLMRunTelemetryRecorder()
    for index, duration_ms in enumerate((100, 200, 300, 400, 500, 600, 700, 800, 900, 1000), start=1):
        recorder.record(
            LLMRunRecord(
                run_id=f"lat-{index}",
                caller="cadrumo.application.ledger.llm_classification",
                provider="llm:claude:test-model",
                model="test-model",
                duration_ms=duration_ms,
                succeeded=True,
                started_at=datetime(2026, 5, index, 9, 0, tzinfo=UTC),
            ),
        )


def _seed_error_runs() -> None:
    """Write four real failed runs across two providers and two error kinds."""
    recorder = LLMRunTelemetryRecorder()
    seeds = (
        ("llm:claude:test-model", "KindA"),
        ("llm:claude:test-model", "KindA"),
        ("llm:claude:test-model", "KindB"),
        ("llm:codex:test-model", "KindA"),
    )
    for index, (provenance, error_kind) in enumerate(seeds, start=1):
        recorder.record(
            LLMRunRecord(
                run_id=f"err-{index}",
                provider=provenance,
                caller="cadrumo.application.ledger.llm_classification",
                model="test-model",
                duration_ms=100,
                succeeded=False,
                error_kind=error_kind,
                started_at=datetime(2026, 5, index, 9, 0, tzinfo=UTC),
            ),
        )


def test_latency_reports_nearest_rank_percentiles(_isolated_backend: None) -> None:
    """The verb reports P50/P95/P99 computed by the documented nearest-rank method."""
    _seed_latency_runs()

    result = _invoke(["--format", "json", "app", "diagnostics", "latency"])
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["has_run_data"] is True
    overall = payload["overall"]
    assert overall["entries"] == 10
    assert overall["min_duration_ms"] == 100
    assert overall["max_duration_ms"] == 1000
    assert overall["p50_duration_ms"] == 500
    assert overall["p95_duration_ms"] == 1000
    assert overall["p99_duration_ms"] == 1000

    providers = {row["provider"]: row for row in payload["by_provider"]}
    assert set(providers) == {"llm:claude:test-model"}
    assert providers["llm:claude:test-model"]["percentiles"]["p50_duration_ms"] == 500


def test_latency_empty_is_instructive(_isolated_backend: None) -> None:
    """With no LLM run telemetry the verb reports empty and surfaces a guidance notice."""
    result = _invoke(["--format", "json", "app", "diagnostics", "latency"])
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    payload = envelope["result"]

    assert payload["has_run_data"] is False
    assert payload["overall"]["entries"] == 0
    assert payload["overall"]["p50_duration_ms"] is None
    assert payload["by_provider"] == []

    codes = {notice["code"] for notice in envelope.get("notices", [])}
    assert "diagnostics.latency.no_run_data" in codes


def test_latency_provider_filter_omits_by_provider_breakdown(_isolated_backend: None) -> None:
    """``--provider`` scopes ``overall`` and leaves ``by_provider`` empty."""
    _seed_latency_runs()

    result = _invoke(
        ["--format", "json", "app", "diagnostics", "latency", "--provider", "llm:claude:test-model"],
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["overall"]["entries"] == 10
    assert payload["by_provider"] == []


def test_latency_since_until_scopes_by_date(_isolated_backend: None) -> None:
    """``--since``/``--until`` narrow the percentile computation by date."""
    _seed_latency_runs()

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "diagnostics",
            "latency",
            "--since",
            "2026-05-01",
            "--until",
            "2026-05-01",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["overall"]["entries"] == 1
    assert payload["overall"]["p50_duration_ms"] == 100


def test_latency_rejects_malformed_date(_isolated_backend: None) -> None:
    """A malformed ``--since`` value is refused instructively with a non-zero exit."""
    result = _invoke(["--format", "json", "app", "diagnostics", "latency", "--since", "01/04/2026"])
    assert result.exit_code != 0
    assert "ISO date" in result.output


def test_errors_reports_breakdown_by_provider_and_kind(_isolated_backend: None) -> None:
    """The verb breaks failures down by provider and error kind, most-frequent-first."""
    _seed_error_runs()

    result = _invoke(["--format", "json", "app", "diagnostics", "errors"])
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["has_failures"] is True
    assert payload["total_runs"] == 4
    assert payload["total_failed"] == 4
    assert [(row["provider"], row["error_kind"], row["count"]) for row in payload["by_error_kind"]] == [
        ("llm:claude:test-model", "KindA", 2),
        ("llm:claude:test-model", "KindB", 1),
        ("llm:codex:test-model", "KindA", 1),
    ]


def test_errors_empty_is_instructive(_isolated_backend: None) -> None:
    """With no failed runs the verb reports empty and surfaces a guidance notice."""
    result = _invoke(["--format", "json", "app", "diagnostics", "errors"])
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    payload = envelope["result"]

    assert payload["has_failures"] is False
    assert payload["total_runs"] == 0
    assert payload["total_failed"] == 0
    assert payload["by_error_kind"] == []

    codes = {notice["code"] for notice in envelope.get("notices", [])}
    assert "diagnostics.errors.no_failures" in codes


def test_errors_succeeded_only_reports_no_failures(_isolated_backend: None) -> None:
    """A store with only succeeded runs reports zero failures against real recorded runs."""
    _seed_latency_runs()

    result = _invoke(["--format", "json", "app", "diagnostics", "errors"])
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["total_runs"] == 10
    assert payload["total_failed"] == 0
    assert payload["has_failures"] is False


def test_errors_provider_filter_scopes_the_breakdown(_isolated_backend: None) -> None:
    """``--provider`` restricts the breakdown to one provider's failures."""
    _seed_error_runs()

    result = _invoke(
        ["--format", "json", "app", "diagnostics", "errors", "--provider", "llm:codex:test-model"],
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["total_runs"] == 1
    assert payload["total_failed"] == 1
    assert len(payload["by_error_kind"]) == 1
    assert payload["by_error_kind"][0]["provider"] == "llm:codex:test-model"


def test_errors_rejects_malformed_date(_isolated_backend: None) -> None:
    """A malformed ``--until`` value is refused instructively with a non-zero exit."""
    result = _invoke(["--format", "json", "app", "diagnostics", "errors", "--until", "not-a-date"])
    assert result.exit_code != 0
    assert "ISO date" in result.output
