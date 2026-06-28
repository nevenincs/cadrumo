"""Settings-override seam coverage for the live-read access gate.

Per the settings dependency-injection contract: the migrated access-gate read of
``aeat_live_tests_enabled`` (formerly a direct ``os.environ`` read)
must observe ``override_settings`` ContextVar values without any test
manipulating the actual environment. This file proves that contract.

Real ``AeatAccessGate`` constructed inline from a real
``Settings``-derived state under each override. No mocks.
"""

from __future__ import annotations

import pytest

from ... import config as _config
from ...config import load_settings, override_settings
from .. import AeatAccessGate
from .._errors import AeatLiveReadNotEnabledError, LiveSubmitForbiddenError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _build_gate() -> AeatAccessGate:
    """Construct a gate from the current settings — the production pattern."""
    return AeatAccessGate(settings=load_settings())


def test_override_to_one_unblocks_live_read() -> None:
    """An override of aeat_live_tests_enabled to '1' admits live reads."""
    with override_settings(aeat_live_tests_enabled="1"):
        _build_gate().require_live_read()


def test_operator_context_does_not_require_live_test_opt_in() -> None:
    """Outside pytest, live-read gating continues to operational auth/profile checks."""
    with override_settings(aeat_live_tests_enabled="0"):
        _build_gate().require_live_read(pytest_current_test="")


def test_override_to_zero_blocks_live_read() -> None:
    """During pytest, an override to anything other than '1' raises the typed refusal."""
    with override_settings(aeat_live_tests_enabled="0"), pytest.raises(AeatLiveReadNotEnabledError):
        _build_gate().require_live_read()


def test_loaded_pytest_module_blocks_live_read_when_current_test_env_is_hidden() -> None:
    """Click isolation can hide PYTEST_CURRENT_TEST; loaded pytest still marks test execution."""
    with override_settings(aeat_live_tests_enabled="0"), pytest.raises(AeatLiveReadNotEnabledError):
        assert "pytest" in __import__("sys").modules
        _build_gate().require_live_read(pytest_current_test=None)


def test_override_to_true_string_still_blocks() -> None:
    """The gate is strict on the literal string '1' — 'true' does not pass."""
    with override_settings(aeat_live_tests_enabled="true"), pytest.raises(AeatLiveReadNotEnabledError):
        _build_gate().require_live_read()


def test_override_restoration_after_block_exits() -> None:
    """Leaving the override scope restores the previous-context behaviour."""
    baseline = load_settings().aeat_live_tests_enabled
    with override_settings(aeat_live_tests_enabled="1"):
        pass
    assert load_settings().aeat_live_tests_enabled == baseline


def test_live_write_is_permanently_forbidden_regardless_of_override() -> None:
    """Per AEAT safety-and-legal-gates: live writes are forbidden, no override unlocks them."""
    with override_settings(aeat_live_tests_enabled="1"), pytest.raises(LiveSubmitForbiddenError):
        _build_gate().require_live_write()


def test_snapshot_reflects_overridden_value() -> None:
    """The audit-snapshot helper reads from the same Settings surface as the gate check."""
    with override_settings(aeat_live_tests_enabled="diagnostic-marker"):
        snapshot = _build_gate().snapshot_env(pytest_current_test=None)
    assert snapshot.aeat_live_tests_enabled == "diagnostic-marker"


def test_override_does_not_mutate_os_environ() -> None:
    """The ContextVar seam must not bleed into the actual environment."""
    import os

    sentinel = "settings-di-test-do-not-set-this"
    os.environ.pop("AEAT_LIVE_TESTS_ENABLED", None)
    with override_settings(aeat_live_tests_enabled=sentinel):
        assert os.environ.get("AEAT_LIVE_TESTS_ENABLED") is None
        assert load_settings().aeat_live_tests_enabled == sentinel
    assert os.environ.get("AEAT_LIVE_TESTS_ENABLED") is None


# Defensive re-import to surface a circular-import regression early.
assert _config.override_settings is override_settings
