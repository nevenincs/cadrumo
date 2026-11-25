"""Fail any test closed, loudly, that reaches for a host other than loopback.

Every AEAT, Cl@ve and other remote read leaves through a Chromium the browser
session launches, often from a profile worker in a separate process, or through
an HTTP client in the test process. Two barriers cover both:

- The process environment names a proxy this plugin serves on loopback. Every
  browser session reads it through ``Settings`` and a profile worker receives
  it from its runtime as a relayed setting, so a Chromium started in this
  process or in any worker sends every non-loopback request here. The proxy
  answers nothing but a refusal and records the host the request named.
- In the test process, a stream connect or event-loop connection to a
  non-loopback address is refused, and a Playwright launch without a loopback
  proxy is given this one.

A test during which either barrier saw a non-loopback host fails, naming the
host. Loopback, ``data:`` and routed pages never reach either barrier. A test
marked ``aeat_live`` runs without the barriers only when the live-test opt-in
is set; without it the test is refused before its body runs.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import os
import socket
import socketserver
import sys
import threading
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Final, cast, override
from urllib.parse import urlsplit

import pytest

PROXY_URL_VARIABLE: Final = "CADRUMO_PROXY_URL"
"""The setting every browser session turns into its Chromium proxy, relayed to profile workers."""

PROXY_BYPASS_VARIABLE: Final = "CADRUMO_PROXY_BYPASS"
"""The browser session's proxy bypass list; loopback stays direct."""

LOOPBACK_BYPASS: Final = "localhost,127.0.0.1,[::1]"

_LIVE_MARKER: Final = "aeat_live"
_REQUEST_HEAD_LIMIT: Final = 16384


class NetworkGuardRefusedError(ConnectionRefusedError):
    """A test-process connection to a non-loopback host, refused by the network guard."""


@dataclass(frozen=True, slots=True)
class Violation:
    """One attempt to reach a non-loopback host, and the barrier that met it."""

    host: str
    barrier: str


