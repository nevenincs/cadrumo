"""Real proofs that the composed TUI module starts a session.

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

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_ALTERNATE_SCREEN = b"?1049h"
"""The control sequence a Textual session emits when it takes the terminal."""


def test_module_execution_starts_a_session_rather_than_raising(module_run: tuple[int | None, bytes]) -> None:
    """The module runs a real full-screen session instead of failing on invocation."""
    status, output = module_run

    assert status is None, (
        f"the session ended by itself with status {status}; a started TUI holds the terminal:\n"
        f"{output.decode('utf-8', errors='replace')[:2000]}"
    )
    assert _ALTERNATE_SCREEN in output, (
        "no session took the terminal:\n" + output.decode("utf-8", errors="replace")[:2000]
    )


def test_module_execution_reports_no_traceback(module_run: tuple[int | None, bytes]) -> None:
    """A delegation that resolves but raises on the way up leaves a traceback."""
    _, output = module_run
    rendered = output.decode("utf-8", errors="replace")

    assert "Traceback (most recent call last)" not in rendered, rendered[:2000]
