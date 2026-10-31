"""Real-behavior CLI tests for ``aeat app diagnostics runs``.

Exercises the listing verb end to end against the real CLI, the real
:func:`~cadrumo.application.diagnostics_run_health.list_recent_runs` projection,
and real encrypted SQLite persistence in an isolated storage root. No test
doubles: LLM run record is seeded through its production writer
(:class:`~cadrumo.adapters.outbound.llm.LLMRunRecorder`), the exact same
recorder ``run-health`` reads, and the verb reports it back typed.
"""

from __future__ import annotations

import json

import pytest

from cadrumo.tests.cli_envelope import unwrap_cli_result as _json_result

from ...native_commands.diagnostics_native_support import diagnostics_native_profile
from ...native_commands.runtime_profile_cli_fixture import NativeCliProfileFixture
from ._diagnostics_cli_support import invoke_diagnostics, seed_claude_and_codex_runs

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.usefixtures("authority_operation"),
]

__all__ = ["diagnostics_native_profile"]

_BUCKET_ID = "22222222-3333-4444-8555-666666666666"


def test_runs_lists_seeded_records_most_recent_first(diagnostics_native_profile: NativeCliProfileFixture) -> None:
    """The verb lists the seeded run record typed, most-recent-first."""
    seed_claude_and_codex_runs()

    result = invoke_diagnostics(["--format", "json", "app", "diagnostics", "runs"], diagnostics_native_profile)
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["has_run_data"] is True
    assert payload["total_runs"] == 3
    assert [row["run_id"] for row in payload["runs"]] == ["run-3", "run-2", "run-1"]
    assert payload["runs"][1]["succeeded"] is False
    assert payload["runs"][1]["error_kind"] == "LLMClassifierError"


def test_runs_empty_is_instructive(diagnostics_native_profile: NativeCliProfileFixture) -> None:
    """With no LLM run record the verb reports empty and surfaces a guidance notice."""
    result = invoke_diagnostics(["--format", "json", "app", "diagnostics", "runs"], diagnostics_native_profile)
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    payload = envelope["result"]

    assert payload["has_run_data"] is False
    assert payload["runs"] == []
    assert payload["total_runs"] == 0

    codes = {notice["code"] for notice in envelope.get("notices", [])}
    assert "diagnostics.runs.no_run_data" in codes


def test_runs_provider_filter_scopes_the_listing(diagnostics_native_profile: NativeCliProfileFixture) -> None:
    """``--provider`` restricts the listing to one provider label."""
    seed_claude_and_codex_runs()

    result = invoke_diagnostics(
        ["--format", "json", "app", "diagnostics", "runs", "--provider", "llm:codex:test-model"],
        diagnostics_native_profile,
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert len(payload["runs"]) == 1
    assert payload["runs"][0]["provider"] == "llm:codex:test-model"
    assert payload["total_runs"] == 1


def test_runs_since_until_scopes_by_date(diagnostics_native_profile: NativeCliProfileFixture) -> None:
    """``--since``/``--until`` narrow the listing by date."""
    seed_claude_and_codex_runs()

    result = invoke_diagnostics(
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
        diagnostics_native_profile,
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["total_runs"] == 1
    assert payload["runs"][0]["run_id"] == "run-1"


def test_runs_limit_caps_the_most_recent_rows(diagnostics_native_profile: NativeCliProfileFixture) -> None:
    """``--limit`` caps the listing to the N most-recent rows."""
    seed_claude_and_codex_runs()

    result = invoke_diagnostics(
        ["--format", "json", "app", "diagnostics", "runs", "--limit", "2"], diagnostics_native_profile
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert [row["run_id"] for row in payload["runs"]] == ["run-3", "run-2"]
    assert payload["total_runs"] == 2


def test_runs_rejects_malformed_date(diagnostics_native_profile: NativeCliProfileFixture) -> None:
    """A malformed ``--since`` value is refused instructively with a non-zero exit."""
    result = invoke_diagnostics(
        ["--format", "json", "app", "diagnostics", "runs", "--since", "01/04/2026"],
        diagnostics_native_profile,
    )
    assert result.exit_code != 0
    assert "ISO date" in result.output, result.output


def test_runs_rejects_nonpositive_limit(diagnostics_native_profile: NativeCliProfileFixture) -> None:
    """A ``--limit`` below 1 is refused by the option's own ``min`` bound."""
    result = invoke_diagnostics(
        ["--format", "json", "app", "diagnostics", "runs", "--limit", "0"], diagnostics_native_profile
    )
    assert result.exit_code != 0
