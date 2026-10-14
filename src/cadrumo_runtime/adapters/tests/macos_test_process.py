"""Retained async process owner shared by native macOS acceptance fixtures."""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from threading import Event, Thread


class MacosTestProcess:
    """Reap one disposable child and its event loop on a retained owning thread."""

    def __init__(self, command: Sequence[str], *, cwd: Path, env: Mapping[str, str]) -> None:
        """Start one fixed fixture command with separate null streams and no inherited descriptors."""
        self._ready = Event()
        self._done = Event()
        self._child: asyncio.subprocess.Process | None = None
        self._failure: BaseException | None = None
        self._code: int | None = None
        self._thread = Thread(target=self._own, args=(tuple(command), cwd, dict(env)), daemon=True)
        self._thread.start()
        self._ready.wait()
        if self._failure is not None:
            self._thread.join()
            raise self._failure

    def _own(self, command: tuple[str, ...], cwd: Path, env: dict[str, str]) -> None:
        try:
            asyncio.run(self._run(command, cwd, env))
        except BaseException as error:
            self._failure = error
        finally:
            self._ready.set()
            self._done.set()

    async def _run(self, command: tuple[str, ...], cwd: Path, env: dict[str, str]) -> None:
        self._child = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
        self._ready.set()
        self._code = await self._child.wait()

    @property
    def pid(self) -> int:
        """Return the exact child PID published after native creation."""
        assert self._child is not None
        return self._child.pid

    def poll(self) -> int | None:
        """Observe completion only after the event loop has reaped its child."""
        return self._code if self._done.is_set() else None

    def kill(self) -> None:
        """Signal only this retained child's native process."""
        assert self._child is not None
        self._child.kill()

    def wait(self, *, timeout: float) -> int:
        """Join the owned loop/thread within the caller's explicit budget."""
        if not self._done.wait(timeout):
            raise subprocess.TimeoutExpired("macos-owned-fixture", timeout)
        self._thread.join()
        if self._failure is not None:
            raise self._failure
        assert self._code is not None
        return self._code
