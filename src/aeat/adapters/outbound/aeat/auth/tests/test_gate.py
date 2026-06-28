"""Unit tests for the canonical live-access gate exported by AEAT auth."""

from __future__ import annotations

import pytest

from ......core.access_gate import AeatLiveReadNotEnabledError, LiveSubmitForbiddenError
from ......core.config import Settings, override_settings
from ......core.errors import render_error_text
from .. import (
    AeatAccessGate,
    AeatGateEnvSnapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_snapshot_env_reports_present_values() -> None:
    with override_settings(aeat_live_tests_enabled="1"):
        settings = Settings(aeat_live_tests_enabled="1")
        snapshot = AeatAccessGate(settings).snapshot_env(pytest_current_test="")
        assert isinstance(snapshot, AeatGateEnvSnapshot)
        assert snapshot.aeat_live_tests_enabled == "1"
        assert snapshot.pytest_current_test == ""


def test_snapshot_env_reflects_settings_field_value() -> None:
    # snapshot_env reports ``settings.aeat_live_tests_enabled`` (Settings
    # surface) and ``os.environ[PYTEST_CURRENT_TEST]`` (pytest
    # infrastructure only — not AEAT config, no Settings mirror). Tests
    # pass an explicit value via the snapshot_env DI seam rather than
    # mutating the real env var.
    with override_settings(aeat_live_tests_enabled=""):
        settings = Settings(aeat_live_tests_enabled="")
        snapshot = AeatAccessGate(settings).snapshot_env(pytest_current_test="")
        assert snapshot.aeat_live_tests_enabled == settings.aeat_live_tests_enabled
        assert snapshot.pytest_current_test == ""


def test_require_live_read_passes_when_enabled() -> None:
    with override_settings(aeat_live_tests_enabled="1"):
        settings = Settings(aeat_live_tests_enabled="1")
        assert settings.aeat_live_tests_enabled
        result = AeatAccessGate(settings).require_live_read()
        assert result is None


def test_require_live_read_allows_operator_context_without_test_opt_in() -> None:
    with override_settings(aeat_live_tests_enabled=""):
        settings = Settings(aeat_live_tests_enabled="")
        result = AeatAccessGate(settings).require_live_read(pytest_current_test="")
        assert result is None


def test_require_live_read_still_blocks_pytest_context_without_test_opt_in() -> None:
    with override_settings(aeat_live_tests_enabled=""):
        settings = Settings(aeat_live_tests_enabled="")
        with pytest.raises(AeatLiveReadNotEnabledError, match=r"AEAT_LIVE_TESTS_ENABLED|pytest live"):
            AeatAccessGate(settings).require_live_read(pytest_current_test="test_gate.py::case (call)")


def test_require_live_read_raises_when_unset() -> None:
    with override_settings(aeat_live_tests_enabled=""):
        settings = Settings(aeat_live_tests_enabled="")
        with pytest.raises(AeatLiveReadNotEnabledError, match=r"AEAT_LIVE_TESTS_ENABLED|live"):
            AeatAccessGate(settings).require_live_read()


def test_require_live_read_raises_when_not_one() -> None:
    with override_settings(aeat_live_tests_enabled="true"):
        settings = Settings(aeat_live_tests_enabled="true")
        with pytest.raises(AeatLiveReadNotEnabledError, match=r"AEAT_LIVE_TESTS_ENABLED|live"):
            AeatAccessGate(settings).require_live_read()


def test_require_live_read_refusal_states_only_literal_one_is_accepted() -> None:
    """The refusal for a truthy spelling names the literal accepted value.

    The gate intentionally accepts only the exact string ``1`` — bool
    coercion would widen the safety surface. When an operator supplies
    a near-miss like ``true`` the refusal must say so unambiguously,
    naming both the required literal and the rejected spellings, so the
    operator does not assume ``true`` enabled the gate.
    """
    with override_settings(aeat_live_tests_enabled="true"):
        settings = Settings(aeat_live_tests_enabled="true")
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


def test_require_live_write_always_raises_permanent_refusal() -> None:
    """``require_live_write`` is unconditional — no env / Settings read."""
    settings = Settings()
    with pytest.raises(LiveSubmitForbiddenError, match="permanently forbidden"):
        AeatAccessGate(settings).require_live_write()


def test_live_write_refusal_uses_central_error_registry_translation() -> None:
    """The refusal renders through the registered error-code message key."""
    error = LiveSubmitForbiddenError()

    with override_settings(aeat_output_language="en"):
        rendered = render_error_text(error)

    assert error.translated_message == "errors.locked.locked_access_gate_live_submit_forbidden"
    assert "Live submission to the AEAT is permanently forbidden" in rendered


def test_access_gate_is_frozen() -> None:
    settings = Settings()
    gate = AeatAccessGate(settings)
    # Frozen dataclass rejects in-place mutation of declared fields.
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError, match=r"settings"):
        gate.__setattr__("settings", settings)
