"""Real-behavior CLI tests for ``aeat app diagnostics telemetry``.

Exercises public ``status`` and worker-backed ``flush`` against the real CLI
and a synthetic encrypted profile. It covers the default-off posture, dry-run
previews, and safe no-op flushes without a complete send configuration. A
sensitive/free-text field structurally cannot appear in the previewed payload because
:class:`~core.telemetry.TelemetryEventPayload` has no such field
(``extra="forbid"``); and an unacknowledged or unconfigured ``--no-dry-run``
invocation remains a safe no-op.

See Also:
    :mod:`~entrypoints.cli._app_diagnostics_telemetry`
        CLI transport that implements the status and flush commands.
    :func:`~application.diagnostics_telemetry.build_telemetry_flush_preview`
        Application payload builder exercised through the CLI dry-run path.
    :mod:`~application.diagnostics_operation`
        Exact-profile worker operation backing telemetry previews.
    :class:`~core.telemetry.TelemetryEventPayload`
        Closed allowlisted payload shape rendered by the CLI.
    :class:`~adapters.outbound.llm.LLMRunTelemetryRecorder`
        Real local telemetry source seeded by the tests.
    :func:`~tests.cli_runner.invoke_cached_cli`
        Shared Typer runner used for the end-to-end CLI calls.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....adapters.persistence.llm.run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder
from ....adapters.persistence.storage.tests.active_profile_isolated_backend_fixture import (
    active_profile_isolated_backend_fixture,
)
from ....core.telemetry.schema import TelemetryEventPayload
from ....core.telemetry.tier import TelemetryTier
from ....tests.cli_envelope import unwrap_cli_result as _json_result
from .._diagnostics_payloads import TelemetryFlushResult
from .diagnostics_native_support import diagnostics_native_profile, invoke_diagnostics_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.usefixtures("authority_operation"),
]

__all__ = ["diagnostics_native_profile"]

_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id="88888888-9999-4aaa-8bbb-cccccccccccc",
    autouse=False,
    settings_overrides={"cadrumo_output_language": "en"},
)


def _invoke(args: list[str]):
    return invoke_diagnostics_cli(args)


def test_telemetry_status_defaults_to_fully_inert(_isolated_backend: None) -> None:
    """A fresh deployment reports the fully-off posture and never emits anything."""
    result = _invoke(["--format", "json", "app", "diagnostics", "telemetry", "status"])
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["opt_in"] is False
    assert payload["tier"] == "off"
    assert payload["gestor_mode"] is False
    assert payload["endpoint"] is None
    assert payload["would_emit_if_acknowledged"] is False


@pytest.mark.parametrize("tier", ["", "bogus"])
def test_telemetry_status_payload_refuses_unknown_tier(tier: str) -> None:
    """The CLI status boundary admits only the core telemetry posture enum."""

    from .._diagnostics_payloads import TelemetryStatusResult

    with pytest.raises(ValidationError, match="TelemetryTier"):
        TelemetryStatusResult(
            opt_in=False,
            tier=tier,
            gestor_mode=False,
            would_emit_if_acknowledged=False,
        )

    accepted = TelemetryStatusResult(
        opt_in=False,
        tier=TelemetryTier.OFF,
        gestor_mode=False,
        would_emit_if_acknowledged=False,
    )
    assert accepted.tier is TelemetryTier.OFF


def test_telemetry_status_previews_a_fully_opted_in_posture_via_flags(_isolated_backend: None) -> None:
    """The ``--opt-in``/``--tier``/``--endpoint`` flags preview a posture without persisting it."""
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "diagnostics",
            "telemetry",
            "status",
            "--opt-in",
            "--tier",
            "full",
            "--endpoint",
            "https://telemetry.example.test/collect",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["opt_in"] is True
    assert payload["tier"] == "full"
    # The universal CLI success-output redaction funnel
    # (``redact_structured_for_cli_output``) applies its ``url-host-only``
    # rule to every emitted URL unconditionally ("URLs remain redacted
    # regardless" -- ``core.redaction`` module docs); the endpoint host
    # survives, the path does not. This proves the display path is redacted.
    assert payload["endpoint"] == "https://telemetry.example.test"
    assert payload["would_emit_if_acknowledged"] is True

    # The override was scoped to this single invocation; a fresh status call
    # with no flags reports the deployment's real (still fully-off) posture.
    fresh = _invoke(["--format", "json", "app", "diagnostics", "telemetry", "status"])
    assert fresh.exit_code == 0, fresh.output
    fresh_payload = _json_result(fresh)
    assert fresh_payload["opt_in"] is False
    assert fresh_payload["tier"] == "off"


def test_telemetry_flush_payload_round_trips_the_canonical_event_schema() -> None:
    """The CLI envelope nests the actual allowlisted telemetry event model."""
    wire_payload: dict[str, object] = {
        "schema_version": 1,
        "workspace_hash": "a" * 64,
        "command": "diagnostics.llm_run",
        "counters": {"runs": 2, "failed": 1},
        "timings_ms": {"duration": 1200},
        "succeeded": False,
        "error_kind": "LLMClassifierError",
        "captured_at": "2026-08-02T10:00:00+00:00",
    }

    result = TelemetryFlushResult.model_validate(
        {
            "dry_run": True,
            "payload": wire_payload,
            "gate_permits": False,
            "endpoint_configured": False,
            "would_send": False,
            "sent": False,
        },
    )

    assert isinstance(result.payload, TelemetryEventPayload)
    assert result.model_dump(mode="json")["payload"] == wire_payload


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("schema_version", 0),
        ("workspace_hash", "a" * 63),
        ("error_kind", "x" * 65),
    ],
)
def test_telemetry_flush_payload_refuses_malformed_canonical_event_fields(
    field: str,
    invalid_value: int | str,
) -> None:
    """The CLI envelope retains the canonical event model's validation boundaries."""
    wire_payload: dict[str, object] = {
        "schema_version": 1,
        "workspace_hash": "a" * 64,
        "command": "diagnostics.llm_run",
        "counters": {},
        "timings_ms": {},
        "succeeded": False,
        "error_kind": "LLMClassifierError",
        "captured_at": "2026-08-02T10:00:00+00:00",
    }
    wire_payload[field] = invalid_value

    with pytest.raises(ValidationError, match=field):
        TelemetryFlushResult.model_validate(
            {
                "dry_run": True,
                "payload": wire_payload,
                "gate_permits": False,
                "endpoint_configured": False,
                "would_send": False,
                "sent": False,
            },
        )


