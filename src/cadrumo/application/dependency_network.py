"""Network preflight for setup items, and the proxy settings Cadrumo-started setup traffic follows.

Before a setup moves any byte, and during a full check, every host an item
declares is resolved, connected, taken through TLS and sent one bounded
``HEAD`` request. Each stage fails in its own way, and the stage that failed
is what tells the person what to do: no name resolution or connection
anywhere means the computer is offline; one host unreachable while others
answer is that host; a refused certificate is a secure-connection problem; a
proxy that refuses the tunnel, or demands credentials, is the network in
between. Any HTTP answer from the host itself over the verified TLS
connection, a ``403``, a ``404``, a ``5xx`` or a redirect to another host
included, proves the host is reachable: the preflight asks whether the host
can be reached, not whether a particular resource exists, and a publisher's
download host commonly refuses or redirects a bare request for its root.

The preflight runs on request only -- at the start of a setup and in a full
check -- never on a timer. It sends no taxpayer data.

The ``CADRUMO_PROXY_*`` settings apply to traffic Cadrumo itself starts: this
preflight, the browser installer's archive downloads and a model program
Cadrumo starts. The browser installer child is given no proxy; Cadrumo fetches
its archives itself through :class:`DependencyProxy`.
"""

from __future__ import annotations

import asyncio
import base64
import socket
import ssl
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, override
from urllib.parse import quote, unquote, urlsplit

from pydantic import BaseModel, Field

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..core.config import Settings, load_settings
from ..core.errors.hierarchy import CadrumoError
from ..core.external_constants import load_external_constants
from ..core.models import STRICT_FROZEN_CONFIG
from .dependency_contracts import DependencyBlockedReason

__all__ = [
    "DEPENDENCY_PREFLIGHT_HOST_TIMEOUT_S",
    "DependencyHostCheck",
    "DependencyNetworkOutcome",
    "DependencyNetworkReport",
    "DependencyProxy",
    "DependencyProxyConfigurationError",
    "check_dependency_host",
    "dependency_host_reachability",
    "dependency_hosts",
    "dependency_proxy_from_settings",
    "preflight_dependency_hosts",
]

DEPENDENCY_PREFLIGHT_HOST_TIMEOUT_S: Final = 3.0
"""Bound for one host's whole preflight: resolution, connection, TLS and the ``HEAD`` answer."""

_HTTPS_PORT: Final = 443
_MAX_RESPONSE_HEAD_BYTES: Final = 16 * 1024
_BLOCKING_STATUSES: Final = frozenset({403, 407})
"""A proxy's refusal of the tunnel; the host's own answer is never blocking."""


class DependencyNetworkOutcome(StrEnum):
    """What the preflight found for one host, or for one item's hosts together."""

    REACHABLE = "reachable"
    OFFLINE = "offline"
    HOST_UNREACHABLE = "host_unreachable"
    SECURE_CONNECTION_FAILED = "secure_connection_failed"
    BLOCKED_BY_NETWORK = "blocked_by_network"


_FAILURE_BY_OUTCOME: Final = {
    DependencyNetworkOutcome.OFFLINE: DependencyFailureCategory.OFFLINE,
    DependencyNetworkOutcome.HOST_UNREACHABLE: DependencyFailureCategory.HOST_UNREACHABLE,
    DependencyNetworkOutcome.SECURE_CONNECTION_FAILED: DependencyFailureCategory.SECURE_CONNECTION_FAILED,
    DependencyNetworkOutcome.BLOCKED_BY_NETWORK: DependencyFailureCategory.BLOCKED_BY_NETWORK,
}

# Worst first: the outcome a report shows is the first one any host reached.
_SEVERITY: Final = (
    DependencyNetworkOutcome.OFFLINE,
    DependencyNetworkOutcome.BLOCKED_BY_NETWORK,
    DependencyNetworkOutcome.SECURE_CONNECTION_FAILED,
    DependencyNetworkOutcome.HOST_UNREACHABLE,
    DependencyNetworkOutcome.REACHABLE,
)


