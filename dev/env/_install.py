"""Additive dependency installation into this checkout's virtualenv.

`uv pip install` rather than `uv sync` is deliberate and load bearing: shared
Windows worktrees hold long-lived executable locks under `.venv/Scripts`, and a
sync - which prunes before it installs - fails against them. The additive form
leaves what is already installed in place, so a resident session keeps working.
"""

from __future__ import annotations

import subprocess
import sys

from dev.env._venv import VENV, guard, interpreter

#: The extras and groups an everyday development environment carries.
EXTRA = ".[workbook-windows]"
GROUP = "dev"


def install() -> int:
    """Install runtime, workbook, and dev dependencies additively.

    Returns:
        0 on success, 1 when the environment is locked or in use, otherwise
        the installer's exit code.
    """
    try:
        with guard(VENV):
            argv = [
                "uv",
                "pip",
                "install",
                "--python",
                str(interpreter(VENV)),
                "--editable",
                EXTRA,
                "--group",
                GROUP,
            ]
            print(f"$ {' '.join(argv)}", flush=True)
            return subprocess.run(argv, check=False).returncode
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 1
