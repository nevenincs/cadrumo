"""Real proofs that ``python -m cadrumo.entrypoints.tui`` starts a session.

The module is EXECUTED as its own process here, never imported. An entry
point that imports cleanly and fails to start is the defect these exist to
catch, and an import-based assertion cannot see it: the delegation could
name a symbol that resolves and still raise, hang, or reach the CLI on the
way up.

Assertions are against the terminal control sequence a started Textual
session emits and against process behaviour, never against rendered prose.
The prose is locale data read from the same catalogue the app reads, so
asserting it would prove only that one file was consulted twice.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MODULE = "cadrumo.entrypoints.tui"
_ALTERNATE_SCREEN = b"?1049h"
"""The control sequence a Textual session emits when it takes the terminal."""

_STARTUP_GRACE_SECONDS = 45.0

_REPO_ROOT = Path(__file__).parents[5]


def _run_module(*, timeout: float) -> tuple[int | None, bytes]:
    """Execute the module as a real process and return its status and output."""
    process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell, repo-local module
        [sys.executable, "-m", _MODULE],
        cwd=_REPO_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        output, _ = process.communicate()
        return None, output
    return process.returncode, output


def test_module_execution_starts_a_session_rather_than_raising() -> None:
    """The module runs a real full-screen session instead of failing on invocation."""
    status, output = _run_module(timeout=_STARTUP_GRACE_SECONDS)

    assert status is None, (
        f"the session ended by itself with status {status}; a started TUI holds the terminal:\n"
        f"{output.decode('utf-8', errors='replace')[:2000]}"
    )
    assert _ALTERNATE_SCREEN in output, (
        "no session took the terminal:\n" + output.decode("utf-8", errors="replace")[:2000]
    )


def test_module_execution_reports_no_traceback() -> None:
    """A delegation that resolves but raises on the way up leaves a traceback."""
    _, output = _run_module(timeout=_STARTUP_GRACE_SECONDS)
    rendered = output.decode("utf-8", errors="replace")

    assert "Traceback (most recent call last)" not in rendered, rendered[:2000]
