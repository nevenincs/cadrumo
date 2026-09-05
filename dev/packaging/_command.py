"""One truthful subprocess result boundary for packaging execution lanes."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

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


def _inheritance_options(descriptors: Sequence[int]) -> dict[str, Any]:
    """Map parent descriptors onto this platform's child-inheritance mechanism.

    POSIX inherits numeric descriptors directly, so an allowlist is the whole
    mechanism. Windows has no equivalent - ``subprocess`` refuses ``pass_fds``
    there outright - and a CRT descriptor number means nothing in a new
    process. The transferable object is the underlying HANDLE, allowlisted in
    the process-creation attribute list; the child converts it back.
    """
    if not descriptors:
        return {}
    if sys.platform != "win32":
        return {"pass_fds": tuple(descriptors)}
    import msvcrt

    handles = [msvcrt.get_osfhandle(descriptor) for descriptor in descriptors]
    for handle in handles:
        os.set_handle_inheritable(handle, True)
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.lpAttributeList = {"handle_list": handles}
    return {"startupinfo": startupinfo}


def _close_inheritance_window(descriptors: Sequence[int]) -> None:
    """Stop allowlisted HANDLEs leaking into any later child of this process."""
    if not descriptors or sys.platform != "win32":
        return
    import msvcrt

    for descriptor in descriptors:
        with suppress(OSError):
            os.set_handle_inheritable(msvcrt.get_osfhandle(descriptor), False)


def run_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
    timeout_seconds: float | None = None,
    errors: Literal["strict", "replace"] = "strict",
    input_text: str | None = None,
    inherited_descriptors: Sequence[int] = (),
) -> CommandResult:
    """Run one command and retain its actual output, timestamps, and exit status.

    ``inherited_descriptors`` names parent descriptors the child must receive
    in addition to the captured standard streams. The caller still has to tell
    the child what it was given, and the token differs by platform, so it reads
    the descriptor numbers - or, on Windows, ``msvcrt.get_osfhandle`` of the
    same descriptors - for itself.
    """
    if isinstance(argv, str):
        raise ValueError("command argv must be a sequence of arguments, not one string")
    command = tuple(argv)
    if not command or any(not argument for argument in command):
        raise ValueError("command argv must contain only non-empty arguments")
    started_at = datetime.now(UTC)
    started = time.monotonic()
    try:
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
            **cast(Any, _inheritance_options(inherited_descriptors)),
        )
    finally:
        _close_inheritance_window(inherited_descriptors)
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
