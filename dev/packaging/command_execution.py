"""One truthful subprocess result boundary for packaging execution lanes.

The result type and the runner are addressed from outside this package by the
``dev.ci`` runtime compatibility lane, which records the same truthful subprocess
result, so both are public here rather than internals of the packaging lanes.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from dev._paths import UTF_8

_UTF_8 = UTF_8
# How long a killed command's pipes may take to close. A tree kill closes them
# at once; the bound only matters when a descendant escaped the kill.
_POST_KILL_DRAIN_SECONDS = 10.0


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
        returncode, stdout, stderr = asyncio.run(
            _run_process(
                command,
                cwd=cwd,
                environment=environment,
                timeout_seconds=timeout_seconds,
                errors=errors,
                input_text=input_text,
                inherited_descriptors=inherited_descriptors,
            ),
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
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


async def _run_process(
    command: tuple[str, ...],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None,
    timeout_seconds: float | None,
    errors: Literal["strict", "replace"],
    input_text: str | None,
    inherited_descriptors: Sequence[int],
) -> tuple[int, str, str]:
    """Execute one explicit argv with bounded capture and optional input."""
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        env=dict(environment) if environment is not None else None,
        stdin=asyncio.subprocess.PIPE if input_text is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **cast(Any, _inheritance_options(inherited_descriptors)),
    )
    encoded_input = None if input_text is None else input_text.encode(_UTF_8)
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(encoded_input), timeout_seconds)
    except TimeoutError as exc:
        await _terminate_tree(process)
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), _POST_KILL_DRAIN_SECONDS)
        except TimeoutError:
            # A descendant the kill could not reach still holds the captured
            # pipes; the timeout is reported without the output it withholds.
            stdout_bytes, stderr_bytes = b"", b""
        if timeout_seconds is None:
            raise RuntimeError("process timed out without a configured timeout") from exc
        raise subprocess.TimeoutExpired(command, timeout_seconds, output=stdout_bytes, stderr=stderr_bytes) from exc
    returncode = process.returncode
    if returncode is None:
        raise RuntimeError("process completed without a return code")
    return (
        returncode,
        _decode_output(stdout_bytes, errors=errors),
        _decode_output(stderr_bytes, errors=errors),
    )


async def _terminate_tree(process: asyncio.subprocess.Process) -> None:
    """Kill a timed-out command together with the processes it started.

    A launcher such as LibreOffice's ``soffice`` hands the work to a child that
    inherits the captured pipes. Killing only the launcher leaves that child
    running and holding the pipes open, so draining them would wait for the
    child to exit on its own. Windows walks the tree with ``taskkill /T``.
    POSIX runs each command in the caller's process group so an interrupt still
    reaches it, which leaves no group to signal here; there the bounded drain is
    what ends the wait.
    """
    if process.returncode is not None:
        return
    taskkill = shutil.which("taskkill") if sys.platform == "win32" else None
    if taskkill is not None:
        killer = await asyncio.create_subprocess_exec(
            taskkill,
            "/F",
            "/T",
            "/PID",
            str(process.pid),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.communicate()
    # Re-read after the await: the kill above may already have reaped it.
    returncode: int | None = process.returncode
    if returncode is None:
        with suppress(ProcessLookupError):
            process.kill()


def _decode_output(payload: bytes, *, errors: Literal["strict", "replace"]) -> str:
    """Match ``subprocess.run(text=True)`` universal-newline decoding."""
    return payload.decode(_UTF_8, errors=errors).replace("\r\n", "\n").replace("\r", "\n")


__all__ = ["CommandResult", "run_command"]
