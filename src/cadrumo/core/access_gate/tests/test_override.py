"""Settings-override seam coverage for the live-read access gate.

Per the settings dependency-injection contract: the migrated access-gate read of
``cadrumo_live_tests_enabled`` (formerly a direct ``os.environ`` read)
must observe ``override_settings`` ContextVar values without any test
manipulating the actual environment. This file proves that contract.

Real ``AeatAccessGate`` constructed inline from a real
``Settings``-derived state under each override, without test doubles.
"""

from __future__ import annotations

import pytest

from ... import config as _config
from ...config import load_settings, override_settings
from ..errors import AeatLiveReadNotEnabledError, LiveSubmitForbiddenError
from ..gate import AeatAccessGate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _build_gate() -> AeatAccessGate:
    """Construct a gate from the current settings — the production pattern."""
    return AeatAccessGate(settings=load_settings())


def test_live_read_override_allows_literal_one_or_operator_context() -> None:
    """Live reads are admitted by literal '1' in tests or by non-pytest operator context."""

    for _case_id, enabled, pytest_current_test in (
        ("literal-one", "1", None),
        ("operator-context", "0", ""),
    ):
        with override_settings(cadrumo_live_tests_enabled=enabled):
            _build_gate().require_live_read(pytest_current_test=pytest_current_test)


def test_live_read_override_blocks_non_one_values_during_pytest() -> None:
    """During pytest, an override to anything other than '1' raises the typed refusal."""

    assert "pytest" in __import__("sys").modules
    for case_id, enabled, use_default_current_test in (
        ("zero-current-test", "0", True),
        ("zero-hidden-env", "0", False),
        ("true-string", "true", True),
    ):
        with (
            override_settings(cadrumo_live_tests_enabled=enabled),
            pytest.raises(AeatLiveReadNotEnabledError) as excinfo,
        ):
            if use_default_current_test:
                _build_gate().require_live_read()
            else:
                _build_gate().require_live_read(pytest_current_test=None)
        assert excinfo.type is AeatLiveReadNotEnabledError, case_id


def test_override_restoration_after_block_exits() -> None:
    """Leaving the override scope restores the previous-context behaviour."""
    baseline = load_settings().cadrumo_live_tests_enabled
    with override_settings(cadrumo_live_tests_enabled="1"):
        pass
    assert load_settings().cadrumo_live_tests_enabled == baseline


def test_live_write_is_permanently_forbidden_regardless_of_override() -> None:
    """Per AEAT safety-and-legal-gates: live writes are forbidden, no override unlocks them."""
    with override_settings(cadrumo_live_tests_enabled="1"), pytest.raises(LiveSubmitForbiddenError):
        _build_gate().require_live_write()


def test_snapshot_reflects_overridden_value() -> None:
    """The audit-snapshot helper reads from the same Settings surface as the gate check."""
    with override_settings(cadrumo_live_tests_enabled="diagnostic-marker"):
        snapshot = _build_gate().snapshot_env(pytest_current_test=None)
    assert snapshot.cadrumo_live_tests_enabled == "diagnostic-marker"


def test_override_does_not_mutate_os_environ() -> None:
    """The ContextVar seam must not bleed into the actual environment."""
    import os

    sentinel = "settings-di-test-do-not-set-this"
    previous = os.environ.pop("CADRUMO_LIVE_TESTS_ENABLED", None)
    try:
        with override_settings(cadrumo_live_tests_enabled=sentinel):
            assert os.environ.get("CADRUMO_LIVE_TESTS_ENABLED") is None
            assert load_settings().cadrumo_live_tests_enabled == sentinel
        assert os.environ.get("CADRUMO_LIVE_TESTS_ENABLED") is None
    finally:
        if previous is not None:
            os.environ["CADRUMO_LIVE_TESTS_ENABLED"] = previous


# Defensive re-import to surface a circular-import regression early.
assert _config.override_settings is override_settings
