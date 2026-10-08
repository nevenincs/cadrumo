"""Installed profile-worker argv selection shared by every POSIX guardian."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

_INSTALLED_WORKER_ARGUMENTS = ("-I", "-B", "-m", "cadrumo.entrypoints.runtime.worker")


def validated_worker_arguments(
    arguments: Sequence[str] | None = None, *, worker_script: Path | None = None
) -> tuple[str, ...]:
    """Build or verify argv for the host's explicitly selected isolated worker.

    Script selection belongs to the trusted Python constructor. It is never
    inferred from worker arguments, client documents or the environment.

    Args:
        arguments: Complete worker argv after the interpreter, or None to build its prefix.
        worker_script: Absolute host-selected script replacing the installed module.
    """
    prefix: tuple[str, ...] = _INSTALLED_WORKER_ARGUMENTS
    if worker_script is not None:
        if not worker_script.is_absolute():
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        try:
            selected = worker_script.resolve(strict=True)
            if not selected.is_file():
                raise ValueError
        except (OSError, ValueError):
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE) from None
        prefix = ("-I", "-B", str(selected))
    if arguments is None:
        return prefix
    command = tuple(arguments)
    if command[: len(prefix)] != prefix or any("\0" in argument for argument in command):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    return command
