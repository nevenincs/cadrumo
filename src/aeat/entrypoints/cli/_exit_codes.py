"""Stable CLI exit-code table for the JSON output contract."""

from __future__ import annotations

from enum import IntEnum

import typer


class ExitCode(IntEnum):
    """Stable process exit codes reserved for the AEAT CLI contract."""

    SUCCESS = 0
    ERROR = 1
    REFUSED = 2
    AUTH = 3
    INTEGRITY = 4
    FAIL = 5
    INTERNAL = 6
    LOCKED_BY_DESIGN = 7
    LOCKED_BY_CONCURRENCY = 8
    NO_NETWORK = 10
    USAGE = 20


def exit_with(code: ExitCode, *, message: str | None = None) -> None:
    """Emit an optional stderr message and terminate with ``code``.

    Phase 2 will route this helper through the sibling error-envelope
    implementation from issue #398. Until then, emission stays plain
    stderr so callers can still standardize on the shared exit table.

    Args:
        code: Stable CLI exit code to raise.
        message: Optional stderr message to emit before exiting.
    """

    if message:
        typer.echo(message, err=True)
    raise typer.Exit(int(code))


__all__ = ["ExitCode", "exit_with"]
