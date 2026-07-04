"""Tests for the telemetry-posture fields on :class:`~aeat.core.config.Settings`.

Confirms the default-off posture and that each field reads its documented
environment variable, mirroring the coverage
``aeat_evidence_cloud_upload_permitted`` / ``aeat_evidence_gestor_mode`` carry
for the sibling off-host consent gate.
"""

from __future__ import annotations

import pytest

from ...config import Settings
from .. import TelemetryTier

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_telemetry_settings_default_to_the_fully_inert_posture() -> None:
    settings = Settings()
    assert settings.aeat_telemetry_opt_in is False
    assert settings.aeat_telemetry_tier is TelemetryTier.OFF
    assert settings.aeat_telemetry_gestor_mode is False
    assert settings.aeat_telemetry_endpoint is None


def test_telemetry_opt_in_reads_its_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_TELEMETRY_OPT_IN", "true")
    settings = Settings()
    assert settings.aeat_telemetry_opt_in is True


def test_telemetry_tier_reads_its_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_TELEMETRY_TIER", "full")
    settings = Settings()
    assert settings.aeat_telemetry_tier is TelemetryTier.FULL


def test_telemetry_tier_rejects_an_unrecognised_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_TELEMETRY_TIER", "not-a-real-tier")
    with pytest.raises(Exception):  # noqa: B017 - pydantic-settings raises a bare ValidationError here
        Settings()


def test_telemetry_gestor_mode_reads_its_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_TELEMETRY_GESTOR_MODE", "true")
    settings = Settings()
    assert settings.aeat_telemetry_gestor_mode is True


def test_telemetry_endpoint_reads_its_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_TELEMETRY_ENDPOINT", "https://telemetry.example.org/collect")
    settings = Settings()
    assert settings.aeat_telemetry_endpoint == "https://telemetry.example.org/collect"
