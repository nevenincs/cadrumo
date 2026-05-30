"""Unit tests for the canonical live-access gate exported by AEAT auth."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from .....core.access_gate import _PYTEST_CURRENT_TEST_ENV
from .....core.config import Settings, override_settings
from ..export import LiveSubmitForbiddenError
from . import (
    AeatAccessGate,
    AeatGateEnvSnapshot,
    AeatLiveReadNotEnabledError,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


@contextmanager
def _pytest_current_test(value: str | None) -> Iterator[None]:
    """Pin ``os.environ[PYTEST_CURRENT_TEST]`` for the with-block.

    ``PYTEST_CURRENT_TEST`` is pytest infrastructure, set by the runner
    itself; the gate reads it directly from ``os.environ`` as the only
    documented exception to the Settings single-source-of-truth rule.
    Testing the present/absent branches requires manipulating that env
    var, so this helper saves the prior value and restores it on exit
    — equivalent to ``monkeypatch.setenv``/``delenv`` but without the
    fixture indirection retired by the project no-monkeypatch mandate
    (CLAUDE.md).
    """
    prior = os.environ.get(_PYTEST_CURRENT_TEST_ENV)
    if value is None:
        os.environ.pop(_PYTEST_CURRENT_TEST_ENV, None)
    else:
        os.environ[_PYTEST_CURRENT_TEST_ENV] = value
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop(_PYTEST_CURRENT_TEST_ENV, None)
        else:
            os.environ[_PYTEST_CURRENT_TEST_ENV] = prior


def test_snapshot_env_reports_present_values() -> None:
    with override_settings(aeat_live_tests_enabled="1"), _pytest_current_test(None):
        settings = Settings(aeat_live_tests_enabled="1")
        snapshot = AeatAccessGate(settings).snapshot_env()
        assert isinstance(snapshot, AeatGateEnvSnapshot)
        assert snapshot.aeat_live_tests_enabled == "1"
        assert snapshot.pytest_current_test == ""


def test_snapshot_env_reflects_settings_field_value() -> None:
    # snapshot_env reports ``settings.aeat_live_tests_enabled`` (Settings
    # surface) and ``os.environ[PYTEST_CURRENT_TEST]`` (pytest
    # infrastructure only — not AEAT config, no Settings mirror).
    with override_settings(aeat_live_tests_enabled=""), _pytest_current_test(None):
        settings = Settings(aeat_live_tests_enabled="")
        snapshot = AeatAccessGate(settings).snapshot_env()
        assert snapshot.aeat_live_tests_enabled == settings.aeat_live_tests_enabled
        assert snapshot.pytest_current_test == ""


def test_snapshot_as_audit_dict_matches_engine_schema() -> None:
    with override_settings(aeat_live_tests_enabled="1"), _pytest_current_test(None):
        settings = Settings(aeat_live_tests_enabled="1")
        snapshot = AeatAccessGate(settings).snapshot_env()
        assert snapshot.as_audit_dict() == {
            "AEAT_LIVE_TESTS_ENABLED": "1",
            "PYTEST_CURRENT_TEST": "",
        }


def test_require_live_read_passes_when_enabled() -> None:
    with override_settings(aeat_live_tests_enabled="1"):
        settings = Settings(aeat_live_tests_enabled="1")
        assert settings.aeat_live_tests_enabled
        result = AeatAccessGate(settings).require_live_read()
        assert result is None


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
    with _pytest_current_test("placeholder"):
        settings = Settings()
        with pytest.raises(LiveSubmitForbiddenError, match="permanently forbidden"):
            AeatAccessGate(settings).require_live_write()


def test_access_gate_is_frozen() -> None:
    settings = Settings()
    gate = AeatAccessGate(settings)
    # Frozen dataclass rejects in-place mutation of declared fields.
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError, match=r"settings"):
        gate.__setattr__("settings", settings)
