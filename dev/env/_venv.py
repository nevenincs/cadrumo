"""Guard the project environment while ``uv sync`` converges it."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from dev._paths import REPO_ROOT, prepare_temporary_directory

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


def _try_lock(handle: int) -> bool:
    """Take the advisory lock on ``handle`` without waiting, and report whether it was taken."""
    if sys.platform == "win32":
        import msvcrt

        try:
            msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl

    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    return True


@contextmanager
def _exclusive(venv: Path) -> Iterator[None]:
    """Hold an exclusive, venv-scoped lock, or refuse.

    The lock is an operating-system advisory lock on a venv-scoped file in the
    temp directory -- ``flock`` on POSIX, ``msvcrt.locking`` on Windows -- so
    the system releases it when the owning process ends, however it ends. A
    lock that was the file's mere existence outlived every installer killed
    before its cleanup ran: a cancelled CI job left one behind, and each later
    install of that environment was refused until someone deleted the file by
    hand. The file stays in place after release, because removing it would let
    a waiting process lock the unlinked file while a third locks its
    replacement. A second installer targeting the same environment is still
    refused immediately rather than queued.

    Args:
        venv: The virtualenv root being protected.

    Yields:
        ``None``, with the lock held.

    Raises:
        RuntimeError: When another install already owns this environment.
    """
    lock = prepare_temporary_directory() / _lock_name(venv)
    handle = os.open(lock, os.O_CREAT | os.O_RDWR)
    try:
        if not _try_lock(handle):
            raise RuntimeError(f"Another dependency install already owns {venv} (it holds {lock}).")
        # The owner's PID, for diagnosis only: the held lock is what excludes.
        os.ftruncate(handle, 0)
        os.write(handle, str(os.getpid()).encode("ascii"))
        yield
    finally:
        # Closing the descriptor releases the lock.
        os.close(handle)


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
