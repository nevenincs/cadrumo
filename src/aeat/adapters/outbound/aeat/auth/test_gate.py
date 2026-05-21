"""Unit tests for the canonical live-access gate exported by AEAT auth."""

from __future__ import annotations

import pytest

from .....core.config import Settings
from ..export import LiveSubmitForbiddenError
from . import (
    AeatAccessGate,
    AeatGateEnvSnapshot,
    AeatLiveReadNotEnabledError,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def _fresh_settings(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Settings:
    """Return a :class:`Settings` instance with per-test env isolation."""
    monkeypatch.delenv("AEAT_LIVE_TESTS_ENABLED", raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    return Settings()


def test_snapshot_env_reports_present_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_LIVE_TESTS_ENABLED", "1")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    settings = _fresh_settings(
        monkeypatch,
        AEAT_LIVE_TESTS_ENABLED="1",
    )
    snapshot = AeatAccessGate(settings).snapshot_env()
    assert isinstance(snapshot, AeatGateEnvSnapshot)
    assert snapshot.aeat_live_tests_enabled == "1"
    assert snapshot.pytest_current_test == ""


def test_snapshot_env_reflects_settings_field_value(monkeypatch: pytest.MonkeyPatch) -> None:
    # snapshot_env reports `settings.aeat_live_tests_enabled` (Settings
    # surface) and `os.environ[PYTEST_CURRENT_TEST]` (pytest infrastructure
    # only — not AEAT config, no Settings mirror). Settings sources both
    # os.environ AND env/.env, so the snapshot captures whichever wins
    # under Pydantic-settings precedence, not the raw shell state.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    settings = _fresh_settings(monkeypatch)
    snapshot = AeatAccessGate(settings).snapshot_env()
    assert snapshot.aeat_live_tests_enabled == settings.aeat_live_tests_enabled
    assert snapshot.pytest_current_test == ""


def test_snapshot_as_audit_dict_matches_engine_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_LIVE_TESTS_ENABLED", "1")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    settings = _fresh_settings(
        monkeypatch,
        AEAT_LIVE_TESTS_ENABLED="1",
    )
    snapshot = AeatAccessGate(settings).snapshot_env()
    assert snapshot.as_audit_dict() == {
        "AEAT_LIVE_TESTS_ENABLED": "1",
        "PYTEST_CURRENT_TEST": "",
    }


def test_require_live_read_passes_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_LIVE_TESTS_ENABLED", "1")
    settings = _fresh_settings(monkeypatch, AEAT_LIVE_TESTS_ENABLED="1")
    assert settings.aeat_live_tests_enabled
    result = AeatAccessGate(settings).require_live_read()
    assert result is None


def test_require_live_read_raises_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEAT_LIVE_TESTS_ENABLED", raising=False)
    settings = _fresh_settings(monkeypatch)
    with pytest.raises(AeatLiveReadNotEnabledError, match=r"AEAT_LIVE_TESTS_ENABLED|live"):
        AeatAccessGate(settings).require_live_read()


def test_require_live_read_raises_when_not_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_LIVE_TESTS_ENABLED", "true")
    settings = _fresh_settings(monkeypatch, AEAT_LIVE_TESTS_ENABLED="true")
    with pytest.raises(AeatLiveReadNotEnabledError, match=r"AEAT_LIVE_TESTS_ENABLED|live"):
        AeatAccessGate(settings).require_live_read()


def test_require_live_read_refusal_states_only_literal_one_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal for a truthy spelling names the literal accepted value.

    The gate intentionally accepts only the exact string ``1`` — bool
    coercion would widen the safety surface. When an operator supplies
    a near-miss like ``true`` the refusal must say so unambiguously,
    naming both the required literal and the rejected spellings, so the
    operator does not assume ``true`` enabled the gate.
    """

    monkeypatch.setenv("AEAT_LIVE_TESTS_ENABLED", "true")
    settings = _fresh_settings(monkeypatch, AEAT_LIVE_TESTS_ENABLED="true")
    with pytest.raises(AeatLiveReadNotEnabledError) as excinfo:
        AeatAccessGate(settings).require_live_read()
    message = str(excinfo.value)
    # The refusal names the literal accepted value.
    assert "literal" in message and "1" in message
    # It explicitly names the rejected near-miss spelling so the
    # operator sees why `true` did not work.
    assert "'true'" in message
    # It echoes the current value for traceability.
    assert repr("true") in message


def test_require_live_write_always_raises_permanent_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "placeholder")
    settings = _fresh_settings(monkeypatch)
    with pytest.raises(LiveSubmitForbiddenError, match="permanently forbidden"):
        AeatAccessGate(settings).require_live_write()


def test_access_gate_is_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _fresh_settings(monkeypatch)
    gate = AeatAccessGate(settings)
    # Frozen dataclass rejects in-place mutation of declared fields.
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError, match=r"settings"):
        gate.__setattr__("settings", settings)
