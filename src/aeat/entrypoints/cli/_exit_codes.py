"""Stable CLI exit-code table for the JSON output contract.

Defines :class:`~aeat.entrypoints.cli._exit_codes.ExitCode`, the canonical
exit-code reservation used by every command in :mod:`aeat.entrypoints.cli`, and
:func:`~aeat.entrypoints.cli._exit_codes.exit_with`, the thin helper that emits
an optional stderr message and raises :class:`typer.Exit` with the chosen code.
Keeping the table centralised beside
:func:`~aeat.core.errors.get_error_exit_code` guarantees that the CLI contract
and the structured error envelope speak the same exit-code vocabulary.
"""

from __future__ import annotations

from enum import IntEnum

import typer


class ExitCode(IntEnum):
    """Stable process exit codes reserved for the AEAT CLI contract.

    The values map one-to-one with :class:`~aeat.core.errors.ErrorCategory`
    categories so the JSON envelope's ``exit_code`` field is always derived
    from the same table the operating shell sees.

    Attributes:
        SUCCESS: Command completed without error.
        ERROR: Generic, recoverable failure.
        REFUSED: Operator-driven refusal (e.g. interactive stdin missing).
        AUTH: Authentication or authorisation failure.
        INTEGRITY: Data-integrity violation (checksum mismatch, etc.).
        FAIL: Operation attempted but failed mid-flight.
        INTERNAL: Unexpected internal error (programming bug surfaced).
        LOCKED_BY_DESIGN: Operation blocked by an intentional safety lock.
        LOCKED_BY_CONCURRENCY: Operation blocked by another in-flight run.
        NO_NETWORK: Required network endpoint unreachable.
        USAGE: Invalid CLI usage (bad flag combination, missing argument).
    """

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

    Args:
        code: Stable CLI exit code to raise.
        message: Optional stderr message to emit before exiting.

    Raises:
        typer.Exit: Always, with the integer value of ``code``.
    """
    if message:
        typer.echo(message, err=True)
    raise typer.Exit(int(code))


__all__ = ["ExitCode", "exit_with"]
