"""Audited subprocess probes for tests.

The test suite deliberately exercises several import and startup boundaries in
fresh interpreters.  This adapter keeps those probes synchronous at their call
sites while using ``asyncio.create_subprocess_exec`` for the actual fixed-argv,
no-shell process launch.  It has no command lookup or dispatch layer: callers
provide the complete argv explicitly.
"""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Mapping, Sequence
from os import PathLike
from pathlib import Path


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
    startupinfo: object | None = None,
) -> subprocess.CompletedProcess[str | bytes]:
    """Run an explicit argv through the audited async process boundary."""
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
    startupinfo: object | None,
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

    process_options: dict[str, object] = {}
    if pass_fds:
        process_options["pass_fds"] = tuple(pass_fds)
    if close_fds is not None:
        process_options["close_fds"] = close_fds
    if startupinfo is not None:
        process_options["startupinfo"] = startupinfo
    process = await asyncio.create_subprocess_exec(
        *rendered_command,
        cwd=cwd,
        env=env,
        stdin=asyncio.subprocess.PIPE if payload is not None else None,
        stdout=asyncio.subprocess.PIPE if capture_output else None,
        stderr=asyncio.subprocess.PIPE if capture_output else None,
        **process_options,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(payload), timeout=timeout)
    except TimeoutError:
        process.kill()
        stdout, stderr = await process.communicate()
        raise subprocess.TimeoutExpired(
            rendered_command,
            timeout,
            output=_render_output(stdout, text=text, encoding=encoding, errors=errors),
            stderr=_render_output(stderr, text=text, encoding=encoding, errors=errors),
        ) from None

    result = subprocess.CompletedProcess(
        rendered_command,
        process.returncode,
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


__all__ = ["run_audited_process"]
