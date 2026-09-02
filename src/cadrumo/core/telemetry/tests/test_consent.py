"""Tests for the remote-telemetry consent gate.

Local telemetry is always on and unaffected by this gate; it governs only the
remote-transmission exception. It must be off by default, re-affirmed per
invocation, refused while the tier is ``off``, and barred absolutely in
gestor deployments (``sensitive-financial-data-secure-storage-only``,
secure-storage telemetry policy).

See Also:
    :func:`~core.telemetry.telemetry_emit_permitted`:
        Four-way consent gate under test.
    :class:`~core.telemetry.TelemetryTier`:
        Closed tier enum consulted by the gate.
    :class:`~core.config.Settings`:
        Deployment posture carrying opt-in, tier, and gestor-mode fields.
    :func:`~core.telemetry.emit_telemetry_event`:
        Dispatcher that applies this gate before any sink receives a payload.
"""

from __future__ import annotations

import pytest

from ...config import Settings
from ..consent import telemetry_emit_permitted
from ..tier import TelemetryTier

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_default_posture_refuses_telemetry_even_when_acknowledged() -> None:
    settings = Settings()
    assert settings.cadrumo_telemetry_opt_in is False
    assert settings.cadrumo_telemetry_gestor_mode is False
    assert settings.cadrumo_telemetry_tier is TelemetryTier.OFF
    assert telemetry_emit_permitted(settings, acknowledged=True) is False


def test_opted_in_deployment_still_requires_a_non_off_tier() -> None:
    settings = Settings(cadrumo_telemetry_opt_in=True, cadrumo_telemetry_tier=TelemetryTier.OFF)
    # Opted in but tier still 'off' -> refused regardless of acknowledgement.
    assert telemetry_emit_permitted(settings, acknowledged=True) is False


def test_opted_in_deployment_still_requires_per_invocation_acknowledgement() -> None:
    settings = Settings(cadrumo_telemetry_opt_in=True, cadrumo_telemetry_tier=TelemetryTier.CRASH_ONLY)
    # Not acknowledged this invocation -> refused (no sticky enable).
    assert telemetry_emit_permitted(settings, acknowledged=False) is False
    # Acknowledged this invocation -> permitted.
    assert telemetry_emit_permitted(settings, acknowledged=True) is True


def test_full_tier_also_requires_opt_in_and_acknowledgement() -> None:
    settings = Settings(cadrumo_telemetry_opt_in=True, cadrumo_telemetry_tier=TelemetryTier.FULL)
    assert telemetry_emit_permitted(settings, acknowledged=True) is True
    assert telemetry_emit_permitted(settings, acknowledged=False) is False


def test_gestor_mode_bars_telemetry_absolutely() -> None:
    settings = Settings(
        cadrumo_telemetry_opt_in=True,
        cadrumo_telemetry_tier=TelemetryTier.FULL,
        cadrumo_telemetry_gestor_mode=True,
    )
    # Gestor mode overrides the deployment opt-in, the tier, and per-invocation consent.
    assert telemetry_emit_permitted(settings, acknowledged=True) is False


def test_acknowledgement_is_never_sticky_across_calls() -> None:
    """Two consecutive calls with the same settings but different acknowledgement
    must diverge -- proving the gate re-reads the flag every time rather than
    caching a prior permit.
    """
    settings = Settings(cadrumo_telemetry_opt_in=True, cadrumo_telemetry_tier=TelemetryTier.CRASH_ONLY)
    first = telemetry_emit_permitted(settings, acknowledged=True)
    second = telemetry_emit_permitted(settings, acknowledged=False)
    assert first is True
    assert second is False