def is_loopback_host(host: str) -> bool:
    """Return whether ``host`` names this machine without leaving it."""
    name = host.strip().strip("[]").rstrip(".").lower()
    if name == "localhost" or name.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(name.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return address.is_loopback or address.is_unspecified


def _requested_host(head: bytes) -> str | None:
    """Return the host a proxy request names: a CONNECT authority, an absolute URL or the Host header."""
    lines = head.decode("latin-1", "replace").split("\r\n")
    parts = lines[0].split()
    if len(parts) < 2:
        return None
    method, target = parts[0].upper(), parts[1]
    if method == "CONNECT":
        return urlsplit(f"//{target}").hostname
    if "://" in target:
        return urlsplit(target).hostname
    for line in lines[1:]:
        name, _, value = line.partition(":")
        if name.strip().lower() == "host":
            return urlsplit(f"//{value.strip()}").hostname
    return None


@dataclass(slots=True)
class NetworkGuard:
    """The armed state and the attempts recorded since the running test began."""

    proxy_url: str = ""
    armed: bool = False
    current: str | None = None
    previous: str | None = None
    _pending: list[Violation] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, host: str, barrier: str) -> None:
        """Record one attempt; the running test, or the next one, fails for it."""
        with self._lock:
            self._pending.append(Violation(host=host, barrier=barrier))

    def refuse(self, host: str, barrier: str) -> None:
        """Record an attempt and refuse it as a connection refusal."""
        self.record(host, barrier)
        raise NetworkGuardRefusedError(
            f"the test network guard refuses a connection to non-loopback host {host!r} ({barrier})"
        )

    def take(self) -> tuple[Violation, ...]:
        """Return and forget every attempt recorded so far."""
        with self._lock:
            taken = tuple(self._pending)
            self._pending.clear()
        return taken

    def browser_proxy(self, given: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
        """Return the proxy a browser launch must use: a loopback one it named, else this guard's."""
        if not self.armed:
            return given
        if given is not None:
            server = str(given.get("server", ""))
            host = urlsplit(server if "://" in server else f"//{server}").hostname or ""
            if is_loopback_host(host):
                return given
            self.record(host, "browser launch proxy")
        return {"server": self.proxy_url, "bypass": LOOPBACK_BYPASS}


GUARD: Final = NetworkGuard()
"""This process's guard; each pytest process, xdist workers included, serves its own proxy."""


def network_guard_armed() -> bool:
    """Return whether this process's barriers are armed."""
    return GUARD.armed


class _RefusingProxyHandler(socketserver.BaseRequestHandler):
    """Read one proxy request head, record the host it names, and refuse it."""

    @override
    def handle(self) -> None:
        connection = cast(socket.socket, self.request)
        connection.settimeout(10)
        head = b""
        try:
            while b"\r\n\r\n" not in head and len(head) < _REQUEST_HEAD_LIMIT:
                chunk = connection.recv(4096)
                if not chunk:
                    break
                head += chunk
        except OSError:
            pass
        host = _requested_host(head)
        if host is not None and not is_loopback_host(host):
            GUARD.record(host, "browser proxy")
        body = f"the test network guard refuses {host or 'this request'}\n".encode()
        response = (
            b"HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\nConnection: close\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode()
            + body
        )
        with contextlib.suppress(OSError):
            connection.sendall(response)


class _RefusingProxy(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False


@dataclass(slots=True)
class _Installed:
    """What arming changed, so disarming and unconfigure restore it exactly."""

    server: _RefusingProxy
    thread: threading.Thread
    original_environment: dict[str, str | None]
    restores: list[Callable[[], None]] = field(default_factory=list)


_INSTALLED: list[_Installed] = []


def _guarded_environment() -> dict[str, str | None]:
    # An operator's proxy credentials stay set: Chromium offers them only to a proxy that asks, and this one never does.
    return {PROXY_URL_VARIABLE: GUARD.proxy_url, PROXY_BYPASS_VARIABLE: LOOPBACK_BYPASS}


def _apply_environment(values: Mapping[str, str | None]) -> None:
    for name, value in values.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    from ..core.config import reset_settings_cache

    reset_settings_cache()


def _patch(owner: object, name: str, replacement: object, restores: list[Callable[[], None]]) -> None:
    original = getattr(owner, name)
    setattr(owner, name, replacement)
    restores.append(lambda: setattr(owner, name, original))


def _stream_host(sock: socket.socket, address: object) -> str | None:
    if sock.family not in (socket.AF_INET, socket.AF_INET6) or not isinstance(address, tuple):
        return None
    host = cast(tuple[object, ...], address)[0]
    return host if isinstance(host, str) else None


def _install_socket_barrier(restores: list[Callable[[], None]]) -> None:
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = asyncio.BaseEventLoop.create_connection

    def connect(self: socket.socket, address: Any) -> None:
        host = _stream_host(self, address)
        if GUARD.armed and host is not None and not is_loopback_host(host):
            GUARD.refuse(host, "socket.connect")
        return original_connect(self, address)

    def connect_ex(self: socket.socket, address: Any) -> int:
        host = _stream_host(self, address)
        if GUARD.armed and host is not None and not is_loopback_host(host):
            GUARD.refuse(host, "socket.connect_ex")
        return original_connect_ex(self, address)

    async def create_connection(self: asyncio.BaseEventLoop, *args: Any, **kwargs: Any) -> Any:
        host = kwargs.get("host", args[1] if len(args) > 1 else None)
        if GUARD.armed and isinstance(host, str) and not is_loopback_host(host):
            GUARD.refuse(host, "event-loop connection")
        return await original_create_connection(self, *args, **kwargs)

    _patch(socket.socket, "connect", connect, restores)
    _patch(socket.socket, "connect_ex", connect_ex, restores)
    _patch(asyncio.BaseEventLoop, "create_connection", create_connection, restores)


def _install_playwright_barrier(restores: list[Callable[[], None]]) -> None:
    try:
        from playwright._impl._browser import Browser
        from playwright._impl._browser_type import BrowserType
        from playwright._impl._fetch import APIRequest
    except ImportError:
        return

    def launching(original: Callable[..., Any]) -> Callable[..., Any]:
        async def launch(self: object, *args: Any, **kwargs: Any) -> Any:
            kwargs["proxy"] = GUARD.browser_proxy(kwargs.get("proxy"))
            return await original(self, *args, **kwargs)

        return launch

    original_new_context = Browser.new_context

    async def new_context(self: Browser, *args: Any, **kwargs: Any) -> Any:
        # A context without a proxy of its own inherits the guarded launch proxy.
        if kwargs.get("proxy") is not None:
            kwargs["proxy"] = GUARD.browser_proxy(kwargs["proxy"])
        return await original_new_context(self, *args, **kwargs)

    _patch(BrowserType, "launch", launching(BrowserType.launch), restores)
    _patch(BrowserType, "launch_persistent_context", launching(BrowserType.launch_persistent_context), restores)
    _patch(Browser, "new_context", new_context, restores)
    # A standalone request context sends from the Playwright driver, outside every socket of this process.
    _patch(APIRequest, "new_context", launching(APIRequest.new_context), restores)


def _arm() -> None:
    GUARD.armed = True
    _apply_environment(_guarded_environment())


def _disarm() -> None:
    GUARD.armed = False
    _apply_environment(_INSTALLED[0].original_environment)


def _describe(violations: tuple[Violation, ...]) -> str:
    by_host: dict[str, list[str]] = {}
    for violation in violations:
        barriers = by_host.setdefault(violation.host, [])
        if violation.barrier not in barriers:
            barriers.append(violation.barrier)
    return ", ".join(f"{host} ({', '.join(barriers)})" for host, barriers in by_host.items())


def _failure(violations: tuple[Violation, ...], *, late_from: str | None = None) -> str:
    when = (
        f"non-loopback host(s) reached after {late_from} ended"
        if late_from is not None
        else "this test reached non-loopback host(s)"
    )
    return (
        f"network guard: {when}: {_describe(violations)}. "
        "Tests stay on loopback, data: or routed pages; a real external read needs "
        f"@pytest.mark.{_LIVE_MARKER} and CADRUMO_LIVE_TESTS_ENABLED=1."
    )


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """Serve the refusing proxy, point the environment at it and arm the barriers."""
    del config
    if _INSTALLED:
        return
    server = _RefusingProxy(("127.0.0.1", 0), _RefusingProxyHandler)
    port = cast(tuple[str, int], server.server_address)[1]
    thread = threading.Thread(target=server.serve_forever, name="cadrumo-network-guard-proxy", daemon=True)
    thread.start()
    GUARD.proxy_url = f"http://127.0.0.1:{port}"
    names = (PROXY_URL_VARIABLE, PROXY_BYPASS_VARIABLE)
    installed = _Installed(
        server=server, thread=thread, original_environment={name: os.environ.get(name) for name in names}
    )
    _INSTALLED.append(installed)
    _install_socket_barrier(installed.restores)
    _install_playwright_barrier(installed.restores)
    _arm()


def pytest_unconfigure(config: pytest.Config) -> None:
    """Restore everything arming changed and stop the proxy."""
    del config
    if not _INSTALLED:
        return
    installed = _INSTALLED.pop()
    GUARD.armed = False
    for restore in reversed(installed.restores):
        restore()
    installed.server.shutdown()
    installed.server.server_close()
    _apply_environment(installed.original_environment)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int | pytest.ExitCode) -> None:
    """Fail the run for an attempt that arrived after the last test of this process ended."""
    del exitstatus
    late = GUARD.take()
    if late:
        sys.stderr.write(_failure(late, late_from=GUARD.previous or "the last test") + "\n")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture(autouse=True)
def _network_guard(request: pytest.FixtureRequest) -> Iterator[None]:
    """Fail the test for any non-loopback attempt; disarm only for an opted-in live test."""
    late = GUARD.take()
    if late:
        pytest.fail(_failure(late, late_from=GUARD.previous or "an earlier test"), pytrace=False)
    if request.node.get_closest_marker(_LIVE_MARKER) is not None:
        from .live_gate import requires_live_enabled

        requires_live_enabled()
        _disarm()
        try:
            yield
        finally:
            _arm()
            GUARD.take()
        return
    GUARD.current = request.node.nodeid
    try:
        yield
    finally:
        GUARD.previous, GUARD.current = GUARD.current, None
    reached = GUARD.take()
    if reached:
        pytest.fail(_failure(reached), pytrace=False)


__all__ = [
    "GUARD",
    "LOOPBACK_BYPASS",
    "PROXY_BYPASS_VARIABLE",
    "PROXY_URL_VARIABLE",
    "NetworkGuard",
    "NetworkGuardRefusedError",
    "Violation",
    "is_loopback_host",
    "network_guard_armed",
]
