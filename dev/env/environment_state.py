"""Observe the installed project environment without synchronizing it."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from dev.packaging.command_execution import run_command

from ._install import sync_command, sync_environment


def environment_is_current(repo_root: Path) -> bool:
    """Ask uv whether the existing environment still matches the locked project.

    A directory or initialization stamp alone cannot detect missing or extra
    installed packages. This check observes the actual environment without
    synchronizing it, so only a stale environment needs installation.
    """
    uv = shutil.which("uv")
    if uv is None:
        return False
    try:
        result = run_command(
            (uv, *sync_command()[1:], "--check"),
            cwd=repo_root,
            environment=sync_environment(),
            timeout_seconds=60,
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0
