"""Launch the independent full-screen root from ``aeat app tui``.

The command is deliberately an opaque process boundary.  It starts the TUI's
module-execution surface without importing it, passing no route, subject, or
session state across the boundary.  The child owns its terminal and every
navigation decision after it starts.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Final

import typer

TUI_ROOT_MODULE: Final[str] = "cadrumo.entrypoints.tui"


def tui_root_command(executable: str = sys.executable) -> list[str]:
    """Build the fixed child-process command for the independent TUI root."""
    return [executable, "-m", TUI_ROOT_MODULE]


def launch_tui() -> None:
    """Start the independent TUI root and propagate its process status."""
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        tui_root_command(),
        check=False,
    )
    raise typer.Exit(completed.returncode)


__all__ = ["TUI_ROOT_MODULE", "launch_tui", "tui_root_command"]
