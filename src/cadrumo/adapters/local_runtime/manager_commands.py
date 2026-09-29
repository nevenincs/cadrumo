"""Bounded control-tool calls; their completion is never application readiness."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
from dataclasses import dataclass
from enum import StrEnum

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError


class NativeManagerCommand(StrEnum):
    """Fixed native tools; callers cannot choose an executable or shell."""

    SYSTEMCTL = "/usr/bin/systemctl"
    LAUNCHCTL = "/bin/launchctl"


@dataclass(frozen=True, slots=True)
class ManagerCommandResult:
    """Bounded nonsecret native control response; stderr is deliberately excluded."""

    returncode: int
    output: str


async def _start_manager_process(
    tool: NativeManagerCommand, arguments: tuple[str, ...], environment: dict[str, str]
) -> tuple[asyncio.subprocess.Process, asyncio.StreamReader]:
    try:
        process = await asyncio.create_subprocess_exec(
            tool.value,
            *arguments,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=environment,
            close_fds=True,
            start_new_session=True,
        )
        if process.stdout is not None:
            return process, process.stdout
        process.kill()
        await process.wait()
    except OSError:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None
    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


async def run_manager_command(tool: NativeManagerCommand, arguments: tuple[str, ...]) -> ManagerCommandResult:
    """Run a fixed tool with bounded I/O, no prompt and no inherited descriptors.

    Timeout kills only our control-tool process. The native manager may already
    have accepted an action; callers must inspect/reconcile before retrying.
    This helper is not worker or browser containment.
    """
    if sys.platform == "win32" or (tool is NativeManagerCommand.LAUNCHCTL and sys.platform != "darwin"):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    if tool is NativeManagerCommand.SYSTEMCTL and not sys.platform.startswith("linux"):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "SYSTEMD_PAGER": "", "SYSTEMD_COLORS": "0"}
    # The standard user-manager bus is bound to the native owner, never a
    # caller-supplied DBUS_SESSION_BUS_ADDRESS or imported shell environment.
    if sys.platform == "linux":
        environment["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    process, stdout = await _start_manager_process(tool, arguments, environment)
    try:
        async with asyncio.timeout(5):
            output = bytearray()
            while block := await stdout.read(4096):
                output.extend(block)
                if len(output) > 64 * 1024:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            returncode = await process.wait()
        try:
            return ManagerCommandResult(returncode=returncode, output=output.decode("utf-8"))
        except UnicodeError:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
    except TimeoutError:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED) from None
    finally:
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=1)