def test_telemetry_flush_rejects_an_unknown_tier(_isolated_backend: None) -> None:
    result = _invoke(
        ["--format", "json", "app", "diagnostics", "telemetry", "status", "--tier", "not-a-real-tier"],
    )
    assert result.exit_code != 0
    assert "off, crash_only, full" in result.output


def test_telemetry_flush_dry_run_is_the_default_and_sends_nothing(
    diagnostics_native_profile: NativeCliProfileFixture,
) -> None:
    """``flush`` with no flags is a dry run: the payload is built, nothing is sent."""
    recorder = LLMRunTelemetryRecorder()
    recorder.record(
        LLMRunRecord(
            run_id="run-1",
            caller="test",
            provider="llm:claude:test-model",
            duration_ms=1000,
            succeeded=True,
            started_at=datetime(2026, 4, 1, tzinfo=UTC),
        ),
    )
    recorder.record(
        LLMRunRecord(
            run_id="run-2",
            caller="test",
            provider="llm:claude:test-model",
            duration_ms=2000,
            succeeded=False,
            error_kind="LLMClassifierError",
            started_at=datetime(2026, 4, 2, tzinfo=UTC),
        ),
    )

    result = _invoke(["--format", "json", "app", "diagnostics", "telemetry", "flush"])
    assert result.exit_code == 0, result.output
    payload = _json_result(result)

    assert payload["dry_run"] is True
    assert payload["sent"] is False
    assert payload["payload"]["command"] == "diagnostics.llm_run"
    assert payload["payload"]["counters"]["runs"] == 2
    assert payload["payload"]["counters"]["succeeded"] == 1
    assert payload["payload"]["counters"]["failed"] == 1
    # Structural allowlist proof: the previewed payload carries exactly the
    # TelemetryEventPayload field set -- no free-text, no transaction/profile
    # identity field could appear even if a producer tried to add one.
    assert set(payload["payload"]) == {
        "schema_version",
        "workspace_hash",
        "command",
        "counters",
        "timings_ms",
        "succeeded",
        "error_kind",
        "captured_at",
    }


def test_telemetry_flush_dry_run_never_dials_out_even_when_fully_configured(
    diagnostics_native_profile: NativeCliProfileFixture,
) -> None:
    """Even a fully opted-in, tiered, endpoint-configured, acknowledged ``--dry-run`` sends nothing."""
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "diagnostics",
            "telemetry",
            "flush",
            "--dry-run",
            "--opt-in",
            "--tier",
            "full",
            "--endpoint",
            "https://telemetry.example.test/collect",
            "--acknowledge-remote-telemetry",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = _json_result(result)
    assert payload["dry_run"] is True
    assert payload["sent"] is False
    assert payload["would_send"] is True  # honest: it WOULD send on --no-dry-run


def test_telemetry_flush_no_dry_run_refuses_without_acknowledgement(
    diagnostics_native_profile: NativeCliProfileFixture,
) -> None:
    """``--no-dry-run`` without ``--acknowledge-remote-telemetry`` is still a safe no-op."""
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "diagnostics",
            "telemetry",
            "flush",
            "--no-dry-run",
            "--opt-in",
            "--tier",
            "full",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = _json_result(result)
    assert payload["dry_run"] is False
    assert payload["sent"] is False
    assert payload["gate_permits"] is False


def test_telemetry_flush_no_dry_run_without_endpoint_is_safe_noop(
    diagnostics_native_profile: NativeCliProfileFixture,
) -> None:
    """An acknowledged invocation still does not send without an endpoint."""
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "diagnostics",
            "telemetry",
            "flush",
            "--no-dry-run",
            "--opt-in",
            "--tier",
            "full",
            "--acknowledge-remote-telemetry",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = _json_result(result)
    assert payload["dry_run"] is False
    assert payload["sent"] is False
    assert payload["endpoint_configured"] is False
    assert payload["would_send"] is False
