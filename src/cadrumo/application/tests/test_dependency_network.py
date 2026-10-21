"""Network preflight against real loopback TLS servers and a real CONNECT proxy."""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import ipaddress
import socket
import ssl
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from pydantic import SecretStr, TypeAdapter

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ...core.config import Settings, override_settings
from ..dependency_contracts import DependencyBlockedReason, DependencyHostName
from ..dependency_network import (
    DependencyNetworkOutcome,
    DependencyProxy,
    DependencyProxyConfigurationError,
    check_dependency_host,
    dependency_host_reachability,
    dependency_hosts,
    dependency_proxy_environment,
    dependency_proxy_from_settings,
    preflight_dependency_hosts,
)
from ..dependency_registry import dependency_item_declarations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_HOST = "127.0.0.1"
_TUNNEL_WORD = "s3cr:et"
type _Handler = Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]


def _tls_pair(directory: Path) -> tuple[ssl.SSLContext, ssl.SSLContext]:
    """Return a server context with a fresh self-signed ``localhost`` certificate, and a client trusting it."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, _HOST)])
    now = dt.datetime.now(dt.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.IPv4Address(_HOST))]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    certificate_file = directory / "server.pem"
    key_file = directory / "server.key"
    certificate_file.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    server = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    server.load_cert_chain(certificate_file, key_file)
    client = ssl.create_default_context(cafile=str(certificate_file))
    return server, client


def _answer(status_line: str, *headers: str) -> _Handler:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.readuntil(b"\r\n\r\n")
        head = "\r\n".join((f"HTTP/1.1 {status_line}", *headers, "Content-Length: 0", "", ""))
        writer.write(head.encode("ascii"))
        await writer.drain()
        writer.close()

    return handle


async def _silent(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    del writer
    await reader.read()


@asynccontextmanager
async def _server(handler: _Handler, *, tls: ssl.SSLContext | None) -> AsyncGenerator[int]:
    server = await asyncio.start_server(handler, "127.0.0.1", 0, ssl=tls)
    port = server.sockets[0].getsockname()[1]
    assert isinstance(port, int)
    async with server:
        yield port


@asynccontextmanager
async def _connect_proxy(*, credentials: str | None) -> AsyncGenerator[int]:
    """A real CONNECT proxy that tunnels bytes to the requested loopback port."""

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = (await reader.readuntil(b"\r\n\r\n")).decode("latin-1").split("\r\n")
        method, target, _version = head[0].split(" ")
        expected = None if credentials is None else f"Basic {base64.b64encode(credentials.encode()).decode()}"
        offered = next(
            (line.split(":", 1)[1].strip() for line in head if line.lower().startswith("proxy-authorization:")), None
        )
        if method != "CONNECT" or offered != expected:
            writer.write(b"HTTP/1.1 407 Proxy Authentication Required\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        _host, port = target.rsplit(":", 1)
        upstream_reader, upstream_writer = await asyncio.open_connection("127.0.0.1", int(port))
        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await writer.drain()

        async def pump(source: asyncio.StreamReader, sink: asyncio.StreamWriter) -> None:
            while chunk := await source.read(65536):
                sink.write(chunk)
                await sink.drain()
            sink.close()

        await asyncio.gather(pump(reader, upstream_writer), pump(upstream_reader, writer), return_exceptions=True)

    async with _server(handle, tls=None) as port:
        yield port


def _closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        assert isinstance(port, int)
        return port


def test_any_http_answer_from_the_host_is_reachable(tmp_path: Path) -> None:
    server_tls, client_tls = _tls_pair(tmp_path)

    async def scenario() -> None:
        async with _server(_answer("404 Not Found"), tls=server_tls) as port:
            check = await check_dependency_host(_HOST, port=port, ssl_context=client_tls)
        assert check.outcome is DependencyNetworkOutcome.REACHABLE
        assert check.status_code == 404
        assert check.connected is True
        assert check.via_proxy is False

    asyncio.run(scenario())


def test_a_refusal_error_or_redirect_from_the_host_is_still_reachable(tmp_path: Path) -> None:
    """A publisher's download host answers a bare request for its root with 403; that answer proves it is there."""
    server_tls, client_tls = _tls_pair(tmp_path)

    async def check(handler: _Handler) -> tuple[DependencyNetworkOutcome, int | None]:
        async with _server(handler, tls=server_tls) as port:
            found = await check_dependency_host(_HOST, port=port, ssl_context=client_tls)
        return found.outcome, found.status_code

    async def scenario() -> None:
        reachable = DependencyNetworkOutcome.REACHABLE
        assert await check(_answer("403 Forbidden")) == (reachable, 403)
        assert await check(_answer("503 Service Unavailable")) == (reachable, 503)
        assert await check(_answer("302 Found", "Location: http://portal.example.net/login")) == (reachable, 302)
        assert await check(_answer("301 Moved", "Location: /elsewhere")) == (reachable, 301)
        async with _server(_answer("403 Forbidden"), tls=server_tls) as port:
            report = await preflight_dependency_hosts((_HOST,), port=port, ssl_context=client_tls)
        assert report.outcome is reachable
        assert report.failure_category is None and report.blocked_reason is None

    asyncio.run(scenario())


