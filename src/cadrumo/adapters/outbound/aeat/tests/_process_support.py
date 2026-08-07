"""Wait for a real OS process to exit, shared across the AEAT adapter tests.

Four copies of this loop had accumulated across two sibling test packages --
``auth/tests/test_browser_lifecycle.py``, ``auth/tests/test_authenticator_real_boundary.py``,
``browser/tests/test_factory.py``, and ``browser/tests/test_async_cleanup_real.py`` --
identical but for the message each failed with. All four assert the same
thing: that a Playwright driver process reached an OS-terminal state within a
bounded wait, rather than being merely detached or leaked. The message is the
only part that is genuinely per-caller, so it is the only parameter.

Deliberately preserves ``psutil.pid_exists`` rather than switching to the
canonical :func:`~core.pid_is_alive`. That helper exists and would be the
better probe on Windows -- it distinguishes a terminated-but-cached PID from a
live one through ``OpenProcess``/``GetExitCodeProcess``, which a PID-existence
check cannot -- but swapping it here changes what these live browser tests
observe, and that is a behaviour decision rather than part of collapsing four
copies into one. Raised separately; this module deliberately changes nothing
about the probe.
"""

from __future__ import annotations

import asyncio
import time

import psutil
import pytest

#: Bound shared by every caller. Generous: these tests race a real Playwright
#: driver teardown, so the wait must survive a slow machine without flaking,
#: while still failing rather than hanging when a process genuinely leaks.
DEFAULT_PROCESS_EXIT_TIMEOUT_SECONDS = 10.0

#: Poll interval. Short enough that a fast teardown is not charged the full
#: interval, long enough not to spin the event loop against the OS.
_POLL_INTERVAL_SECONDS = 0.1


async def wait_for_process_exit(
    pid: int,
    *,
    after: str,
    timeout_seconds: float = DEFAULT_PROCESS_EXIT_TIMEOUT_SECONDS,
) -> None:
    """Fail unless ``pid`` leaves the process table within ``timeout_seconds``.

    Args:
        pid: The process id expected to terminate.
        after: What the caller just did, phrased to complete "remained alive
            after ..." -- e.g. ``"session close"``. Carrying it keeps each
            call site's failure as specific as its own copy was.
        timeout_seconds: Bound on the wait.

    Raises:
        Failed: Via :func:`pytest.fail`, when the process is still present at
            the deadline. A leaked driver process is the defect these tests
            exist to catch, so this fails rather than returning a flag no
            caller would be obliged to check.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not psutil.pid_exists(pid):
            return
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
    pytest.fail(f"Playwright driver process {pid} remained alive after {after}")


__all__ = ["DEFAULT_PROCESS_EXIT_TIMEOUT_SECONDS", "wait_for_process_exit"]
