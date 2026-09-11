"""Exact, lock-aware project synchronization through ``uv``."""

from __future__ import annotations

import subprocess
import sys

from ._venv import VENV, guard

#: The extras and groups an everyday development environment carries.
EXTRA = "workbook-windows"
GROUP = "dev"


def sync_command() -> tuple[str, ...]:
    """Return the sole command that converges the project environment."""
    return (
        "uv",
        "sync",
        "--locked",
        "--extra",
        EXTRA,
        "--group",
        GROUP,
    )


def install() -> int:
    """Synchronize runtime, workbook, and dev dependencies from ``uv.lock``.

    Returns:
        0 on success, 1 when the environment is locked or in use, otherwise
        the installer's exit code.
    """
    try:
        with guard(VENV):
            argv = sync_command()
            print(f"$ {' '.join(argv)}", flush=True)
            return subprocess.run(argv, check=False).returncode
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 1
