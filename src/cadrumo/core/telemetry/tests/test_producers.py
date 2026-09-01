"""Real-HTTP tests for the non-sensitive operational telemetry producers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from queue import Empty, Queue
from typing import cast

import pytest

from ....tests.loopback_recording_server import run_loopback_server, stop_loopback_server
from ...config import Settings
from .._http_sink import HttpTelemetrySink
from .._producers import emit_command_invocation_telemetry, emit_error_frequency_telemetry, emit_llm_run_telemetry
from ..tier import TelemetryTier
from ._telemetry_endpoint_support import RecordingTelemetryEndpoint

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WORKSPACE_HASH = "c" * 64
_CAPTURED_AT = "2026-07-04T00:00:00+00:00"


@contextmanager
def _opened_http_sink() -> Iterator[tuple[HttpTelemetrySink, Queue[dict[str, object]]]]:
    server, thread, events = run_loopback_server(RecordingTelemetryEndpoint)
    try:
        yield HttpTelemetrySink(endpoint=f"http://127.0.0.1:{server.server_port}/collect"), events
    finally:
        stop_loopback_server(server, thread)


def _permitted_settings() -> Settings:
    return Settings(cadrumo_telemetry_opt_in=True, cadrumo_telemetry_tier=TelemetryTier.FULL)


def _received_payload(events: Queue[dict[str, object]]) -> dict[str, object]:
    event = events.get(timeout=2)
    assert event["path"] == "/collect"
    assert event["content_type"] == "application/json"
    payload = event["body"]
    assert isinstance(payload, dict)
    return cast("dict[str, object]", payload)


def test_command_invocation_consent_off_emits_nothing() -> None:
    with _opened_http_sink() as (sink, events):
        result = emit_command_invocation_telemetry(
            workspace_hash=_WORKSPACE_HASH,
            succeeded=True,
            duration_ms=120,
            captured_at=_CAPTURED_AT,
            settings=Settings(),
            acknowledged=True,
            sink=sink,
        )
        assert result is False
        with pytest.raises(Empty):
            events.get_nowait()


def test_command_invocation_permitted_dispatches_allowlisted_payload() -> None:
    with _opened_http_sink() as (sink, events):
        result = emit_command_invocation_telemetry(
            workspace_hash=_WORKSPACE_HASH,
            succeeded=True,
            duration_ms=250,
            captured_at=_CAPTURED_AT,
            settings=_permitted_settings(),
            acknowledged=True,
            sink=sink,
        )
        payload = _received_payload(events)

    assert result is True
    assert payload["command"] == "diagnostics.command_invocation"
    assert payload["counters"] == {"invocations": 1, "succeeded": 1, "failed": 0}
    assert payload["timings_ms"] == {"duration": 250}
    assert payload["succeeded"] is True


def test_command_invocation_failed_run_increments_failed_counter() -> None:
    with _opened_http_sink() as (sink, events):
        emit_command_invocation_telemetry(
            workspace_hash=_WORKSPACE_HASH,
            succeeded=False,
            duration_ms=10,
            captured_at=_CAPTURED_AT,
            settings=_permitted_settings(),
            acknowledged=True,
            sink=sink,
        )
        payload = _received_payload(events)

    assert payload["counters"] == {"invocations": 1, "succeeded": 0, "failed": 1}
    assert payload["succeeded"] is False


def test_llm_run_not_acknowledged_emits_nothing() -> None:
    with _opened_http_sink() as (sink, events):
        result = emit_llm_run_telemetry(
            workspace_hash=_WORKSPACE_HASH,
            succeeded=True,
            duration_ms=4200,
            captured_at=_CAPTURED_AT,
            settings=_permitted_settings(),
            acknowledged=False,
            sink=sink,
        )
        assert result is False
        with pytest.raises(Empty):
            events.get_nowait()


def test_llm_run_permitted_dispatches_allowlisted_payload() -> None:
    with _opened_http_sink() as (sink, events):
        result = emit_llm_run_telemetry(
            workspace_hash=_WORKSPACE_HASH,
            succeeded=True,
            duration_ms=4200,
            captured_at=_CAPTURED_AT,
            settings=_permitted_settings(),
            acknowledged=True,
            sink=sink,
        )
        payload = _received_payload(events)

    assert result is True
    assert payload["command"] == "diagnostics.llm_run"
    assert payload["counters"] == {"runs": 1, "succeeded": 1, "failed": 0}
    assert payload["timings_ms"] == {"duration": 4200}


def test_llm_run_gestor_mode_never_emits() -> None:
    settings = Settings(
        cadrumo_telemetry_opt_in=True,
        cadrumo_telemetry_tier=TelemetryTier.FULL,
        cadrumo_telemetry_gestor_mode=True,
    )
    with _opened_http_sink() as (sink, events):
        result = emit_llm_run_telemetry(
            workspace_hash=_WORKSPACE_HASH,
            succeeded=True,
            duration_ms=100,
            captured_at=_CAPTURED_AT,
            settings=settings,
            acknowledged=True,
            sink=sink,
        )
        assert result is False
        with pytest.raises(Empty):
            events.get_nowait()


def test_error_frequency_dispatches_closed_non_sensitive_payload() -> None:
    with _opened_http_sink() as (sink, events):
        result = emit_error_frequency_telemetry(
            workspace_hash=_WORKSPACE_HASH,
            error_kind="LLMClassifierError",
            captured_at=_CAPTURED_AT,
            settings=_permitted_settings(),
            acknowledged=True,
            sink=sink,
        )
        payload = _received_payload(events)

    assert result is True
    assert payload["command"] == "diagnostics.error_frequency"
    assert payload["counters"] == {"occurrences": 1}
    assert payload["error_kind"] == "LLMClassifierError"
    assert payload["succeeded"] is False
    assert {"message", "context", "nif"}.isdisjoint(payload)