def test_an_untrusted_certificate_is_a_secure_connection_failure(tmp_path: Path) -> None:
    server_tls, _client_tls = _tls_pair(tmp_path)

    async def scenario() -> None:
        async with _server(_answer("200 OK"), tls=server_tls) as port:
            check = await check_dependency_host(_HOST, port=port)
        assert check.outcome is DependencyNetworkOutcome.SECURE_CONNECTION_FAILED
        assert check.connected is True

    asyncio.run(scenario())


def test_a_silent_host_is_unreachable_within_the_bound_and_not_offline(tmp_path: Path) -> None:
    server_tls, client_tls = _tls_pair(tmp_path)

    async def scenario() -> None:
        async with _server(_silent, tls=server_tls) as port:
            started = asyncio.get_running_loop().time()
            report = await preflight_dependency_hosts((_HOST,), port=port, ssl_context=client_tls, timeout_s=0.5)
            elapsed = asyncio.get_running_loop().time() - started
        assert elapsed < 2.0
        assert report.outcome is DependencyNetworkOutcome.HOST_UNREACHABLE
        assert report.failure_category is DependencyFailureCategory.HOST_UNREACHABLE
        assert report.blocked_reason is None

    asyncio.run(scenario())


def test_reaching_no_host_at_all_is_offline_and_blocks() -> None:
    async def scenario() -> None:
        report = await preflight_dependency_hosts(("nothing-here.invalid", _HOST), port=_closed_port(), timeout_s=2.0)
        assert [check.outcome for check in report.hosts] == [DependencyNetworkOutcome.OFFLINE] * 2
        assert report.outcome is DependencyNetworkOutcome.OFFLINE
        assert report.failure_category is DependencyFailureCategory.OFFLINE
        assert report.blocked_reason is DependencyBlockedReason.OFFLINE

    asyncio.run(scenario())


def test_one_host_down_while_another_answers_is_that_host(tmp_path: Path) -> None:
    server_tls, client_tls = _tls_pair(tmp_path)

    async def scenario() -> None:
        async with _server(_answer("200 OK"), tls=server_tls) as port:
            reachable = await check_dependency_host(_HOST, port=port, ssl_context=client_tls)
        down = await check_dependency_host("nothing-here.invalid", timeout_s=2.0)
        assert reachable.outcome is DependencyNetworkOutcome.REACHABLE
        assert down.outcome is DependencyNetworkOutcome.HOST_UNREACHABLE

    asyncio.run(scenario())


