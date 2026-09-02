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
import tempfile
from pathlib import Path
from typing import Final

import typer

from ..full_screen_session_protocol import (
    SELF_TEST_FLAG,
    FullScreenDestination,
    FullScreenSessionOutcome,
    FullScreenSessionRequest,
    parse_outcome,
    render_request_arguments,
)

TUI_SESSION_MODULE: Final[str] = "cadrumo.entrypoints.tui"

_OUTCOME_FILE_NAME: Final[str] = "session-outcome.json"


def tui_session_command(executable: str = sys.executable, *, self_test: bool = False) -> list[str]:
    """Build the child-interpreter command line that starts one TUI session."""
    command = [executable, "-m", TUI_SESSION_MODULE]
    if self_test:
        command.append(SELF_TEST_FLAG)
    return command


def run_tui_session(*, self_test: bool = False) -> int:
    """Run one full-screen session to completion and return its exit status.

    The child inherits this process's streams so the terminal belongs to it for
    the session's lifetime. Its status is returned rather than interpreted: a
    session that ends badly must not read as a successful CLI invocation.
    """
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        tui_session_command(self_test=self_test), check=False
    )
    return completed.returncode


def destination_session_command(request: FullScreenSessionRequest, executable: str = sys.executable) -> list[str]:
    """Build the child-interpreter command line that opens one destination."""
    return [executable, "-m", TUI_SESSION_MODULE, *render_request_arguments(request)]


def run_destination_session(
    *,
    destination: FullScreenDestination,
    work_unit_id: str | None = None,
    bucket_id: str | None = None,
    include_discarded: bool = False,
    output_language: str | None = None,
    self_test: bool = False,
) -> FullScreenSessionOutcome:
    """Open one full-screen destination out of process and read its outcome.

    The child inherits this process's streams so the terminal belongs to the
    session for its lifetime, which is also why the outcome cannot ride the
    child's standard output. The parent names a file instead; it lives in a
    directory removed when this call returns, and it carries only the
    destination's own identity tokens and the guidance a refusal already shows
    the operator.

    A session that ends badly must not read as a successful invocation, so a
    non-zero child status leaves through this process's exit status rather
    than being converted into an outcome nobody observed.
    """
    with tempfile.TemporaryDirectory(prefix="cadrumo-session-") as scratch:
        outcome_file = Path(scratch) / _OUTCOME_FILE_NAME
        request = FullScreenSessionRequest(
            destination=destination,
            outcome_file=outcome_file,
            work_unit_id=work_unit_id,
            bucket_id=bucket_id,
            include_discarded=include_discarded,
            output_language=output_language,
            self_test=self_test,
        )
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            destination_session_command(request), check=False
        )
        if completed.returncode != 0:
            raise typer.Exit(completed.returncode)
        if not outcome_file.exists():
            raise typer.Exit(1)
        return parse_outcome(outcome_file.read_text(encoding="utf-8"))


__all__ = [
    "TUI_SESSION_MODULE",
    "destination_session_command",
    "run_destination_session",
    "run_tui_session",
    "tui_session_command",
]