class DependencyHostCheck(BaseModel):
    """One host's preflight answer.

    ``connected`` records whether a TCP connection to the host, or to the
    proxy, was ever made; it is what separates an offline computer from one
    unreachable host. ``status_code`` is the ``HEAD`` answer when one arrived.
    """

    model_config = STRICT_FROZEN_CONFIG

    host: str = Field(min_length=1, max_length=253)
    outcome: DependencyNetworkOutcome
    connected: bool
    via_proxy: bool
    status_code: int | None = Field(default=None, ge=100, le=599)


class DependencyNetworkReport(BaseModel):
    """The preflight of every host one item needs, in declaration order."""

    model_config = STRICT_FROZEN_CONFIG

    hosts: tuple[DependencyHostCheck, ...] = Field(min_length=1)

    @property
    def outcome(self) -> DependencyNetworkOutcome:
        """The worst outcome among the hosts; reachable only when every host is."""
        reached = {check.outcome for check in self.hosts}
        return next(outcome for outcome in _SEVERITY if outcome in reached)

    @property
    def reachable(self) -> bool:
        """Whether every host answered."""
        return self.outcome is DependencyNetworkOutcome.REACHABLE

    @property
    def failure_category(self) -> DependencyFailureCategory | None:
        """The failure category the report maps to, or ``None`` when every host answered."""
        return _FAILURE_BY_OUTCOME.get(self.outcome)

    @property
    def blocked_reason(self) -> DependencyBlockedReason | None:
        """``offline`` when the computer reached no host at all, which blocks rather than fails an item."""
        if self.outcome is DependencyNetworkOutcome.OFFLINE:
            return DependencyBlockedReason.OFFLINE
        return None


class DependencyProxyConfigurationError(CadrumoError):
    """The configured proxy is not one the preflight and child processes can use."""


@dataclass(frozen=True, slots=True)
class DependencyProxy:
    """An HTTP proxy reached with ``CONNECT``, its optional credentials and its bypass list.

    The password is held only to build the ``Proxy-Authorization`` header and
    the credentialed proxy URL; :meth:`__repr__` never shows it.
    """

    host: str
    port: int
    username: str = ""
    password: str = ""
    bypass: tuple[str, ...] = ()

    @override
    def __repr__(self) -> str:
        """Show the proxy endpoint without its credentials."""
        return f"DependencyProxy(host={self.host!r}, port={self.port}, bypass={self.bypass!r})"

    def bypasses(self, host: str) -> bool:
        """Whether ``host`` is reached directly: equal to, or a subdomain of, a bypass entry."""
        name = host.lower().rstrip(".")
        for entry in self.bypass:
            suffix = entry.lower().lstrip("*").lstrip(".").rstrip(".")
            if suffix and (name == suffix or name.endswith(f".{suffix}")):
                return True
        return False

    def url(self, *, with_credentials: bool) -> str:
        """Return the proxy as an ``http://`` URL, with percent-encoded credentials when asked."""
        authority = f"{self.host}:{self.port}"
        if with_credentials and self.username:
            credentials = quote(self.username, safe="")
            if self.password:
                credentials = f"{credentials}:{quote(self.password, safe='')}"
            authority = f"{credentials}@{authority}"
        return f"http://{authority}"


def dependency_proxy_from_settings(settings: Settings) -> DependencyProxy | None:
    """Return the proxy the ``CADRUMO_PROXY_*`` settings name, or ``None`` when none is set.

    Only plain ``http://`` proxies are supported: setup traffic is tunnelled
    with ``CONNECT`` and protected end to end by TLS to the publisher. The
    address may carry the user name and password (``http://user:pass@host``);
    the separate settings win when they are set.
    """
    raw = settings.cadrumo_proxy_url.strip()
    if not raw:
        return None
    parts = urlsplit(raw)
    if parts.scheme.lower() != "http" or parts.hostname is None or parts.hostname == "":
        raise DependencyProxyConfigurationError("the proxy must be an http:// address with a host name")
    try:
        port = parts.port or 80
    except ValueError as error:
        raise DependencyProxyConfigurationError("the proxy port is not a number between 1 and 65535") from error
    secret = settings.cadrumo_proxy_password_secret
    password = "" if secret is None else secret.get_secret_value()
    bypass = tuple(entry.strip() for entry in settings.cadrumo_proxy_bypass.split(",") if entry.strip())
    return DependencyProxy(
        host=parts.hostname,
        port=port,
        username=settings.cadrumo_proxy_username or unquote(parts.username or ""),
        password=password or unquote(parts.password or ""),
        bypass=bypass,
    )


