"""Cross-platform PID-liveness probe shared by the crash-recoverable locks.

Both the bucket lockfile
(:mod:`adapters.persistence.storage.bucket`) and the auth-acquisition lock
(:mod:`application.auth`) reclaim a stale lock by asking the OS whether the
recorded holder PID is still a live process. This module is the single home
for that probe so the two lock subsystems cannot diverge on Windows
failure-mode handling: a probe failure other than "PID does not exist" MUST
be treated as alive, never as grounds to reclaim a lock this process cannot
actually inspect.
"""

from __future__ import annotations

import os
import sys

from .logging import get_logger

_log = get_logger(__name__)


def pid_is_alive(pid: int) -> bool:
    """Return whether ``pid`` is a live process, per a best-effort OS probe.

    Returns ``True`` when the OS reports ``pid`` as a live process and
    ``False`` when the OS reports it as gone (or ``pid`` is not a valid
    process id). A permission error probing the PID (it exists but belongs
    to another user, or this process lacks the query right) is treated as
    alive: from the caller's perspective a lock held by that PID cannot be
    safely reclaimed.

    On Windows the probe distinguishes ``ERROR_INVALID_PARAMETER`` (87,
    returned by ``OpenProcess`` for a PID that no longer exists) from every
    other ``OpenProcess`` failure (access-denied against a foreign or
    protected process, a PID recycled onto a process this call cannot
    query, etc.). Only the former is treated as dead; every other failure
    is treated as alive so a lock is never wrongly reclaimed just because
    this process could not inspect its holder.
    """
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _pid_is_alive_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        _log.debug("pid liveness probe denied for pid=%s; treating as alive", pid)
        return True
    return True


def _pid_is_alive_windows(pid: int) -> bool:
    """Windows ``OpenProcess`` + ``GetExitCodeProcess`` liveness probe.

    ``os.kill(pid, 0)`` on Windows reports terminated-but-cached PIDs as
    alive until the kernel reclaims the PID, so the probe goes through
    ``OpenProcess`` + ``GetExitCodeProcess`` instead: a process whose exit
    code is not ``STILL_ACTIVE`` (259) is dead even if its PID is still
    allocated.
    """
    if sys.platform != "win32":  # pragma: no cover - dispatch never routes here
        # Narrowed on sys.platform rather than os.name: the ctypes Windows API
        # below does not exist in the POSIX stubs, so a checker running on Linux
        # reports every reference unresolved unless the platform is established.
        raise RuntimeError("the Windows liveness probe is not available on this platform")

    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    still_active = 259
    error_invalid_parameter = 87
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        last_error = ctypes.get_last_error()
        missing = last_error == error_invalid_parameter
        if not missing:
            _log.debug(
                "pid liveness probe unavailable for pid=%s (last_error=%s); treating as alive",
                pid,
                last_error,
            )
        return not missing
    try:
        code = wintypes.DWORD()
        ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        if not ok:
            return True
        return code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


__all__ = ["pid_is_alive"]
