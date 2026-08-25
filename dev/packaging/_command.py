"""One truthful subprocess result boundary for packaging execution lanes."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from .._paths import UTF_8

_UTF_8 = UTF_8


@dataclass(frozen=True)
class CommandResult:
    """The complete observable result of one owned subprocess invocation."""

    argv: tuple[str, ...]
    cwd: str
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    returncode: int
    stdout: str
    stderr: str


def run_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
    timeout_seconds: float | None = None,
    errors: Literal["strict", "replace"] = "strict",
    input_text: str | None = None,
) -> CommandResult:
    """Run one command and retain its actual output, timestamps, and exit status."""
    if isinstance(argv, str):
        raise ValueError("command argv must be a sequence of arguments, not one string")
    command = tuple(argv)
    if not command or any(not argument for argument in command):
        raise ValueError("command argv must contain only non-empty arguments")
    started_at = datetime.now(UTC)
    started = time.monotonic()
    completed = subprocess.run(  # noqa: S603 - callers supply resolved internal or operator-approved argv.
        command,
        cwd=cwd,
        env=dict(environment) if environment is not None else None,
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors=errors,
        check=False,
        timeout=timeout_seconds,
        input=input_text,
    )
    completed_at = datetime.now(UTC)
    return CommandResult(
        argv=command,
        cwd=str(cwd),
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=round(time.monotonic() - started, 3),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


__all__ = ["CommandResult", "run_command"]
