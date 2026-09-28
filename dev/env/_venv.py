"""Guard the project environment while ``uv sync`` converges it."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from dev._paths import REPO_ROOT

if TYPE_CHECKING:
    from collections.abc import Iterator

#: The virtualenv this repository provisions and installs into.
VENV = REPO_ROOT / ".venv"


def _lock_name(venv: Path) -> str:
    """Derive a stable, venv-scoped lock name.

    Hashing the resolved path is what scopes the lock to ONE environment: two
    worktrees on the same machine install concurrently, and a machine-wide lock
    would serialise them for no reason.

    Args:
        venv: The virtualenv root.

    Returns:
        The lock file's name.
    """
    resolved = str(venv.resolve()).rstrip("\\/").encode("utf-8")
    return f"cadrumo-install-{hashlib.sha256(resolved).hexdigest()[:32]}.lock"


#: How long an empty lock may exist before its writer is presumed dead. The
#: owner writes its PID immediately after the exclusive create, so a live
#: install leaves it empty for microseconds, never seconds.
_EMPTY_LOCK_GRACE_SECONDS = 10.0


def _pid_is_alive(pid: int) -> bool:
    """Whether ``pid`` may still be running; only a proven exit counts as dead.

    Standard library only: this runs before the environment that would provide
    anything else exists. A probe that cannot decide answers alive, so a lock is
    never taken from an owner this process merely could not inspect.
    """
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        process_query_limited_information = 0x1000
        still_active = 259
        error_invalid_parameter = 87
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return ctypes.get_last_error() != error_invalid_parameter
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _held_by_a_live_install(lock: Path) -> bool:
    """Whether the process recorded in ``lock`` may still be installing."""
    try:
        recorded = lock.read_text(encoding="ascii").strip()
        age = time.time() - lock.stat().st_mtime
    except FileNotFoundError:
        return False
    except (OSError, UnicodeDecodeError):
        return True
    if not recorded:
        return age < _EMPTY_LOCK_GRACE_SECONDS
    try:
        pid = int(recorded)
    except ValueError:
        return True
    return _pid_is_alive(pid)


def _reclaim(lock: Path) -> int | None:
    """Replace a dead owner's lock, or return ``None`` when a peer won the race."""
    lock.unlink(missing_ok=True)
    try:
        return os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None


@contextmanager
def _exclusive(venv: Path) -> Iterator[None]:
    """Hold an exclusive, venv-scoped lock, or refuse.

    Uses an atomic ``O_CREAT | O_EXCL`` create rather than a Windows named
    mutex so one implementation serves every platform. A second installer
    targeting the same environment is refused immediately rather than queued.
    A mutex is also released when its owner dies, and a lock file is not: an
    install killed mid-sync (a cancelled CI job, a closed terminal) left its
    file behind and refused every later install on that machine. A lock whose
    recorded owner has exited is therefore reclaimed, once.

    Args:
        venv: The virtualenv root being protected.

    Yields:
        ``None``, with the lock held.

    Raises:
        RuntimeError: When another install already owns this environment.
    """
    lock = Path(tempfile.gettempdir()) / _lock_name(venv)
    try:
        handle: int | None = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        handle = None if _held_by_a_live_install(lock) else _reclaim(lock)
    if handle is None:
        message = (
            f"Another dependency install already owns {venv}.\n"
            f"  If no install is running, delete the stale lock at {lock}."
        )
        raise RuntimeError(message)
    try:
        os.write(handle, str(os.getpid()).encode("ascii"))
        os.close(handle)
        yield
    finally:
        lock.unlink(missing_ok=True)


def _windows_users(venv: Path) -> list[str]:
    """Return descriptions of live Windows processes running out of ``venv``.

    The probe runs through PowerShell's CIM interface because the process
    command line is not reachable from the standard library. It is confined to
    this function: every caller sees a plain list of strings.

    Args:
        venv: The virtualenv root.

    Returns:
        One ``PID <n>: <command line>`` line per owning process. An empty list
        when none are found OR when the probe itself could not run - the probe
        is an aid to diagnosis, and its absence must not block an install.
    """
    prefix = str(venv.resolve()).rstrip("\\") + "\\"
    script = (
        "Get-CimInstance Win32_Process | Where-Object { "
        f"($_.ExecutablePath -and $_.ExecutablePath.StartsWith('{prefix}', "
        "[StringComparison]::OrdinalIgnoreCase)) -or "
        f"($_.CommandLine -and $_.CommandLine.Contains('{prefix}', "
        "[StringComparison]::OrdinalIgnoreCase)) } | "
        'ForEach-Object { "PID $($_.ProcessId): $($_.CommandLine)" }'
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def owning_processes(venv: Path = VENV) -> list[str]:
    """Return descriptions of live processes running out of ``venv``.

    Args:
        venv: The virtualenv root.

    Returns:
        One line per owning process; empty on platforms where the probe does
        not apply. Only Windows holds executables open in a way that breaks an
        install, so only Windows is probed.
    """
    if sys.platform != "win32":
        return []
    return _windows_users(venv)


@contextmanager
def guard(venv: Path = VENV) -> Iterator[None]:
    """Hold the install lock and refuse to mutate a venv that is in use.

    Args:
        venv: The virtualenv root to protect.

    Yields:
        ``None``, with the environment locked and verified idle.

    Raises:
        RuntimeError: When another install holds the lock, or when live
            processes are running out of this environment.
    """
    with _exclusive(venv):
        users = owning_processes(venv)
        if users:
            listing = "\n  ".join(users)
            message = (
                f"Refusing to mutate a virtualenv used by live processes. Stop the owning sessions first:\n  {listing}"
            )
            raise RuntimeError(message)
        yield
