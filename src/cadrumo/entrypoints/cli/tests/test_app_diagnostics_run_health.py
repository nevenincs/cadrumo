"""Real-behavior CLI tests for ``aeat app diagnostics run-health``.

Exercises the diagnose verb end to end against the real CLI, the real
:func:`~cadrumo.application.diagnostics_run_health.build_run_health_report`
aggregator, real encrypted SQLite persistence in an isolated storage root, and
the real :func:`~cadrumo.application.auth.test_operator_auth` session probe. No
test doubles: LLM run telemetry is seeded through its production writer
(:class:`~cadrumo.adapters.outbound.llm.LLMRunTelemetryRecorder`) and the verb
reports it back typed, alongside a real auth-session staleness verdict for a
profile with no configured auth provider.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from click.testing import Result
from pydantic import ValidationError

from ....adapters.outbound.llm.run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.cli_envelope import unwrap_cli_result as _json_result
from ....tests.cli_runner import invoke_cached_cli
from .._diagnostics_payloads import (
    ErrorKindCountPayload,
    LatencyPercentilesPayload,
    LlmRunProviderPayload,
    RunRecordPayload,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "11111111-2222-4333-8444-555555555555"

_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id=_BUCKET_ID,
    autouse=False,
    settings_overrides={"cadrumo_output_language": "en"},
)


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


def test_run_health_reports_seeded_llm_runs_and_no_session(_isolated_backend: None) -> None:
    """The verb reports the seeded run telemetry typed and a no-session auth verdict."""
    _seed_runs()

    result = _invoke(["--format", "json", "app", "diagnostics", "run-health"])
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["has_run_data"] is True
    providers = {row["provider"]: row for row in payload["llm_providers"]}
    assert set(providers) == {"llm:claude:test-model", "llm:codex:test-model"}

    claude = providers["llm:claude:test-model"]
    assert claude["runs"] == 2
    assert claude["succeeded"] == 1
    assert claude["failed"] == 1
    assert claude["min_duration_ms"] == 1200
    assert claude["max_duration_ms"] == 45000

    codex = providers["llm:codex:test-model"]
    assert codex["runs"] == 1
    assert codex["succeeded"] == 1
    assert codex["failed"] == 0

    assert payload["total_runs"] == 3
    assert payload["total_succeeded"] == 2
    assert payload["total_failed"] == 1

    # No auth provider is configured for this fresh profile, so the probe
    # reports no persisted session -- a real, non-mocked verdict.
    assert payload["auth_configured"] is False
    assert payload["persisted_session_present"] is False
    assert payload["session_stale"] is False


def test_run_health_empty_is_instructive(_isolated_backend: None) -> None:
    """With no LLM run telemetry the verb reports empty and surfaces a guidance notice."""
    result = _invoke(["--format", "json", "app", "diagnostics", "run-health"])
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    payload = envelope["result"]

    assert payload["has_run_data"] is False
    assert payload["llm_providers"] == []
    assert payload["total_runs"] == 0

    codes = {notice["code"] for notice in envelope.get("notices", [])}
    assert "diagnostics.run_health.no_session" in codes


def test_run_health_provider_filter_scopes_the_report(_isolated_backend: None) -> None:
    """``--provider`` restricts the LLM run-timing section to one provider label."""
    _seed_runs()

    result = _invoke(
        ["--format", "json", "app", "diagnostics", "run-health", "--provider", "llm:codex:test-model"],
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert len(payload["llm_providers"]) == 1
    assert payload["llm_providers"][0]["provider"] == "llm:codex:test-model"
    assert payload["total_runs"] == 1


def test_run_health_since_until_scopes_by_date(_isolated_backend: None) -> None:
    """``--since``/``--until`` narrow the LLM run-timing section by date."""
    _seed_runs()

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "diagnostics",
            "run-health",
            "--since",
            "2026-04-01",
            "--until",
            "2026-04-01",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["total_runs"] == 1
    assert payload["llm_providers"][0]["provider"] == "llm:claude:test-model"
    assert payload["llm_providers"][0]["runs"] == 1


def test_run_health_rejects_malformed_date(_isolated_backend: None) -> None:
    """A malformed ``--since`` value is refused instructively with a non-zero exit."""
    result = _invoke(["--format", "json", "app", "diagnostics", "run-health", "--since", "01/04/2026"])
    assert result.exit_code != 0
    assert "ISO date" in result.output


def test_run_health_payloads_mirror_their_canonical_bounds() -> None:
    """The diagnostics transport must refuse what its canonical models refuse.

    The run-health payload family redeclared provider/run/caller identities and
    every counter as bare strings and ints, so an empty identity, a negative
    run or duration, and a malformed timestamp could all cross the
    ``diagnostics.*`` envelopes.

    The bounds mirror the canonical models exactly, including two places the
    obvious guess is wrong: the nullable duration and percentile fields carry
    NO lower bound (the canonical models leave them unbounded, and a bound
    invented here would be stricter than the contract it claims to mirror), and
    ``ErrorKindCount.count`` is ``ge=1`` rather than ``ge=0`` because a row only
    exists for an error kind that occurred.
    """
    provider_row = LlmRunProviderPayload(provider="claude", runs=1, succeeded=1, failed=0)
    assert provider_row.min_duration_ms is None

    for label, model, base, override in (
        (
            "empty provider",
            LlmRunProviderPayload,
            {"provider": "claude", "runs": 1, "succeeded": 1, "failed": 0},
            {"provider": ""},
        ),
        (
            "negative runs",
            LlmRunProviderPayload,
            {"provider": "claude", "runs": 1, "succeeded": 1, "failed": 0},
            {"runs": -1},
        ),
        ("empty run id", RunRecordPayload, _RUN_RECORD_BASE, {"run_id": ""}),
        ("empty caller", RunRecordPayload, _RUN_RECORD_BASE, {"caller": ""}),
        ("negative duration", RunRecordPayload, _RUN_RECORD_BASE, {"duration_ms": -1}),
        ("negative entries", LatencyPercentilesPayload, {"entries": 1}, {"entries": -1}),
        (
            "empty error kind",
            ErrorKindCountPayload,
            {"error_kind": "timeout", "provider": "claude", "count": 1},
            {"error_kind": ""},
        ),
        (
            "zero error count",
            ErrorKindCountPayload,
            {"error_kind": "timeout", "provider": "claude", "count": 1},
            {"count": 0},
        ),
    ):
        model.model_validate(base)  # positive control: the base must be accepted
        try:
            model.model_validate(base | override)
        except ValidationError:
            continue
        pytest.fail(f"{label} was accepted by the transport row")

    # Deliberately permitted, because the canonical models permit them.
    LatencyPercentilesPayload(entries=1, p50_duration_ms=-1)
    LlmRunProviderPayload(provider="claude", runs=1, succeeded=1, failed=0, min_duration_ms=-1)


def test_run_record_timestamp_round_trips_and_refuses_malformed_text() -> None:
    """``started_at`` is a real datetime on the canonical record, not free text."""
    row = RunRecordPayload.model_validate(_RUN_RECORD_BASE)
    rendered = row.model_dump_json()
    assert '"started_at":"2026-01-01T00:00:00Z"' in rendered
    assert RunRecordPayload.model_validate_json(rendered) == row

    tampered = json.loads(rendered) | {"started_at": "not-date"}
    with pytest.raises(ValidationError):
        RunRecordPayload.model_validate_json(json.dumps(tampered))


_RUN_RECORD_BASE = {
    "run_id": "run-1",
    "caller": "cli",
    "provider": "claude",
    "model": "sonnet",
    "duration_ms": 5,
    "succeeded": True,
    "error_kind": "",
    "started_at": datetime(2026, 1, 1, tzinfo=UTC),
}