async def dependency_host_reachability(hosts: tuple[str, ...]) -> DependencyFailureCategory | None:
    """Preflight ``hosts`` through the configured proxy and return the failure category, or ``None`` when all answer.

    This is the reachability port the setup items take. A proxy setting the
    preflight cannot use is the network in between, not an unreachable host.
    """
    try:
        proxy = dependency_proxy_from_settings(load_settings())
    except DependencyProxyConfigurationError:
        return DependencyFailureCategory.BLOCKED_BY_NETWORK
    report = await preflight_dependency_hosts(hosts, proxy=proxy)
    return report.failure_category


def dependency_hosts(group: str) -> tuple[str, ...]:
    """Return the declared hosts of one setup item's host group."""
    return load_external_constants().dependency_hosts.hosts_for(group)


class _StageError(CadrumoError):
    """Internal: a preflight stage ended with this outcome."""

    def __init__(self, outcome: DependencyNetworkOutcome, *, connected: bool, status_code: int | None = None) -> None:
        super().__init__(outcome.value)
        self.outcome = outcome
        self.connected = connected
        self.status_code = status_code


async def check_dependency_host(
    host: str,
    *,
    proxy: DependencyProxy | None = None,
    port: int = _HTTPS_PORT,
    ssl_context: ssl.SSLContext | None = None,
    timeout_s: float = DEPENDENCY_PREFLIGHT_HOST_TIMEOUT_S,
) -> DependencyHostCheck:
    """Resolve, connect, complete TLS and send one ``HEAD /`` to ``host``, classifying where it stopped.

    ``ssl_context`` defaults to the platform's verified client context; only
    tests pass another, to trust a local certificate.
    """
    tunnel = proxy if proxy is not None and not proxy.bypasses(host) else None
    context = ssl.create_default_context() if ssl_context is None else ssl_context
    progress = {"connected": False}
    try:
        async with asyncio.timeout(timeout_s):
            status = await _head(host, port=port, proxy=tunnel, context=context, progress=progress)
    except _StageError as stage:
        return DependencyHostCheck(
            host=host,
            outcome=stage.outcome,
            connected=stage.connected or progress["connected"],
            via_proxy=tunnel is not None,
            status_code=stage.status_code,
        )
    except TimeoutError:
        return DependencyHostCheck(
            host=host,
            outcome=DependencyNetworkOutcome.HOST_UNREACHABLE,
            connected=progress["connected"],
            via_proxy=tunnel is not None,
        )
    return DependencyHostCheck(
        host=host,
        outcome=DependencyNetworkOutcome.REACHABLE,
        connected=True,
        via_proxy=tunnel is not None,
        status_code=status,
    )


async def preflight_dependency_hosts(
    hosts: Sequence[str],
    *,
    proxy: DependencyProxy | None = None,
    port: int = _HTTPS_PORT,
    ssl_context: ssl.SSLContext | None = None,
    timeout_s: float = DEPENDENCY_PREFLIGHT_HOST_TIMEOUT_S,
) -> DependencyNetworkReport:
    """Check every host together and report them in the given order.

    When no host was even connected and no proxy stood in between, the
    computer is offline and every host reports so. Through a proxy that cannot
    be reached, nothing proves the computer itself is offline, so the hosts
    stay unreachable.
    """
    if not hosts:
        raise ValueError("a preflight checks at least one host")
    checks = await asyncio.gather(
        *(
            check_dependency_host(host, proxy=proxy, port=port, ssl_context=ssl_context, timeout_s=timeout_s)
            for host in hosts
        )
    )
    return DependencyNetworkReport(hosts=_with_offline(checks))


