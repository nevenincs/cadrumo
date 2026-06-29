"""Strict live-test opt-in constants and predicates."""

from __future__ import annotations

LIVE_READ_TEST_OPT_IN_SETTINGS_FIELD = "aeat_live_tests_enabled"
"""Settings field backing the pytest-only live-read opt-in."""
LIVE_READ_TEST_OPT_IN_ENV_VAR = "AEAT_LIVE_TESTS_ENABLED"
"""Environment variable backing ``Settings.aeat_live_tests_enabled``."""
LIVE_READ_TEST_OPT_IN_VALUE = "1"
"""The only literal value that opts in to live tests."""
LIVE_READ_TEST_GOOGLE_OPT_IN_SETTINGS_FIELD = "aeat_live_tests_google"
"""Settings field backing the pytest-only Google live-test opt-in."""
LIVE_READ_TEST_GOOGLE_OPT_IN_ENV_VAR = "AEAT_LIVE_TESTS_GOOGLE"
"""Environment variable backing ``Settings.aeat_live_tests_google``."""


def strict_live_test_opt_in(value: str) -> bool:
    """Return whether ``value`` is the sole accepted live-test opt-in token."""
    return value == LIVE_READ_TEST_OPT_IN_VALUE
