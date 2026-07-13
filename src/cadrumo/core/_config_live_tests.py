"""Strict live-test opt-in constants and predicates.

This module centralises the pytest-only live-read flags consumed by
:class:`~core.config.Settings`, re-exported by :mod:`core.config`,
and enforced by :meth:`~core.access_gate.AeatAccessGate.require_live_read`.
The same predicate backs the generic test helper in :mod:`aeat-tests.live_gate`,
so ordinary live tests, Google live tests, and access-gate diagnostics all
agree that the only opt-in token is the literal string ``"1"``.
"""

from __future__ import annotations

LIVE_READ_TEST_OPT_IN_SETTINGS_FIELD = "cadrumo_live_tests_enabled"
"""Settings field backing the pytest-only live-read opt-in on :class:`~core.config.Settings`."""
LIVE_READ_TEST_OPT_IN_ENV_VAR = "CADRUMO_LIVE_TESTS_ENABLED"
"""Environment variable backing ``Settings.cadrumo_live_tests_enabled``."""
LIVE_READ_TEST_OPT_IN_VALUE = "1"
"""The only literal value that opts in to live tests."""
LIVE_READ_TEST_GOOGLE_OPT_IN_SETTINGS_FIELD = "cadrumo_live_tests_google"
"""Settings field backing the pytest-only Google live-test opt-in on :class:`~core.config.Settings`."""
LIVE_READ_TEST_GOOGLE_OPT_IN_ENV_VAR = "CADRUMO_LIVE_TESTS_GOOGLE"
"""Environment variable backing ``Settings.cadrumo_live_tests_google``."""


def strict_live_test_opt_in(value: str) -> bool:
    """Return whether ``value`` is the sole accepted live-test opt-in token.

    :class:`~core.config.Settings` uses this for both
    ``live_tests_enabled`` and ``live_tests_google_enabled`` so neither field
    accepts truthy alternatives such as ``"true"``, ``"yes"``, or ``"on"``.
    """
    return value == LIVE_READ_TEST_OPT_IN_VALUE
