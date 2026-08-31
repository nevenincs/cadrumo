"""Real-behavior CLI tests for ``aeat app diagnostics runs``.

Exercises the listing verb end to end against the real CLI, the real
:func:`~cadrumo.application.diagnostics_run_health.list_recent_runs` projection,
and real encrypted SQLite persistence in an isolated storage root. No test
doubles: LLM run telemetry is seeded through its production writer
(:class:`~cadrumo.adapters.outbound.llm.LLMRunTelemetryRecorder`), the exact same
recorder ``run-health`` reads, and the verb reports it back typed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from click.testing import Result

from ....adapters.outbound.llm._run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder
from ....tests.cli_envelope import unwrap_cli_result as _json_result
from ....tests.cli_runner import invoke_cached_cli
from ._strict_cli_fixture_support import diagnostics_isolated_backend

__all__ = ["diagnostics_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "22222222-3333-4444-8555-666666666666"


def _invoke(args: list[str]) -> Result:
    return invoke_cached_cli(args)


def _seed_runs() -> None:
    """Write three real run-timing records: two claude (one failed), one codex."""
    recorder = LLMRunTelemetryRecorder()
    recorder.record(
        LLMRunRecord(
            run_id="run-1",
            caller="cadrumo.application.ledger.llm_classification",
            provider="llm:claude:test-model",
            model="test-model",
            duration_ms=1200,
            succeeded=True,
            started_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
        ),
    )
    recorder.record(
        LLMRunRecord(
            run_id="run-2",
            caller="cadrumo.application.ledger.llm_classification",
            provider="llm:claude:test-model",
            model="test-model",
            duration_ms=45000,
            succeeded=False,
            error_kind="LLMClassifierError",
            started_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
        ),
    )
    recorder.record(
        LLMRunRecord(
            run_id="run-3",
            caller="cadrumo.application.ledger.llm_classification",
            provider="llm:codex:test-model",
            model="test-model",
            duration_ms=800,
            succeeded=True,
            started_at=datetime(2026, 4, 3, 9, 0, tzinfo=UTC),
        ),
    )


def test_runs_lists_seeded_records_most_recent_first(_isolated_backend: None) -> None:
    """The verb lists the seeded run telemetry typed, most-recent-first."""
    _seed_runs()

    result = _invoke(["--format", "json", "app", "diagnostics", "runs"])
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["has_run_data"] is True
    assert payload["total_runs"] == 3
    assert [row["run_id"] for row in payload["runs"]] == ["run-3", "run-2", "run-1"]
    assert payload["runs"][1]["succeeded"] is False
    assert payload["runs"][1]["error_kind"] == "LLMClassifierError"


def test_runs_empty_is_instructive(_isolated_backend: None) -> None:
    """With no LLM run telemetry the verb reports empty and surfaces a guidance notice."""
    result = _invoke(["--format", "json", "app", "diagnostics", "runs"])
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    payload = envelope["result"]

    assert payload["has_run_data"] is False
    assert payload["runs"] == []
    assert payload["total_runs"] == 0

    codes = {notice["code"] for notice in envelope.get("notices", [])}
    assert "diagnostics.runs.no_run_data" in codes


def test_runs_provider_filter_scopes_the_listing(_isolated_backend: None) -> None:
    """``--provider`` restricts the listing to one provider label."""
    _seed_runs()

    result = _invoke(
        ["--format", "json", "app", "diagnostics", "runs", "--provider", "llm:codex:test-model"],
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert len(payload["runs"]) == 1
    assert payload["runs"][0]["provider"] == "llm:codex:test-model"
    assert payload["total_runs"] == 1


def test_runs_since_until_scopes_by_date(_isolated_backend: None) -> None:
    """``--since``/``--until`` narrow the listing by date."""
    _seed_runs()

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "diagnostics",
            "runs",
            "--since",
            "2026-04-01",
            "--until",
            "2026-04-01",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["total_runs"] == 1
    assert payload["runs"][0]["run_id"] == "run-1"


def test_runs_limit_caps_the_most_recent_rows(_isolated_backend: None) -> None:
    """``--limit`` caps the listing to the N most-recent rows."""
    _seed_runs()

    result = _invoke(["--format", "json", "app", "diagnostics", "runs", "--limit", "2"])
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert [row["run_id"] for row in payload["runs"]] == ["run-3", "run-2"]
    assert payload["total_runs"] == 2


def test_runs_rejects_malformed_date(_isolated_backend: None) -> None:
    """A malformed ``--since`` value is refused instructively with a non-zero exit."""
    result = _invoke(["--format", "json", "app", "diagnostics", "runs", "--since", "01/04/2026"])
    assert result.exit_code != 0
    assert "ISO date" in result.output


def test_runs_rejects_nonpositive_limit(_isolated_backend: None) -> None:
    """A ``--limit`` below 1 is refused by the option's own ``min`` bound."""
    result = _invoke(["--format", "json", "app", "diagnostics", "runs", "--limit", "0"])
    assert result.exit_code != 0
