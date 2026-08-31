"""Real-behavior CLI tests for ``aeat app diagnostics telemetry``.

Exercises ``status`` and ``flush`` end to end against the real CLI, the real
:mod:`~application.diagnostics_telemetry` composition, real encrypted
SQLite persistence in an isolated storage root, and (for the fully-permitted
send case) a real loopback HTTP server -- never a mocked transport. Proves:
the default-off posture; ``flush --dry-run`` (the CLI default) never performs
a network call regardless of posture; a sensitive/free-text field structurally
cannot appear in the previewed payload because
:class:`~core.telemetry.TelemetryEventPayload` has no such field
(``extra="forbid"``); and only a fully-permitted, explicitly acknowledged
``--no-dry-run`` invocation with a configured endpoint actually transmits.

See Also:
    :mod:`~entrypoints.cli._app_diagnostics_telemetry`
        CLI transport that implements the status and flush commands.
    :func:`~application.diagnostics_telemetry.build_telemetry_flush_preview`
        Application payload builder exercised through the CLI dry-run path.
    :func:`~application.diagnostics_telemetry.flush_telemetry`
        Application send path exercised by the acknowledged non-dry-run case.
    :class:`~core.telemetry.TelemetryEventPayload`
        Closed allowlisted payload shape rendered by the CLI.
    :class:`~adapters.outbound.llm.LLMRunTelemetryRecorder`
        Real local telemetry source seeded by the tests.
    :func:`~tests.cli_runner.invoke_cached_cli`
        Shared Typer runner used for the end-to-end CLI calls.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from queue import Empty, Queue
from typing import Any, ClassVar, cast, override

import pytest
from click.testing import Result
from pydantic import ValidationError

from ....adapters.outbound.llm._run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder
from ....core.telemetry._schema import TelemetryEventPayload
from ....core.telemetry._tier import TelemetryTier
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.cli_envelope import unwrap_cli_result as _json_result
from ....tests.cli_runner import invoke_cached_cli
from ....tests.loopback_recording_server import run_loopback_server, stop_loopback_server
from .._diagnostics_payloads import TelemetryFlushResult

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "88888888-9999-4aaa-8bbb-cccccccccccc"

_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id=_BUCKET_ID,
    autouse=False,
    settings_overrides={"cadrumo_output_language": "en"},
)


def _invoke(args: list[str]) -> Result:
    return invoke_cached_cli(args)


class _RecordingTelemetryEndpoint(BaseHTTPRequestHandler):
    """Local telemetry-collector-shaped endpoint used to prove a real send occurred."""

    events: ClassVar[Queue[dict[str, object]]]

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("content-length", "0")))
        self.events.put({"path": self.path, "body": json.loads(body.decode("utf-8"))})
        self.send_response(HTTPStatus.OK)
        self.send_header("content-length", "0")
        self.end_headers()

    @override
    def log_message(self, format: str, *args: object) -> None:
        """Silence stdlib request logging during tests."""


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
    # survives, the path does not. This proves the display path is redacted
    # while the send-path test below proves the real, unredacted endpoint is
    # what actually receives the POST.
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
    assert "off, crash_only, full" in result.output or "not-a-real-tier" in result.output


def test_telemetry_flush_dry_run_is_the_default_and_sends_nothing(_isolated_backend: None) -> None:
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


def test_telemetry_flush_dry_run_never_dials_out_even_when_fully_configured(_isolated_backend: None) -> None:
    """Even a fully opted-in, tiered, endpoint-configured, acknowledged ``--dry-run`` sends nothing."""
    server, thread, events = run_loopback_server(_RecordingTelemetryEndpoint)
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/collect"
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
                endpoint,
                "--acknowledge-remote-telemetry",
            ],
        )
    finally:
        stop_loopback_server(server, thread)

    assert result.exit_code == 0, result.output
    payload = _json_result(result)
    assert payload["dry_run"] is True
    assert payload["sent"] is False
    assert payload["would_send"] is True  # honest: it WOULD send on --no-dry-run
    with pytest.raises(Empty):
        events.get_nowait()


def test_telemetry_flush_no_dry_run_refuses_without_acknowledgement(_isolated_backend: None) -> None:
    """``--no-dry-run`` without ``--acknowledge-remote-telemetry`` is still a safe no-op."""
    server, thread, events = run_loopback_server(_RecordingTelemetryEndpoint)
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/collect"
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
                "--endpoint",
                endpoint,
            ],
        )
    finally:
        stop_loopback_server(server, thread)

    assert result.exit_code == 0, result.output
    payload = _json_result(result)
    assert payload["dry_run"] is False
    assert payload["sent"] is False
    assert payload["gate_permits"] is False
    with pytest.raises(Empty):
        events.get_nowait()


def test_telemetry_flush_no_dry_run_sends_when_fully_permitted(_isolated_backend: None) -> None:
    """A fully-permitted, acknowledged ``--no-dry-run`` actually POSTs the previewed payload."""
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

    server, thread, events = run_loopback_server(_RecordingTelemetryEndpoint)
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/collect"
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
                "--endpoint",
                endpoint,
                "--acknowledge-remote-telemetry",
            ],
        )
        observed = events.get_nowait()
    finally:
        stop_loopback_server(server, thread)

    assert result.exit_code == 0, result.output
    payload = _json_result(result)
    assert payload["dry_run"] is False
    assert payload["sent"] is True
    assert payload["would_send"] is True
    observed_body = cast("dict[str, Any]", observed["body"])
    assert observed_body["command"] == "diagnostics.llm_run"
    assert observed_body["counters"]["runs"] == 1
    assert observed_body == payload["payload"]
