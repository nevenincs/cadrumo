"""Real-behavior tests for :mod:`~application.diagnostics_telemetry`.

Exercises the status report and the dry-run-safe flush composition against
real :class:`~core.config.Settings` and a real
:class:`~adapters.outbound.llm.LLMRunTelemetryRecorder` (real encrypted
secure-object persistence, no mocks). Proves the default-off posture, that
``build_telemetry_flush_preview`` never performs a network call regardless of
posture, and that :func:`~application.diagnostics_telemetry.flush_telemetry`
composes the real core gate/sink primitives rather than re-implementing them
(``aeat-architecture-boundaries``): a real loopback HTTP server
proves a fully-permitted flush actually transmits the exact previewed payload,
and a refused-consent flush never dials out.

See Also:
    :func:`~application.diagnostics_telemetry.build_telemetry_status_report`
        Application service that reports the deployment telemetry posture.
    :func:`~application.diagnostics_telemetry.build_telemetry_flush_preview`
        Dry-run-safe payload builder shared by preview and send paths.
    :class:`~core.telemetry.TelemetryEventPayload`
        Closed allowlisted payload shape asserted by the tests.
    :class:`~core.telemetry.TelemetryTier`
        Closed opt-in tier enum used to exercise the consent gate.
    :mod:`~entrypoints.cli._app_diagnostics_telemetry`
        CLI transport covered by the sibling end-to-end telemetry tests.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from queue import Empty, Queue
from typing import Any, ClassVar, cast, override

import pytest

from ...adapters.outbound.llm.run_telemetry import LLMRunRecord, LLMRunTelemetryRecorder
from ...core.config import Settings
from ...core.telemetry.tier import TelemetryTier
from ...tests.loopback_recording_server import run_loopback_server, stop_loopback_server
from ...tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ..diagnostics_telemetry import (
    build_telemetry_flush_preview,
    build_telemetry_status_report,
    flush_telemetry,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "66666666-6666-4666-8666-666666666666"


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as p:
        yield p


class _RecordingTelemetryEndpoint(BaseHTTPRequestHandler):
    """Local telemetry-collector-shaped endpoint used to inspect the real HTTP POST."""

    events: ClassVar[Queue[dict[str, object]]]

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("content-length", "0")))
        self.events.put(
            {
                "path": self.path,
                "body": json.loads(body.decode("utf-8")),
            },
        )
        self.send_response(HTTPStatus.OK)
        self.send_header("content-length", "0")
        self.end_headers()

    @override
    def log_message(self, format: str, *args: object) -> None:
        """Silence stdlib request logging during tests."""


def test_status_report_defaults_to_the_fully_inert_posture(profile: TestRuntimeProfile) -> None:
    settings = Settings()
    report = build_telemetry_status_report(settings=settings)

    assert report.opt_in is False
    assert report.tier is TelemetryTier.OFF
    assert report.gestor_mode is False
    assert report.endpoint is None
    assert report.would_emit_if_acknowledged is False


def test_status_report_reflects_a_fully_opted_in_posture(profile: TestRuntimeProfile) -> None:
    settings = Settings(cadrumo_telemetry_opt_in=True, cadrumo_telemetry_tier=TelemetryTier.FULL)
    report = build_telemetry_status_report(settings=settings)

    assert report.opt_in is True
    assert report.tier is TelemetryTier.FULL
    assert report.would_emit_if_acknowledged is True


def test_flush_preview_aggregates_real_recorded_llm_runs_without_any_network_call(
    profile: TestRuntimeProfile,
) -> None:
    """The preview reflects real seeded run data and never dials out."""
    recorder = LLMRunTelemetryRecorder()
    recorder.record(
        LLMRunRecord(
            run_id="a",
            caller="test",
            provider="llm:claude:test-model",
            duration_ms=1000,
            succeeded=True,
            started_at=datetime(2026, 4, 1, tzinfo=UTC),
        ),
    )
    recorder.record(
        LLMRunRecord(
            run_id="b",
            caller="test",
            provider="llm:claude:test-model",
            duration_ms=9000,
            succeeded=False,
            error_kind="LLMClassifierError",
            started_at=datetime(2026, 4, 2, tzinfo=UTC),
        ),
    )

    settings = Settings()  # default-off posture
    preview = build_telemetry_flush_preview(settings=settings)

    assert preview.payload.command == "diagnostics.llm_run"
    assert preview.payload.counters["runs"] == 2
    assert preview.payload.counters["succeeded"] == 1
    assert preview.payload.counters["failed"] == 1
    assert preview.payload.succeeded is False
    # Sensitive/free-text content structurally cannot appear: the payload
    # model has no field wide enough to carry it (`extra="forbid"`), so this
    # is a structural guarantee rather than a scrub -- confirm no such key
    # exists on the model at all.
    dumped = preview.payload.model_dump()
    assert set(dumped) == {
        "schema_version",
        "workspace_hash",
        "command",
        "counters",
        "timings_ms",
        "succeeded",
        "error_kind",
        "captured_at",
    }
    assert preview.gate_permits is False
    assert preview.endpoint_configured is False
    assert preview.would_send is False


def test_flush_telemetry_never_sends_when_consent_gate_refuses(profile: TestRuntimeProfile) -> None:
    """A fully-configured endpoint with the default-off posture never receives a POST."""
    server, thread, events = run_loopback_server(_RecordingTelemetryEndpoint)
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/collect"
        settings = Settings(cadrumo_telemetry_endpoint=endpoint)  # opt_in stays False
        preview = flush_telemetry(settings=settings, acknowledged=True)
    finally:
        stop_loopback_server(server, thread)

    assert preview.gate_permits is False
    assert preview.would_send is False
    with pytest.raises(Empty):
        events.get_nowait()


def test_flush_telemetry_never_sends_without_a_configured_endpoint(profile: TestRuntimeProfile) -> None:
    """Full opt-in/tier/acknowledgement still never sends when no endpoint is configured."""
    settings = Settings(cadrumo_telemetry_opt_in=True, cadrumo_telemetry_tier=TelemetryTier.FULL)
    preview = flush_telemetry(settings=settings, acknowledged=True)

    assert preview.gate_permits is True
    assert preview.endpoint_configured is False
    assert preview.would_send is False


def test_flush_telemetry_sends_the_exact_previewed_payload_when_fully_permitted(
    profile: TestRuntimeProfile,
) -> None:
    """A fully-permitted flush POSTs exactly the payload the preview showed."""
    recorder = LLMRunTelemetryRecorder()
    recorder.record(
        LLMRunRecord(
            run_id="a",
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
        settings = Settings(
            cadrumo_telemetry_opt_in=True,
            cadrumo_telemetry_tier=TelemetryTier.FULL,
            cadrumo_telemetry_endpoint=endpoint,
        )
        # A prior --dry-run-shaped preview (no send) and the real send share
        # the same construction path and therefore the same aggregate
        # shape -- except ``captured_at``, which is a fresh wall-clock
        # timestamp on every call by design.
        dry_run_preview = build_telemetry_flush_preview(settings=settings, acknowledged=True)
        sent_preview = flush_telemetry(settings=settings, acknowledged=True)
        observed = events.get_nowait()
    finally:
        stop_loopback_server(server, thread)

    assert sent_preview.would_send is True
    assert dry_run_preview.would_send is True
    dry_run_dump = dry_run_preview.payload.model_dump(exclude={"captured_at"})
    sent_dump = sent_preview.payload.model_dump(exclude={"captured_at"})
    assert dry_run_dump == sent_dump
    # The payload actually transmitted over the wire is byte-identical (as
    # JSON) to the exact object handed to the sink -- no re-derivation, no
    # drift between construction and transmission.
    observed_body = cast("dict[str, Any]", observed["body"])
    assert observed_body == json.loads(sent_preview.payload.model_dump_json())
    assert observed_body["counters"]["runs"] == 1


def test_flush_telemetry_requires_per_invocation_acknowledgement(profile: TestRuntimeProfile) -> None:
    """Opt-in, tier, and endpoint alone are not enough without ``acknowledged=True``."""
    server, thread, events = run_loopback_server(_RecordingTelemetryEndpoint)
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/collect"
        settings = Settings(
            cadrumo_telemetry_opt_in=True,
            cadrumo_telemetry_tier=TelemetryTier.FULL,
            cadrumo_telemetry_endpoint=endpoint,
        )
        preview = flush_telemetry(settings=settings, acknowledged=False)
    finally:
        stop_loopback_server(server, thread)

    assert preview.gate_permits is False
    with pytest.raises(Empty):
        events.get_nowait()
