"""Bounded control-tool calls; their completion is never application readiness."""

from __future__ import annotations

import asyncio
import contextlib
import os
import select
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import StrEnum

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.async_cleanup import await_cancellation_complete, close_async_resources


class NativeManagerCommand(StrEnum):
    """Fixed native tools; callers cannot choose an executable or shell."""

    SYSTEMCTL = "/usr/bin/systemctl"
    SYSTEMD_RUN = "/usr/bin/systemd-run"
    LAUNCHCTL = "/bin/launchctl"


@dataclass(frozen=True, slots=True)
class ManagerCommandResult:
    """Bounded nonsecret native control response; stderr is deliberately excluded."""

    returncode: int
    output: str


class _ManagerCommandProcess:
    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self._process = process

    async def close(self) -> None:
        if self._process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                self._process.kill()
        await asyncio.wait_for(self._process.wait(), timeout=1)


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


async def _start_launchctl_process(
    arguments: tuple[str, ...], environment: dict[str, str]
) -> tuple[asyncio.subprocess.Process, asyncio.StreamReader]:
    owned: list[tuple[asyncio.subprocess.Process, asyncio.StreamReader]] = []

    async def launch() -> None:
        owned.append(await _start_manager_process(NativeManagerCommand.LAUNCHCTL, arguments, environment))

    try:
        await await_cancellation_complete(launch(), task_name="launchctl-control-launch")
    except BaseException:
        if owned:
            await close_async_resources(
                _ManagerCommandProcess(owned[0][0]), task_name="launchctl-control-close", primary_error=sys.exception()
            )
        raise
    if not owned:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return owned[0]


def _require_manager_platform(tool: NativeManagerCommand) -> None:
    if tool is NativeManagerCommand.LAUNCHCTL:
        if sys.platform != "darwin":
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    elif not sys.platform.startswith("linux"):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


async def run_manager_command(
    tool: NativeManagerCommand, arguments: tuple[str, ...], *, timeout: float = 5
) -> ManagerCommandResult:
    """Run a fixed tool with bounded I/O, no prompt and no inherited descriptors.

    Timeout kills only our control-tool process. The native manager may already
    have accepted an action; callers must inspect/reconcile before retrying.
    This helper is not worker or browser containment.

    Args:
        tool: Fixed platform control executable.
        arguments: Exact native target and bounded action arguments.
        timeout: Finite control budget; defaults preserve ordinary manager calls.
    """
    _require_manager_platform(tool)
    if not 0 < timeout <= 30:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "SYSTEMD_PAGER": "", "SYSTEMD_COLORS": "0"}
    # The standard user-manager bus is bound to the native owner, never a
    # caller-supplied DBUS_SESSION_BUS_ADDRESS or imported shell environment.
    if sys.platform == "linux":
        environment["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    if tool is NativeManagerCommand.LAUNCHCTL:
        process, stdout = await _start_launchctl_process(arguments, environment)
    else:
        process, stdout = await _start_manager_process(tool, arguments, environment)
    try:
        async with asyncio.timeout(timeout):
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
        if tool is NativeManagerCommand.LAUNCHCTL:
            await close_async_resources(
                _ManagerCommandProcess(process), task_name="launchctl-control-close", primary_error=sys.exception()
            )
        elif process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=1)


def run_manager_command_sync(tool: NativeManagerCommand, arguments: tuple[str, ...]) -> ManagerCommandResult:
    """Bound a fixed native manager command from the synchronous worker owner."""
    if sys.platform == "linux":
        if tool not in {NativeManagerCommand.SYSTEMCTL, NativeManagerCommand.SYSTEMD_RUN}:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        environment = {
            "PATH": "/usr/bin:/bin",
            "LANG": "C",
            "LC_ALL": "C",
            "SYSTEMD_PAGER": "",
            "SYSTEMD_COLORS": "0",
            "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}",
        }
        try:
            process = subprocess.Popen(  # noqa: S603 - fixed manager executable and bounded argument tuple
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
            deadline = time.monotonic() + 5
            output = bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
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
                return ManagerCommandResult(returncode, output.decode("utf-8"))
            except UnicodeError:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
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
