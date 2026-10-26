"""Which finishing-session exit statuses a session refusal may replace.

Several session-finish hooks turn a run that would otherwise read as complete
into ``USAGE_ERROR``. Only a pass, an ordinary test failure, or an empty
collection is replaceable. Any other status -- an interruption, an internal
error, an existing usage error, or a custom ``pytest.exit`` code -- is already a
more specific verdict and is preserved. Every refusing hook goes through this
one definition, so the order the hooks run in cannot change the final status.
"""

from __future__ import annotations

from typing import Final

import pytest

REPLACEABLE_EXIT_STATUSES: Final[frozenset[pytest.ExitCode]] = frozenset(
    {pytest.ExitCode.OK, pytest.ExitCode.TESTS_FAILED, pytest.ExitCode.NO_TESTS_COLLECTED},
)
"""The session exit statuses a refusal may replace with ``USAGE_ERROR``."""


def refuse_session(session: pytest.Session) -> None:
    """Replace a passing, failing or empty session's exit status with ``USAGE_ERROR``.

    Args:
        session: The finishing session; any other exit status is left untouched.
    """
    if session.exitstatus in REPLACEABLE_EXIT_STATUSES:
        session.exitstatus = pytest.ExitCode.USAGE_ERROR
