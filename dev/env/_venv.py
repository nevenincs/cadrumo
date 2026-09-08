"""Guard the project environment while ``uv sync`` converges it."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
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


@contextmanager
def _exclusive(venv: Path) -> Iterator[None]:
    """Hold an exclusive, venv-scoped lock, or refuse.

    Uses an atomic ``O_CREAT | O_EXCL`` create rather than a Windows named
    mutex so one implementation serves every platform. The semantics the mutex
    provided are preserved: a second installer targeting the same environment
    is refused immediately rather than queued.

    Args:
        venv: The virtualenv root being protected.

    Yields:
        ``None``, with the lock held.

    Raises:
        RuntimeError: When another install already owns this environment.
    """
    lock = Path(tempfile.gettempdir()) / _lock_name(venv)
    try:
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        message = (
            f"Another dependency install already owns {venv}.\n"
            f"  If no install is running, delete the stale lock at {lock}."
        )
        raise RuntimeError(message) from None
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
