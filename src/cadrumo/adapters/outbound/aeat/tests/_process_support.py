"""Wait for a real OS process to exit, shared across the AEAT adapter tests.

Four copies of this loop had accumulated across two sibling test packages --
``auth/tests/test_browser_lifecycle.py``, ``auth/tests/test_authenticator_real_boundary.py``,
``browser/tests/test_factory.py``, and ``browser/tests/test_async_cleanup_real.py`` --
identical but for the message each failed with. All four assert the same
thing: that a Playwright driver process reached an OS-terminal state within a
bounded wait, rather than being merely detached or leaked. The message is the
only part that is genuinely per-caller, so it is the only parameter.

Probes with the canonical :func:`~core.pid_is_alive` rather than
``psutil.pid_exists``. The distinction is not academic on the platform these
tests run on: a PID-existence check reports a terminated-but-cached PID as
still present until Windows reclaims the PID, while ``pid_is_alive`` asks
``OpenProcess``/``GetExitCodeProcess`` whether the process actually exited.
That is the exact case this loop is built around -- a driver that has
terminated but whose PID the kernel has not yet released.

The failure it removes is a false NEGATIVE, which is the expensive direction.
A probe that keeps reporting a dead driver as alive does not let a leak
through; it spins to the deadline and fails, so the symptom is an
intermittently failing lifecycle test rather than a missed defect. Those get
re-run, then marked slow, then weakened -- and the wall that was supposed to
catch a genuinely leaked process is gone by attrition rather than by decision.
Asking the kernel whether the process exited makes the wait terminate for the
reason it is testing.

``pid_is_alive`` treats an unreadable probe (permission denied, a PID this
process cannot query) as ALIVE. That bias was chosen for lock reclamation,
where assuming alive is the safe error, and it is also the safe error here: an
unreadable PID fails this wait rather than passing it, so the helper still
cannot green a leak it could not see.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from .....core.pid_liveness import pid_is_alive

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
        if not pid_is_alive(pid):
            return
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
    pytest.fail(f"Playwright driver process {pid} remained alive after {after}")


__all__ = ["DEFAULT_PROCESS_EXIT_TIMEOUT_SECONDS", "wait_for_process_exit"]
