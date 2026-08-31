"""Tests for the telemetry-posture fields on :class:`~core.config.Settings`.

Confirms the default-off posture and that each field reads its documented
environment variable, mirroring the coverage
the retired evidence cloud-upload and gestor-mode flags carried
for the sibling off-host consent gate.

See Also:
    :class:`~core.telemetry.TelemetryTier`:
        Closed tier enum parsed from ``CADRUMO_TELEMETRY_TIER``.
    :func:`~core.telemetry.telemetry_emit_permitted`:
        Consent gate that consumes the settings fields under test.
    :func:`~application.diagnostics_telemetry.build_telemetry_status_report`:
        Read-only application projection of the configured telemetry posture.
    :mod:`~entrypoints.cli._app_diagnostics_telemetry`:
        CLI surface that previews and overrides these fields per invocation.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....tests.env_scope import isolated_aeat_env, settings_without_env_file
from ...config import Settings
from ..tier import TelemetryTier

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _settings_from_env(**env: str) -> Settings:
    with isolated_aeat_env(**env):
        return settings_without_env_file()


def test_telemetry_settings_default_to_the_fully_inert_posture() -> None:
    settings = _settings_from_env()
    assert settings.cadrumo_telemetry_opt_in is False
    assert settings.cadrumo_telemetry_tier is TelemetryTier.OFF
    assert settings.cadrumo_telemetry_gestor_mode is False
    assert settings.cadrumo_telemetry_endpoint is None


def test_telemetry_opt_in_reads_its_env_var() -> None:
    settings = _settings_from_env(CADRUMO_TELEMETRY_OPT_IN="true")
    assert settings.cadrumo_telemetry_opt_in is True


def test_telemetry_tier_reads_its_env_var() -> None:
    settings = _settings_from_env(CADRUMO_TELEMETRY_TIER="full")
    assert settings.cadrumo_telemetry_tier is TelemetryTier.FULL


def test_telemetry_tier_rejects_an_unrecognised_value() -> None:
    with pytest.raises(ValidationError):
        _settings_from_env(CADRUMO_TELEMETRY_TIER="not-a-real-tier")


def test_telemetry_gestor_mode_reads_its_env_var() -> None:
    settings = _settings_from_env(CADRUMO_TELEMETRY_GESTOR_MODE="true")
    assert settings.cadrumo_telemetry_gestor_mode is True


def test_telemetry_endpoint_reads_its_env_var() -> None:
    settings = _settings_from_env(CADRUMO_TELEMETRY_ENDPOINT="https://telemetry.example.org/collect")
    assert settings.cadrumo_telemetry_endpoint == "https://telemetry.example.org/collect"
