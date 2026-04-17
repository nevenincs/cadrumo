"""Unit tests for :mod:`aeat.auth._gate`."""

from __future__ import annotations

import pytest

from aeat.auth import (
    AeatAccessGate,
    AeatGateEnvSnapshot,
    AeatLiveReadNotEnabledError,
)
from aeat.config import Settings
from aeat.submission import (
    AeatLiveSubmitNotEnabledError,
    AeatPytestLiveWriteRefusedError,
)


def _fresh_settings(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Settings:
    """Return a :class:`Settings` instance with per-test env isolation."""
    monkeypatch.delenv("AEAT_LIVE_TESTS_ENABLED", raising=False)
    monkeypatch.delenv("AEAT_LIVE_SUBMIT_ENABLED", raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    return Settings()


@pytest.mark.unit
def test_snapshot_env_reports_present_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_LIVE_TESTS_ENABLED", "1")
    monkeypatch.setenv("AEAT_LIVE_SUBMIT_ENABLED", "true")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    settings = _fresh_settings(
        monkeypatch,
        AEAT_LIVE_TESTS_ENABLED="1",
        AEAT_LIVE_SUBMIT_ENABLED="true",
    )
    snapshot = AeatAccessGate(settings).snapshot_env()
    assert isinstance(snapshot, AeatGateEnvSnapshot)
    assert snapshot.aeat_live_tests_enabled == "1"
    assert snapshot.aeat_live_submit_enabled == "true"
    assert snapshot.pytest_current_test == ""


@pytest.mark.unit
def test_snapshot_env_reports_absent_vars_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEAT_LIVE_TESTS_ENABLED", raising=False)
    monkeypatch.delenv("AEAT_LIVE_SUBMIT_ENABLED", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    settings = _fresh_settings(monkeypatch)
    snapshot = AeatAccessGate(settings).snapshot_env()
    assert snapshot.aeat_live_tests_enabled == ""
    assert snapshot.aeat_live_submit_enabled == ""
    assert snapshot.pytest_current_test == ""


@pytest.mark.unit
def test_snapshot_as_audit_dict_matches_engine_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_LIVE_TESTS_ENABLED", "1")
    monkeypatch.setenv("AEAT_LIVE_SUBMIT_ENABLED", "false")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    settings = _fresh_settings(
        monkeypatch,
        AEAT_LIVE_TESTS_ENABLED="1",
        AEAT_LIVE_SUBMIT_ENABLED="false",
    )
    snapshot = AeatAccessGate(settings).snapshot_env()
    assert snapshot.as_audit_dict() == {
        "AEAT_LIVE_TESTS_ENABLED": "1",
        "AEAT_LIVE_SUBMIT_ENABLED": "false",
        "PYTEST_CURRENT_TEST": "",
    }


@pytest.mark.unit
def test_require_live_read_passes_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_LIVE_TESTS_ENABLED", "1")
    settings = _fresh_settings(monkeypatch, AEAT_LIVE_TESTS_ENABLED="1")
    # Should not raise.
    AeatAccessGate(settings).require_live_read()


@pytest.mark.unit
def test_require_live_read_raises_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEAT_LIVE_TESTS_ENABLED", raising=False)
    settings = _fresh_settings(monkeypatch)
    with pytest.raises(AeatLiveReadNotEnabledError):
        AeatAccessGate(settings).require_live_read()


@pytest.mark.unit
def test_require_live_read_raises_when_not_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_LIVE_TESTS_ENABLED", "true")
    settings = _fresh_settings(monkeypatch, AEAT_LIVE_TESTS_ENABLED="true")
    with pytest.raises(AeatLiveReadNotEnabledError):
        AeatAccessGate(settings).require_live_read()


@pytest.mark.unit
def test_require_live_write_raises_without_submit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEAT_LIVE_SUBMIT_ENABLED", raising=False)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "placeholder")  # would trigger the other check
    settings = _fresh_settings(monkeypatch)
    with pytest.raises(AeatLiveSubmitNotEnabledError):
        AeatAccessGate(settings).require_live_write()


@pytest.mark.unit
def test_require_live_write_raises_under_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEAT_LIVE_SUBMIT_ENABLED", "true")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "placeholder")
    settings = _fresh_settings(monkeypatch, AEAT_LIVE_SUBMIT_ENABLED="true")
    with pytest.raises(AeatPytestLiveWriteRefusedError):
        AeatAccessGate(settings).require_live_write()


@pytest.mark.unit
def test_access_gate_is_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _fresh_settings(monkeypatch)
    gate = AeatAccessGate(settings)
    # Frozen dataclass rejects in-place mutation of declared fields.
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        gate.__setattr__("settings", settings)
