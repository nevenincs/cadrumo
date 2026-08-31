"""Tests for the single remote-telemetry emit call site.

The real HTTP dispatch and refusal paths are exercised in
``test_http_sink.py``. This module retains the default local-noop contract.

See Also:
    :func:`~core.telemetry.emit_telemetry_event`:
        Consent-gated dispatcher under test.
    :class:`~core.telemetry.LocalNoopTelemetrySink`:
        Default inert sink used when no transport is supplied.
    :class:`~core.telemetry.TelemetryEventPayload`:
        Already-allowlisted payload handed to the sink unchanged.
"""

from __future__ import annotations

import pytest

from ...config import Settings
from .._emit import LocalNoopTelemetrySink, emit_telemetry_event
from ..schema import TelemetryEventPayload, build_telemetry_payload
from ..tier import TelemetryTier

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WORKSPACE_HASH = "b" * 64
_CAPTURED_AT = "2026-07-04T00:00:00+00:00"


def _payload() -> TelemetryEventPayload:
    return build_telemetry_payload(
        workspace_hash=_WORKSPACE_HASH,
        command="diagnostics.run_health",
        succeeded=True,
        captured_at=_CAPTURED_AT,
    )


def test_default_sink_is_the_local_noop_and_produces_no_observable_side_effect() -> None:
    """No sink argument at all falls back to :class:`LocalNoopTelemetrySink`.

    This is the "no transport exists yet" default: even when the gate fully
    permits emission, the payload is discarded rather than sent anywhere --
    there is no HTTP client, no file write, no state mutation to observe.
    """
    settings = Settings(cadrumo_telemetry_opt_in=True, cadrumo_telemetry_tier=TelemetryTier.FULL)
    result = emit_telemetry_event(_payload(), settings=settings, acknowledged=True)
    assert result is True  # the gate permitted it; the noop sink accepted it


def test_local_noop_sink_send_returns_none() -> None:
    sink = LocalNoopTelemetrySink()
    assert sink.send(_payload()) is None
