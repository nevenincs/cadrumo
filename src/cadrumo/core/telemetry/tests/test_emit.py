"""Tests for the single remote-telemetry emit call site.

Proves the consent gate composes correctly with the sink dispatch: a refused
gate never touches the sink at all (true no-op), and a permitted gate hands
the exact allowlisted payload to the sink. Uses a real, minimal in-memory
:class:`~core.telemetry.TelemetrySink` implementation (not a mock) to observe dispatch --
this is the sanctioned "test double for isolating pure logic" case
(``aeat-local-execution`` / the project's real-behavior test mandate), since
no external service or persistence boundary is involved.

See Also:
    :func:`~core.telemetry.emit_telemetry_event`:
        Consent-gated dispatcher under test.
    :func:`~core.telemetry.telemetry_emit_permitted`:
        Four-way gate composed before any sink receives a payload.
    :class:`~core.telemetry.LocalNoopTelemetrySink`:
        Default inert sink used when no transport is supplied.
    :class:`~core.telemetry.TelemetryEventPayload`:
        Already-allowlisted payload handed to the sink unchanged.
"""

from __future__ import annotations

import pytest

from ...config import Settings
from .. import (
    LocalNoopTelemetrySink,
    TelemetryEventPayload,
    TelemetryTier,
    build_telemetry_payload,
    emit_telemetry_event,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WORKSPACE_HASH = "b" * 64
_CAPTURED_AT = "2026-07-04T00:00:00+00:00"


class _RecordingSink:
    """A real, minimal sink that records every payload it receives.

    Not a mock: it has no configured return values or call assertions built
    in. It is genuine, tiny production-shaped code -- exactly what a caller
    would write to inspect what a real sink would have received.
    """

    def __init__(self) -> None:
        self.received: list[TelemetryEventPayload] = []

    def send(self, payload: TelemetryEventPayload) -> None:
        self.received.append(payload)


def _payload() -> TelemetryEventPayload:
    return build_telemetry_payload(
        workspace_hash=_WORKSPACE_HASH,
        command="diagnostics.run_health",
        succeeded=True,
        captured_at=_CAPTURED_AT,
    )


def test_default_off_settings_never_touch_the_sink() -> None:
    settings = Settings()
    sink = _RecordingSink()
    result = emit_telemetry_event(_payload(), settings=settings, acknowledged=True, sink=sink)
    assert result is False
    assert sink.received == []


def test_opted_in_but_not_acknowledged_never_touches_the_sink() -> None:
    settings = Settings(aeat_telemetry_opt_in=True, aeat_telemetry_tier=TelemetryTier.CRASH_ONLY)
    sink = _RecordingSink()
    result = emit_telemetry_event(_payload(), settings=settings, acknowledged=False, sink=sink)
    assert result is False
    assert sink.received == []


def test_gestor_mode_never_touches_the_sink_even_when_fully_opted_in() -> None:
    settings = Settings(
        aeat_telemetry_opt_in=True,
        aeat_telemetry_tier=TelemetryTier.FULL,
        aeat_telemetry_gestor_mode=True,
    )
    sink = _RecordingSink()
    result = emit_telemetry_event(_payload(), settings=settings, acknowledged=True, sink=sink)
    assert result is False
    assert sink.received == []


def test_fully_permitted_invocation_dispatches_the_exact_payload_to_the_sink() -> None:
    settings = Settings(aeat_telemetry_opt_in=True, aeat_telemetry_tier=TelemetryTier.FULL)
    sink = _RecordingSink()
    payload = _payload()
    result = emit_telemetry_event(payload, settings=settings, acknowledged=True, sink=sink)
    assert result is True
    assert sink.received == [payload]


def test_default_sink_is_the_local_noop_and_produces_no_observable_side_effect() -> None:
    """No sink argument at all falls back to :class:`LocalNoopTelemetrySink`.

    This is the "no transport exists yet" default: even when the gate fully
    permits emission, the payload is discarded rather than sent anywhere --
    there is no HTTP client, no file write, no state mutation to observe.
    """
    settings = Settings(aeat_telemetry_opt_in=True, aeat_telemetry_tier=TelemetryTier.FULL)
    result = emit_telemetry_event(_payload(), settings=settings, acknowledged=True)
    assert result is True  # the gate permitted it; the noop sink accepted it


def test_local_noop_sink_send_returns_none() -> None:
    sink = LocalNoopTelemetrySink()
    assert sink.send(_payload()) is None
