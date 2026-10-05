"""Bounded control-tool calls; their completion is never application readiness."""

from __future__ import annotations

import contextlib
import os
import select
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import IO

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import remaining_budget


class ContainmentCommand(StrEnum):
    """Fixed native tools; callers cannot choose an executable or shell."""

    LAUNCHCTL = "/bin/launchctl"
    SYSTEMCTL = "/usr/bin/systemctl"
    SYSTEMD_RUN = "/usr/bin/systemd-run"


@dataclass(frozen=True, slots=True)
class ContainmentCommandResult:
    """Bounded nonsecret native control response; stderr is deliberately excluded."""

    returncode: int
    output: str


def run_containment_command_sync(tool: ContainmentCommand, arguments: tuple[str, ...]) -> ContainmentCommandResult:
    """Bound a fixed native containment command from the synchronous worker owner."""
    if sys.platform == "linux" or sys.platform == "darwin":
        supported = (
            {ContainmentCommand.SYSTEMCTL, ContainmentCommand.SYSTEMD_RUN}
            if sys.platform == "linux"
            else {ContainmentCommand.LAUNCHCTL}
        )
        if tool not in supported:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        environment = {
            "PATH": "/usr/bin:/bin",
            "LANG": "C",
            "LC_ALL": "C",
            "SYSTEMD_PAGER": "",
            "SYSTEMD_COLORS": "0",
        }
        if sys.platform == "linux":
            environment["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
        try:
            process = subprocess.Popen(  # noqa: S603 - fixed containment executable and bounded argument tuple
                (tool.value, *arguments),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=environment,
                close_fds=True,
                start_new_session=True,
            )
        except OSError:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
        stdout = process.stdout
        try:
            if stdout is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            return _read_containment_command_output(process, stdout)
        except subprocess.TimeoutExpired:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED) from None
        finally:
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=1)
            if stdout is not None:
                stdout.close()
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _read_containment_command_output(process: subprocess.Popen[bytes], stdout: IO[bytes]) -> ContainmentCommandResult:
    """Read one finite output stream with the original absolute budget and UTF-8 refusal."""
    deadline = time.monotonic() + 5
    output = bytearray()
    while True:
        remaining = remaining_budget(deadline)
        readable, _, _ = select.select((stdout,), (), (), remaining)
        if not readable:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        block = os.read(stdout.fileno(), 4096)
        if not block:
            break
        output.extend(block)
        if len(output) > 64 * 1024:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    returncode = process.wait(timeout=max(0.001, deadline - time.monotonic()))
    try:
        return ContainmentCommandResult(returncode, output.decode("utf-8"))
    except UnicodeError:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