def test_the_proxy_tunnels_with_credentials_and_its_refusal_is_the_network(tmp_path: Path) -> None:
    server_tls, client_tls = _tls_pair(tmp_path)

    async def scenario() -> None:
        async with (
            _server(_answer("204 No Content"), tls=server_tls) as port,
            _connect_proxy(credentials=f"ana:{_TUNNEL_WORD}") as proxy_port,
        ):
            good = DependencyProxy(host="127.0.0.1", port=proxy_port, username="ana", password=_TUNNEL_WORD)
            tunnelled = await check_dependency_host(_HOST, port=port, proxy=good, ssl_context=client_tls)
            wrong = DependencyProxy(host="127.0.0.1", port=proxy_port, username="ana", password=_TUNNEL_WORD[::-1])
            refused = await check_dependency_host(_HOST, port=port, proxy=wrong, ssl_context=client_tls)
            bypassed = await check_dependency_host(
                _HOST,
                port=port,
                proxy=DependencyProxy(host="127.0.0.1", port=_closed_port(), bypass=(_HOST,)),
                ssl_context=client_tls,
            )
        assert tunnelled.outcome is DependencyNetworkOutcome.REACHABLE
        assert tunnelled.via_proxy is True
        assert tunnelled.status_code == 204
        assert refused.outcome is DependencyNetworkOutcome.BLOCKED_BY_NETWORK
        assert refused.status_code == 407
        assert bypassed.outcome is DependencyNetworkOutcome.REACHABLE
        assert bypassed.via_proxy is False

    asyncio.run(scenario())


def test_an_unreachable_proxy_never_claims_the_computer_is_offline() -> None:
    async def scenario() -> None:
        proxy = DependencyProxy(host="127.0.0.1", port=_closed_port())
        report = await preflight_dependency_hosts(("cdn.playwright.dev",), proxy=proxy, timeout_s=2.0)
        assert report.outcome is DependencyNetworkOutcome.HOST_UNREACHABLE

    asyncio.run(scenario())


def test_proxy_settings_reach_child_processes_without_showing_the_password() -> None:
    settings = Settings(
        cadrumo_proxy_url="http://proxy.example.net:3128",
        cadrumo_proxy_username="ana maria",
        cadrumo_proxy_password_secret=SecretStr("p@ss:word"),
        cadrumo_proxy_bypass="intranet.example, .corp.example",
    )
    proxy = dependency_proxy_from_settings(settings)
    assert proxy is not None
    assert (proxy.host, proxy.port, proxy.bypass) == ("proxy.example.net", 3128, ("intranet.example", ".corp.example"))
    assert proxy.bypasses("files.corp.example") is True
    assert proxy.bypasses("corp.example.org") is False
    assert "p@ss" not in repr(proxy)
    environment = dependency_proxy_environment(proxy)
    assert environment["HTTPS_PROXY"] == "http://ana%20maria:p%40ss%3Aword@proxy.example.net:3128"
    assert environment["https_proxy"] == environment["HTTPS_PROXY"]
    assert environment["NO_PROXY"] == "intranet.example,.corp.example"
    assert dependency_proxy_environment(None) == {}
    in_address = dependency_proxy_from_settings(
        Settings(cadrumo_proxy_url="http://ana%20maria:p%40ss@proxy.example:3128")
    )
    assert in_address is not None
    assert (in_address.username, in_address.password) == ("ana maria", "p@ss")
    assert "p@ss" not in repr(in_address)
    assert dependency_proxy_environment(in_address)["HTTPS_PROXY"] == "http://ana%20maria:p%40ss@proxy.example:3128"
    assert dependency_proxy_from_settings(Settings(cadrumo_proxy_url="")) is None
    with pytest.raises(DependencyProxyConfigurationError):
        dependency_proxy_from_settings(Settings(cadrumo_proxy_url="socks5://proxy.example.net:1080"))


def test_every_declared_item_names_declared_valid_hosts() -> None:
    adapter = TypeAdapter(DependencyHostName)
    for declaration in dependency_item_declarations():
        hosts = dependency_hosts(declaration.network_host_group)
        assert hosts
        for host in hosts:
            assert adapter.validate_python(host) == host
    with pytest.raises(KeyError):
        dependency_hosts("elsewhere")


def test_the_reachability_port_reports_an_unusable_proxy_as_the_network() -> None:
    with override_settings(cadrumo_proxy_url="socks5://proxy.example.net:1080"):
        outcome = asyncio.run(dependency_host_reachability(("cdn.playwright.dev",)))
    assert outcome is DependencyFailureCategory.BLOCKED_BY_NETWORK
