"""Start the full-screen session that a bare ``aeat --tui`` requests.

The session runs OUT OF PROCESS, and that is the whole point of this module.
A CLI entrypoint may not import, load, re-export, annotate against, or register
from the TUI; out-of-process execution is the sanctioned way for one to reach
the other. So the request is honoured by executing the TUI package's own
module-execution surface as a child interpreter, and nothing here names a TUI
symbol.

The child is addressed as ``python -m`` against the package rather than by the
installed console script, so a checkout, an editable install, and a wheel all
start the same session, and no second packaging entry has to exist for the CLI
to find it.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Final

TUI_SESSION_MODULE: Final[str] = "cadrumo.entrypoints.tui"


def tui_session_command(executable: str = sys.executable) -> list[str]:
    """Build the child-interpreter command line that starts one TUI session."""
    return [executable, "-m", TUI_SESSION_MODULE]


def run_tui_session() -> int:
    """Run one full-screen session to completion and return its exit status.

    The child inherits this process's streams so the terminal belongs to it for
    the session's lifetime. Its status is returned rather than interpreted: a
    session that ends badly must not read as a successful CLI invocation.
    """
    completed = subprocess.run(tui_session_command(), check=False)  # noqa: S603 - fixed argv, no shell
    return completed.returncode


__all__ = ["TUI_SESSION_MODULE", "run_tui_session", "tui_session_command"]
