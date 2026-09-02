"""Behaviour tests for :class:`~core.telemetry.HttpTelemetrySink`.

Every send-path assertion here runs against a real loopback
``ThreadingHTTPServer`` (mirroring the pattern in
``adapters/outbound/llm/_providers/tests/test_gemini.py``) or a real closed
port for the transport-failure case -- never a mocked ``httpx`` client. This
proves the default-inert and consent-gated invariants: no configured endpoint
means no send, a refused consent gate never reaches the sink at all (composed
through :func:`~core.telemetry.emit_telemetry_event`), a fully permitted
invocation POSTs exactly the allowlisted payload, and a transport failure never
escapes to the caller.

See Also:
    :class:`~core.telemetry.HttpTelemetrySink`
        Optional network sink whose default-inert behavior is asserted here.
    :class:`~core.telemetry.TelemetrySink`
        Sink protocol implemented by the HTTP transport.
    :func:`~core.telemetry.emit_telemetry_event`
        Consent-gated dispatch function used to prove refused sends stay local.
    :func:`~core.telemetry.build_telemetry_payload`
        Payload builder used to construct allowlisted wire bodies.
    :class:`~core.telemetry.TelemetryEventPayload`
        Closed schema whose JSON representation is posted by the sink.
    :class:`~core.telemetry.TelemetryTier`
        Consent tier enum used by the permitted and refused settings cases.
    :func:`~core.telemetry.telemetry_emit_permitted`
        Gate whose false result prevents the HTTP sink from being touched.
"""

from __future__ import annotations

import json
import socket
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty
from typing import override

import pytest

from ....tests.loopback_recording_server import run_loopback_server, stop_loopback_server
from ...config import Settings
from ..emit import emit_telemetry_event
from ..http_sink import HttpTelemetrySink
from ..schema import TelemetryEventPayload, build_telemetry_payload
from ..tier import TelemetryTier
from ._telemetry_endpoint_support import RecordingTelemetryEndpoint

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WORKSPACE_HASH = "d" * 64
_CAPTURED_AT = "2026-07-04T00:00:00+00:00"


def _payload() -> TelemetryEventPayload:
    return build_telemetry_payload(
        workspace_hash=_WORKSPACE_HASH,
        command="diagnostics.command_invocation",
        counters={"invocations": 1, "succeeded": 1, "failed": 0},
        timings_ms={"duration": 42},
        succeeded=True,
        captured_at=_CAPTURED_AT,
    )


def test_no_configured_endpoint_never_sends() -> None:
    """A sink built without an endpoint is permanently inert."""
    server, thread, events = run_loopback_server(RecordingTelemetryEndpoint)
    try:
        # Deliberately construct the sink with ``endpoint=None`` even though a
        # live server is running, proving the sink itself refuses to dial out
        # rather than merely happening to have nowhere configured to send.
        sink = HttpTelemetrySink(endpoint=None)
        sink.send(_payload())
    finally:
        stop_loopback_server(server, thread)
    with pytest.raises(Empty):
        events.get_nowait()


def test_consent_gate_refusal_never_reaches_the_http_sink() -> None:
    """Default-off Settings must keep the HTTP sink untouched via ``emit_telemetry_event``."""
    server, thread, events = run_loopback_server(RecordingTelemetryEndpoint)
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/collect"
        sink = HttpTelemetrySink(endpoint=endpoint)
        settings = Settings()  # fully-inert default posture
        result = emit_telemetry_event(_payload(), settings=settings, acknowledged=True, sink=sink)
    finally:
        stop_loopback_server(server, thread)
    assert result is False
    with pytest.raises(Empty):
        events.get_nowait()


def test_endpoint_configured_but_consent_off_never_sends() -> None:
    """An opted-out deployment must not send even with a fully configured endpoint."""
    server, thread, events = run_loopback_server(RecordingTelemetryEndpoint)
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/collect"
        sink = HttpTelemetrySink(endpoint=endpoint)
        settings = Settings(cadrumo_telemetry_opt_in=False, cadrumo_telemetry_tier=TelemetryTier.OFF)
        result = emit_telemetry_event(_payload(), settings=settings, acknowledged=True, sink=sink)
    finally:
        stop_loopback_server(server, thread)
    assert result is False
    with pytest.raises(Empty):
        events.get_nowait()


def test_fully_permitted_invocation_posts_the_allowlisted_payload() -> None:
    """Consent on, tier set, endpoint configured, acknowledged: the payload is POSTed."""
    server, thread, events = run_loopback_server(RecordingTelemetryEndpoint)
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/collect"
        sink = HttpTelemetrySink(endpoint=endpoint)
        settings = Settings(
            cadrumo_telemetry_opt_in=True,
            cadrumo_telemetry_tier=TelemetryTier.FULL,
            cadrumo_telemetry_endpoint=endpoint,
        )
        payload = _payload()
        result = emit_telemetry_event(payload, settings=settings, acknowledged=True, sink=sink)
    finally:
        stop_loopback_server(server, thread)
    assert result is True
    observed = events.get_nowait()
    assert observed["path"] == "/collect"
    assert observed["content_type"] == "application/json"
    assert observed["body"] == json.loads(payload.model_dump_json())


def test_transport_error_is_swallowed_and_returns_none() -> None:
    """A closed-port connection failure must never escape :meth:`~core.telemetry.HttpTelemetrySink.send`."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        unused_port = probe.getsockname()[1]
    sink = HttpTelemetrySink(endpoint=f"http://127.0.0.1:{unused_port}/collect", timeout_s=1)
    # No exception must propagate; ``send`` returns ``None`` either way.
    assert sink.send(_payload()) is None


def test_non_2xx_response_is_swallowed() -> None:
    """A collector that answers with a server error must not raise past the sink."""

    class _FailingEndpoint(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("content-length", "0")))
            _ = body
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send_header("content-length", "0")
            self.end_headers()

        @override
        def log_message(self, format: str, *args: object) -> None:
            """Silence stdlib request logging during tests."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), _FailingEndpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        sink = HttpTelemetrySink(endpoint=f"http://127.0.0.1:{server.server_port}/collect")
        assert sink.send(_payload()) is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_allowlisted_payload_cannot_carry_a_sensitive_field_over_http() -> None:
    """The wire body sent by the sink is the same structurally-closed model.

    Reuses the schema-level allowlist proof (``test_schema_allowlist.py``)
    against the actual bytes this sink transmits: since ``send`` only ever
    serialises a real ``TelemetryEventPayload`` (``extra="forbid"``, no
    free-text field), the JSON body it posts cannot carry a sensitive key --
    there is no attribute to smuggle one through.
    """
    server, thread, events = run_loopback_server(RecordingTelemetryEndpoint)
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/collect"
        HttpTelemetrySink(endpoint=endpoint).send(_payload())
    finally:
        stop_loopback_server(server, thread)
    observed = events.get_nowait()
    body = observed["body"]
    assert isinstance(body, dict)
    for forbidden_key in ("message", "context", "description", "path", "nif", "amount", "profile_id"):
        assert forbidden_key not in body
