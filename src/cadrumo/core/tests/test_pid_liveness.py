"""Real-behaviour coverage for the shared PID-liveness probe.

Exercises the branches reachable without patching a syscall: the ``pid <= 0``
guard, the current (self) process, and a genuinely-terminated child process
(real OS state, no mocks, no monkeypatches). The Windows
access-denied-but-alive failure mode this probe exists to classify correctly
-- an ``OpenProcess`` failure for a reason other than "PID does not exist"
must be treated as alive -- cannot be constructed deterministically without a
genuinely inaccessible target process (a foreign-user or protected process),
which is not available in this test environment; it is therefore NOT
exercised for real here. Instead, :func:`test_bucket_lockfile_and_acquisition_lock_share_one_probe`
locks the structural fix: both former call sites now resolve to the exact
same function object, so a re-introduced duplicate (which is exactly how the
divergence happened) fails this test immediately.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from ..pid_liveness import pid_is_alive
from ..pid_liveness import pid_is_alive as _canonical_pid_is_alive

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_pid_is_alive_rejects_non_positive_pid() -> None:
    assert pid_is_alive(0) is False
    assert pid_is_alive(-1) is False


def test_pid_is_alive_reports_current_process_alive() -> None:
    assert pid_is_alive(os.getpid()) is True


def test_pid_is_alive_reports_genuinely_terminated_child_as_dead() -> None:
    """A real spawned-then-exited child PID must classify as dead.

    On POSIX this exercises ``os.kill(pid, 0)`` -> ``ProcessLookupError``
    once the child is reaped. On Windows this exercises the real
    ``OpenProcess`` + ``GetExitCodeProcess`` path against a process that has
    genuinely exited: ``GetExitCodeProcess`` reports its real (non
    ``STILL_ACTIVE``) exit code even though this test process still held
    (and released via ``wait``) its own handle, which is exactly the
    production code path the fix hardens.
    """
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    pid = proc.pid
    proc.wait(timeout=10)
    assert pid_is_alive(pid) is False


def test_bucket_lockfile_and_acquisition_lock_share_one_probe() -> None:
    """The two lock subsystems must resolve to the identical shared probe.

    Before the fix each module carried its own private
    ``_pid_is_alive`` / ``_pid_is_running_windows`` implementation, and the
    two disagreed on the Windows failure mode. This assertion fails again
    the moment either module re-grows a private duplicate, even if that
    duplicate happens to behave identically at first.
    """
    from ...adapters.persistence.storage.bucket import _lockfile
    from ...application.auth import acquisition_lock as acquisition_lock

    assert not hasattr(_lockfile, "_pid_is_alive")
    assert not hasattr(acquisition_lock, "_pid_is_running_windows")
    assert _lockfile.pid_is_alive is pid_is_alive
    assert acquisition_lock.pid_is_alive is pid_is_alive
    assert pid_is_alive is _canonical_pid_is_alive