def _with_offline(checks: Iterable[DependencyHostCheck]) -> tuple[DependencyHostCheck, ...]:
    settled = tuple(checks)
    nowhere = all(
        check.outcome is DependencyNetworkOutcome.HOST_UNREACHABLE and not check.connected and not check.via_proxy
        for check in settled
    )
    if not nowhere:
        return settled
    return tuple(check.model_copy(update={"outcome": DependencyNetworkOutcome.OFFLINE}) for check in settled)


async def _head(
    host: str,
    *,
    port: int,
    proxy: DependencyProxy | None,
    context: ssl.SSLContext,
    progress: dict[str, bool],
) -> int:
    connect_host, connect_port = (host, port) if proxy is None else (proxy.host, proxy.port)
    await _resolve(connect_host, connect_port)
    try:
        reader, writer = await asyncio.open_connection(connect_host, connect_port)
    except OSError as error:
        raise _StageError(DependencyNetworkOutcome.HOST_UNREACHABLE, connected=False) from error
    progress["connected"] = True
    try:
        if proxy is not None:
            await _open_tunnel(reader, writer, host=host, port=port, proxy=proxy)
        try:
            await writer.start_tls(context, server_hostname=host)
        except ssl.SSLError as error:
            raise _StageError(DependencyNetworkOutcome.SECURE_CONNECTION_FAILED, connected=True) from error
        except OSError as error:
            raise _StageError(DependencyNetworkOutcome.HOST_UNREACHABLE, connected=True) from error
        authority = host if port == _HTTPS_PORT else f"{host}:{port}"
        writer.write(_head_request(authority))
        await writer.drain()
        status, _headers = await _read_response_head(reader)
    finally:
        writer.close()
    return status


def _head_request(authority: str) -> bytes:
    lines = (
        "HEAD / HTTP/1.1",
        f"Host: {authority}",
        "User-Agent: Cadrumo",
        "Accept: */*",
        "Connection: close",
    )
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii")


async def _resolve(host: str, port: int) -> None:
    loop = asyncio.get_running_loop()
    try:
        await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as error:
        raise _StageError(DependencyNetworkOutcome.HOST_UNREACHABLE, connected=False) from error


async def _open_tunnel(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *,
    host: str,
    port: int,
    proxy: DependencyProxy,
) -> None:
    lines = [f"CONNECT {host}:{port} HTTP/1.1", f"Host: {host}:{port}", "User-Agent: Cadrumo"]
    if proxy.username:
        token = base64.b64encode(f"{proxy.username}:{proxy.password}".encode()).decode("ascii")
        lines.append(f"Proxy-Authorization: Basic {token}")
    writer.write(("\r\n".join(lines) + "\r\n\r\n").encode("utf-8"))
    await writer.drain()
    status, _headers = await _read_response_head(reader)
    if 200 <= status < 300:
        return
    if status in _BLOCKING_STATUSES:
        raise _StageError(DependencyNetworkOutcome.BLOCKED_BY_NETWORK, connected=True, status_code=status)
    raise _StageError(DependencyNetworkOutcome.HOST_UNREACHABLE, connected=True, status_code=status)


async def _read_response_head(reader: asyncio.StreamReader) -> tuple[int, dict[str, str]]:
    try:
        raw = await reader.readuntil(b"\r\n\r\n")
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError) as error:
        raise _StageError(DependencyNetworkOutcome.HOST_UNREACHABLE, connected=True) from error
    if len(raw) > _MAX_RESPONSE_HEAD_BYTES:
        raise _StageError(DependencyNetworkOutcome.HOST_UNREACHABLE, connected=True)
    lines = raw.decode("latin-1").split("\r\n")
    fields = lines[0].split(" ", 2)
    if len(fields) < 2 or not fields[0].startswith("HTTP/") or not fields[1].isdigit():
        raise _StageError(DependencyNetworkOutcome.HOST_UNREACHABLE, connected=True)
    status = int(fields[1])
    if not 100 <= status <= 599:
        raise _StageError(DependencyNetworkOutcome.HOST_UNREACHABLE, connected=True)
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, separator, value = line.partition(":")
        if separator:
            headers[name.strip().lower()] = value.strip()
    return status, headers
