"""Seal a test's process against network access and child-process launches.

A command that would reach a remote host, a local runtime server, an installer
or a browser meets an ``OSError`` at the standard library instead, exactly as it
would on a host with no network, and nothing outside the process starts. Every
refused attempt is recorded so a test can say which boundary a run met.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import socket
import subprocess
from dataclasses import dataclass, field
from typing import NoReturn

import pytest


@dataclass(slots=True)
class OfflineGuard:
    """The boundaries a sealed run tried to cross, and the hosts it named, in order."""

    refused: list[str] = field(default_factory=list)
    hosts: list[str] = field(default_factory=list)

    def refuse(self, boundary: str, host: object = None) -> NoReturn:
        """Record and refuse one attempt to leave the process."""
        self.refused.append(boundary)
        if isinstance(host, str | bytes) and host:
            self.hosts.append(host.decode("ascii", "replace") if isinstance(host, bytes) else host)
        raise OSError(f"the offline seal refuses {boundary}")

    def outcome(self) -> str:
        """Name the boundary the run met, or that it met none."""
        if not self.refused:
            return "completed without leaving the process"
        return "refused at " + ", ".join(dict.fromkeys(self.refused))


@pytest.fixture(name="offline_guard")
def offline_guard_fixture(monkeypatch: pytest.MonkeyPatch) -> OfflineGuard:
    """Seal the process against network and child-process launches for one test."""
    guard = OfflineGuard()
    original_connect = socket.socket.connect
    # Windows builds ``socket.socketpair`` from a loopback connect, and every
    # asyncio event loop needs one for its self-pipe; that connect never
    # leaves the process.
    socketpair_code = getattr(socket.socketpair, "__code__", None)

    def connect(self: socket.socket, address: tuple[str, int]) -> None:
        frame = inspect.currentframe()
        caller = None if frame is None else frame.f_back
        if socketpair_code is not None and caller is not None and caller.f_code is socketpair_code:
            return original_connect(self, address)
        guard.refuse("socket.connect", address[0])

    def connect_ex(self: socket.socket, address: tuple[str, int]) -> int:
        del self
        guard.refuse("socket.connect_ex", address[0])

    def create_connection(address: tuple[str, int], *args: object, **kwargs: object) -> socket.socket:
        del args, kwargs
        guard.refuse("socket.create_connection", address[0])

    def getaddrinfo(host: object, port: object, *args: object, **kwargs: object) -> list[object]:
        del port, args, kwargs
        guard.refuse("socket.getaddrinfo", host)

    async def loop_connection(self: asyncio.AbstractEventLoop, *args: object, **kwargs: object) -> object:
        del self
        guard.refuse("event-loop connection", kwargs.get("host", args[1] if len(args) > 1 else None))

    def execute_child(self: subprocess.Popen[bytes], *args: object, **kwargs: object) -> None:
        del self, args, kwargs
        guard.refuse("child process")

    def shell_launch(*args: object, **kwargs: object) -> int:
        del args, kwargs
        guard.refuse("shell launch")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "create_connection", create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(asyncio.BaseEventLoop, "create_connection", loop_connection)
    monkeypatch.setattr(subprocess.Popen, "_execute_child", execute_child)
    monkeypatch.setattr(os, "system", shell_launch)
    monkeypatch.setattr(os, "startfile", shell_launch, raising=False)
    return guard


__all__ = ["OfflineGuard", "offline_guard_fixture"]
