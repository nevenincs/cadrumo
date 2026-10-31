"""Start Playwright's pipe driver with an environment owned by that driver.

Playwright's public async context manager does not accept a driver environment.
This adapter follows its pipe transport and context-manager startup protocol so
that independent sessions never have to mutate the parent process environment.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from collections.abc import Mapping
from typing import Any, override

from playwright._impl import _transport as playwright_transport
from playwright._impl._connection import Connection
from playwright._impl._object_factory import create_remote_object
from playwright.async_api import Playwright
from playwright.async_api._context_manager import PlaywrightContextManager


class _EnvironmentPipeTransport(playwright_transport.PipeTransport):
    """Playwright's regular pipe transport, with explicit subprocess variables."""

    def __init__(self, loop: asyncio.AbstractEventLoop, environment: Mapping[str, str]) -> None:
        super().__init__(loop)
        self._environment = dict(environment)

    @override
    async def connect(self) -> None:
        self._stopped_future = asyncio.Future()
        try:
            environment = playwright_transport.get_driver_env()
            environment.update(self._environment)
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            executable, entrypoint = playwright_transport.compute_driver_executable()
            self._proc = await asyncio.create_subprocess_exec(
                executable,
                entrypoint,
                "run-driver",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=playwright_transport._get_stderr_fileno(),
                limit=32768,
                env=environment,
                startupinfo=startupinfo,
            )
        except Exception as exc:
            self.on_error_future.set_exception(exc)
            raise
        self._output = self._proc.stdin


class _OwnedPlaywright(Playwright):
    """Expose the regular Playwright API and retain its context manager."""

    def __init__(self, impl: Any, owner: PlaywrightContextManager) -> None:
        super().__init__(impl)
        self._owner = owner

    @override
    async def stop(self) -> None:
        await self._owner.__aexit__()


class DriverEnvironmentPlaywright(PlaywrightContextManager):
    """Playwright's async manager with a per-instance driver environment."""

    def __init__(self, environment: Mapping[str, str]) -> None:
        """Capture only this driver’s environment overrides."""
        super().__init__()
        self._environment = dict(environment)

    @override
    async def __aenter__(self) -> Playwright:
        """Connect the driver and return a runtime that owns its manager."""
        loop = asyncio.get_running_loop()
        transport = _EnvironmentPipeTransport(loop, self._environment)
        self._connection = Connection(None, create_remote_object, transport, loop)
        self._connection_task = loop.create_task(self._connection.run())
        future = self._connection.playwright_future
        done, _ = await asyncio.wait({transport.on_error_future, future}, return_when=asyncio.FIRST_COMPLETED)
        if not future.done():
            future.cancel()
        return _OwnedPlaywright(next(iter(done)).result(), self)
