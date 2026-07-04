"""Tests for the telemetry-posture fields on :class:`~aeat.core.config.Settings`.

Confirms the default-off posture and that each field reads its documented
environment variable, mirroring the coverage
``aeat_evidence_cloud_upload_permitted`` / ``aeat_evidence_gestor_mode`` carry
for the sibling off-host consent gate.
"""

from __future__ import annotations

import pytest

from ....tests.env_scope import isolated_aeat_env
from ...config import Settings
from .. import TelemetryTier

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _settings_from_env(**env: str) -> Settings:
    with isolated_aeat_env(**env):
        return Settings(_env_file=None)


def test_telemetry_settings_default_to_the_fully_inert_posture() -> None:
    settings = _settings_from_env()
    assert settings.aeat_telemetry_opt_in is False
    assert settings.aeat_telemetry_tier is TelemetryTier.OFF
    assert settings.aeat_telemetry_gestor_mode is False
    assert settings.aeat_telemetry_endpoint is None


def test_telemetry_opt_in_reads_its_env_var() -> None:
    settings = _settings_from_env(AEAT_TELEMETRY_OPT_IN="true")
    assert settings.aeat_telemetry_opt_in is True


def test_telemetry_tier_reads_its_env_var() -> None:
    settings = _settings_from_env(AEAT_TELEMETRY_TIER="full")
    assert settings.aeat_telemetry_tier is TelemetryTier.FULL


def test_telemetry_tier_rejects_an_unrecognised_value() -> None:
    with pytest.raises(Exception):  # noqa: B017 - pydantic-settings raises a bare ValidationError here
        _settings_from_env(AEAT_TELEMETRY_TIER="not-a-real-tier")


def test_telemetry_gestor_mode_reads_its_env_var() -> None:
    settings = _settings_from_env(AEAT_TELEMETRY_GESTOR_MODE="true")
    assert settings.aeat_telemetry_gestor_mode is True


def test_telemetry_endpoint_reads_its_env_var() -> None:
    settings = _settings_from_env(AEAT_TELEMETRY_ENDPOINT="https://telemetry.example.org/collect")
    assert settings.aeat_telemetry_endpoint == "https://telemetry.example.org/collect"
