"""Audited subprocess probes for tests.

The test suite deliberately exercises several import and startup boundaries in
fresh interpreters.  This adapter keeps those probes synchronous at their call
sites while using ``asyncio.create_subprocess_exec`` for the actual fixed-argv,
no-shell process launch.  It has no command lookup or dispatch layer: callers
provide the complete argv explicitly.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from os import PathLike
from pathlib import Path
from typing import Any, TypedDict

# The ``STARTUPINFO`` type on the platform that has one.
#
# ``subprocess.STARTUPINFO`` exists only in the Windows stubs, so naming it
# directly in an annotation is unresolved wherever the tree is analysed for
# another platform -- and an annotation is not a runtime branch, so no guard at
# a call site can narrow it. The module-level ``sys.platform == "win32"`` block
# is the one shape every checker this project runs narrows on, which makes this
# alias the real type on Windows and an unconstrained one everywhere else.
if sys.platform == "win32":
    type WindowsStartupInfo = subprocess.STARTUPINFO
else:
    type WindowsStartupInfo = Any


class _ProcessOptions(TypedDict, total=False):
    """Typed optional ``Popen`` options forwarded by the audited boundary."""

    pass_fds: tuple[int, ...]
    close_fds: bool
    startupinfo: WindowsStartupInfo


def run_audited_process(
    command: Sequence[str | PathLike[str]],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    input: str | bytes | None = None,
    capture_output: bool = False,
    text: bool = False,
    encoding: str | None = None,
    errors: str | None = None,
    timeout: float | None = None,
    check: bool = False,
    pass_fds: Sequence[int] = (),
    close_fds: bool | None = None,
    startupinfo: WindowsStartupInfo | None = None,
    after_spawn: Callable[[asyncio.subprocess.Process], object] | None = None,
) -> subprocess.CompletedProcess[str | bytes]:
    """Run an explicit argv through the audited async process boundary.

    ``after_spawn`` runs once the child exists and before it is awaited. A
    caller handing the child inherited descriptors or HANDLEs needs this gap:
    the child only inherits what is still open when it starts, and a parent
    that keeps its own copies open afterwards holds the pipe open, so a reader
    waiting for end-of-stream never sees it. Closing them before the launch
    instead makes the handle list invalid, which Windows reports as
    ``WinError 87``.
    """
    return asyncio.run(
        _run_audited_process(
            command,
            cwd=cwd,
            env=env,
            input=input,
            capture_output=capture_output,
            text=text,
            encoding=encoding,
            errors=errors,
            timeout=timeout,
            check=check,
            pass_fds=pass_fds,
            close_fds=close_fds,
            startupinfo=startupinfo,
            after_spawn=after_spawn,
        )
    )


async def _run_audited_process(
    command: Sequence[str | PathLike[str]],
    *,
    cwd: str | Path | None,
    env: Mapping[str, str] | None,
    input: str | bytes | None,
    capture_output: bool,
    text: bool,
    encoding: str | None,
    errors: str | None,
    timeout: float | None,
    check: bool,
    pass_fds: Sequence[int],
    close_fds: bool | None,
    startupinfo: WindowsStartupInfo | None,
    after_spawn: Callable[[asyncio.subprocess.Process], object] | None,
) -> subprocess.CompletedProcess[str | bytes]:
    """Implement :func:`run_audited_process` without shell or dispatch."""
    rendered_command = [str(argument) for argument in command]
    payload: bytes | None
    if input is None:
        payload = None
    elif isinstance(input, bytes):
        payload = input
    elif text:
        payload = input.encode(encoding or "utf-8", errors or "strict")
    else:
        raise TypeError("a string input requires text=True")

    launch_command, launch_env = _direct_interpreter_launch(rendered_command, env)
    process_options: _ProcessOptions = {}
    if pass_fds:
        process_options["pass_fds"] = tuple(pass_fds)
    if close_fds is not None:
        process_options["close_fds"] = close_fds
    if startupinfo is not None:
        process_options["startupinfo"] = startupinfo
    process = await asyncio.create_subprocess_exec(
        *launch_command,
        cwd=cwd,
        env=launch_env,
        stdin=asyncio.subprocess.PIPE if payload is not None else None,
        stdout=asyncio.subprocess.PIPE if capture_output else None,
        stderr=asyncio.subprocess.PIPE if capture_output else None,
        **process_options,
    )
    if after_spawn is not None:
        try:
            after_spawn(process)
        except BaseException:
            # The child is running; a hook failure must not leave it orphaned.
            process.kill()
            await process.communicate()
            raise
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(payload), timeout=timeout)
    except TimeoutError:
        process.kill()
        stdout, stderr = await process.communicate()
        if timeout is None:
            raise RuntimeError("the child process timed out without a timeout budget") from None
        raise subprocess.TimeoutExpired(
            rendered_command,
            timeout,
            output=_render_output(stdout, text=text, encoding=encoding, errors=errors),
            stderr=_render_output(stderr, text=text, encoding=encoding, errors=errors),
        ) from None

    returncode = process.returncode
    if returncode is None:
        raise RuntimeError("the child process did not finish after communicate()")
    result = subprocess.CompletedProcess(
        rendered_command,
        returncode,
        _render_output(stdout, text=text, encoding=encoding, errors=errors),
        _render_output(stderr, text=text, encoding=encoding, errors=errors),
    )
    if check and result.returncode:
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result


#: The variable a Windows virtual-environment ``python.exe`` sets before it
#: starts the base interpreter; the base interpreter reads it to adopt the
#: environment's ``sys.executable``, prefix and site-packages.
_VENV_LAUNCHER_VARIABLE = "__PYVENV_LAUNCHER__"


def _direct_interpreter_launch(
    command: list[str], env: Mapping[str, str] | None
) -> tuple[list[str], Mapping[str, str] | None]:
    """Start this environment's base interpreter directly instead of through its launcher.

    On Windows a virtual environment's ``python.exe`` is a separate launcher
    process whose only work is to start the base interpreter with
    ``__PYVENV_LAUNCHER__`` set. Doing that here yields the same interpreter
    configuration with one process creation fewer, which is the dominant
    start-up cost of a fresh-interpreter probe on a busy Windows host. Any
    other argv, including another interpreter or a console script, is
    launched exactly as given.
    """
    if sys.platform != "win32" or not command or sys.prefix == sys.base_prefix:
        return command, env
    base = getattr(sys, "_base_executable", None)
    if not isinstance(base, str) or not base or Path(command[0]) != Path(sys.executable):
        return command, env
    if Path(base) == Path(sys.executable) or not Path(base).is_file():
        return command, env
    launch_env = dict(os.environ if env is None else env)
    launch_env[_VENV_LAUNCHER_VARIABLE] = sys.executable
    return [base, *command[1:]], launch_env


def _render_output(
    output: bytes | None,
    *,
    text: bool,
    encoding: str | None,
    errors: str | None,
) -> str | bytes | None:
    """Render captured bytes with the same text/binary distinction as ``run``."""
    if output is None or not text:
        return output
    return output.decode(encoding or "utf-8", errors or "strict")


def ensure_text_completed_process(
    result: subprocess.CompletedProcess[str | bytes],
) -> subprocess.CompletedProcess[str]:
    """Validate the text-output contract of an explicitly text-mode child."""
    if not isinstance(result.stdout, str) or not isinstance(result.stderr, str):
        raise TypeError("the audited process did not return text output")
    return subprocess.CompletedProcess(result.args, result.returncode, result.stdout, result.stderr)


__all__ = ["ensure_text_completed_process", "run_audited_process"]
