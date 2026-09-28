"""Credential-free real HTTP and Playwright boundary for adapter tests.

Every page request is fulfilled by the context route from a real loopback HTTP
server. Playwright continues a redirect hop without consulting any route, so the
browser is also launched through this server as its proxy: a hop arrives as a
``CONNECT`` tunnel, is served through the same scenario table, and nothing the
browser requests can reach the network.
"""

from __future__ import annotations

import asyncio
import ssl
import tempfile
import threading
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Final, cast, override
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from playwright.async_api import BrowserContext, Playwright, Route, async_playwright
from playwright.async_api import Error as PlaywrightError

from ......application.auth.protocols import BrowserContextProvisioner, BrowserSessionFactoryPort
from ......core.config import Settings
from ......core.config_support import AEAT_CERTIFICATE_PROTECTED_PATH, AEAT_CERTIFICATE_PROTECTED_URL
from ..evasion import PlaywrightStealthEvasion
from ..factory import DefaultBrowserSession
from ..profile import Profile
from ..session import BrowserSession

EXTERNAL = Settings.external_constants()
_DOMAINS = EXTERNAL.aeat.domains
_CLAVE_MOVIL = EXTERNAL.aeat.clave_movil
_CLAVE_PERMANENTE = EXTERNAL.aeat.clave_permanente
PRE303 = EXTERNAL.aeat.pre303
_PROTECTED_PARENT = AEAT_CERTIFICATE_PROTECTED_PATH.rpartition("/")[0]
_WRONG_HOST_URL: Final[str] = f"{_DOMAINS.www1}{AEAT_CERTIFICATE_PROTECTED_PATH}"
_WRONG_PATH_URL: Final[str] = f"{_DOMAINS.www6}{_PROTECTED_PARENT}/OtroRecurso"
_REDACTION_PROBE_VALUE: Final[str] = "certificate-query-7e2b"
_SENSITIVE_URL: Final[str] = f"{_DOMAINS.www6}{_PROTECTED_PARENT}/Interrumpido?probe={_REDACTION_PROBE_VALUE}"
_MOVIL_QR_URL: Final[str] = f"{_DOMAINS.www12}{_CLAVE_MOVIL.obtener_clave_movil_qr_path}"
_REPRESENTATION_URL: Final[str] = f"{_DOMAINS.www6}{_CLAVE_MOVIL.dialogo_representacion_path}"
_PRE303_TARGET_URL: Final[str] = f"{_DOMAINS.www1}{PRE303.presentation_service_path}"
_PERMANENTE_IDP_URL: Final[str] = f"https://se-pasarela.{urlsplit(_DOMAINS.clave).netloc}/idp/login"
_DEFAULT_CLAVE_TARGET_URL: Final[str] = f"{_DOMAINS.www6}{EXTERNAL.aeat.sede_paths.expedientes_resumen}"
#: Registrable domains whose hosts the tunnel stands in for; any other host is refused.
_STOOD_IN_DOMAINS: Final[tuple[str, ...]] = (_DOMAINS.host_suffix, urlsplit(_DOMAINS.clave).netloc)


_TUNNEL_CERTIFICATE_NAME: Final = "boundary.crt"


def _tunnel_tls_context(directory: Path) -> ssl.SSLContext:
    """Return a server context over a throwaway self-signed certificate written to ``directory``."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "cadrumo-real-http-boundary")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    certificate_path = directory / _TUNNEL_CERTIFICATE_NAME
    key_path = directory / "boundary.key"
    certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate_path, key_path)
    return context


class _BoundaryServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], boundary: LocalHttpBoundary) -> None:
        self.boundary = boundary
        super().__init__(server_address, _BoundaryHandler)


class _BoundaryHandler(BaseHTTPRequestHandler):
    _tunnel_host: str | None = None
    """Host of the ``CONNECT`` tunnel this connection carries, once one is open."""

    def do_CONNECT(self) -> None:
        """Terminate a redirect hop's TLS tunnel so the scenario table serves it."""
        boundary = cast("_BoundaryServer", self.server).boundary
        host = self.path.rpartition(":")[0]
        if not boundary.stands_in_for(host):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        self.send_response(HTTPStatus.OK, "Connection Established")
        self.end_headers()
        try:
            tunnel = boundary.tunnel_tls.wrap_socket(self.connection, server_side=True)
        except (ssl.SSLError, OSError):
            # Chromium also opens a speculative connection it abandons mid-handshake.
            self.close_connection = True
            return
        self.connection = tunnel
        self.rfile = tunnel.makefile("rb")
        self.wfile = tunnel.makefile("wb")
        self._tunnel_host = host
        # The handler speaks HTTP/1.0, so the connection closes once the CONNECT
        # is answered; the one request the tunnel carries is served here first.
        self.handle_one_request()

    def do_GET(self) -> None:
        if self._tunnel_host is not None:
            proxied_url = f"https://{self._tunnel_host}{self.path}"
        elif self.path.startswith("http://"):
            # A plain-HTTP request the browser sent to this server as its proxy.
            proxied_url = self.path
        else:
            proxied_url = None
        if proxied_url is not None:
            boundary = cast("_BoundaryServer", self.server).boundary
            if not boundary.stands_in_for(urlsplit(proxied_url).hostname or ""):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            self.path = boundary.record_request(proxied_url)
        if self.path == "/failure":
            self.send_error(HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if self.path == "/redirect-wrong-host":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", _WRONG_HOST_URL)
            self.end_headers()
            return
        if self.path == "/redirect-wrong-path":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", _WRONG_PATH_URL)
            self.end_headers()
            return
        if self.path == "/redirect-sensitive":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", _SENSITIVE_URL)
            self.end_headers()
            return
        if self.path == "/disconnect":
            self.connection.shutdown(2)
            self.connection.close()
            return
        if self.path == "/blocking":
            boundary = cast("_BoundaryServer", self.server).boundary
            boundary.request_started.set()
            if not boundary.release_request.wait(timeout=10):
                self.send_error(HTTPStatus.GATEWAY_TIMEOUT)
                return
        body = self._body()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        if self.path == "/clave-success":
            self.send_header("Set-Cookie", "AEAT_SESSION=real-boundary; Path=/; Secure; SameSite=Lax")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> bytes:
        boundary = cast("_BoundaryServer", self.server).boundary
        if boundary.response_html is not None:
            html = boundary.response_html
        elif self.path == "/clave-movil-selector-pending":
            html = (
                f'<form method="get" action="{_MOVIL_QR_URL}">'
                '<button name="autoriza-P" type="submit">Cl@ve Movil</button>'
                "</form>"
            )
        elif self.path == "/clave-movil-pending":
            html = (
                "<p>No ha sido posible generar una nueva petición de autenticación con Cl@ve Móvil. "
                "Rechace la petición pendiente en la APP Cl@ve.</p>"
            )
        elif self.path == "/clave-movil-selector-representation":
            html = (
                f'<form method="get" action="{_REPRESENTATION_URL}">'
                '<button name="autoriza-P" type="submit">Continuar</button>'
                "</form>"
            )
        elif self.path == "/clave-movil-representation":
            html = f"""
            <form id="repForm" method="get" action="{_PRE303_TARGET_URL}">
              <input name="forigen" type="hidden" value="pre303">
              <input id="propio" type="radio">
              <label for="propio">Actuar en nombre propio</label>
              <input id="representante" type="radio">
              <button type="submit">Confirmar</button>
            </form>
            """
        elif self.path == "/clave-movil-representation-missing":
            html = "<main><h1>Representación autenticada</h1></main>"
        elif self.path in {"/clave-permanente-form-success", "/clave-permanente-form-invalid"}:
            action = _DEFAULT_CLAVE_TARGET_URL if self.path.endswith("success") else _PERMANENTE_IDP_URL
            html = f"""
            <form method="get" action="{action}">
              <input id="usuario_login" name="usuario_login">
              <input id="password_login" name="password_login" type="password">
              <button id="enviar_login" type="submit">Entrar</button>
            </form>
            """
        elif self.path == "/clave-permanente-invalid":
            html = f"<p>{_CLAVE_PERMANENTE.invalid_credentials_marker}</p>"
        else:
            html = "<html><title>real-auth-boundary</title></html>"
        return html.encode("utf-8")

    @override
    def log_message(self, format: str, *args: object) -> None:
        del format, args


class LocalHttpBoundary:
    """Serve real HTTP responses while Playwright retains the requested AEAT URL."""

    def __init__(self) -> None:
        self.scenario = "success"
        self.response_html: str | None = None
        self.navigation_count = 0
        self.requested_urls: list[str] = []
        self.request_started = threading.Event()
        self.release_request = threading.Event()
        self.release_request.set()
        self._record_lock = threading.Lock()
        self._tunnel_material = tempfile.TemporaryDirectory(prefix="cadrumo-boundary-tls-")
        self.tunnel_tls = _tunnel_tls_context(Path(self._tunnel_material.name))
        self.tunnel_certificate = Path(self._tunnel_material.name) / _TUNNEL_CERTIFICATE_NAME
        self._server = _BoundaryServer(("127.0.0.1", 0), self)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def sensitive_token(self) -> str:
        return _REDACTION_PROBE_VALUE

    def configure(self, scenario: str) -> None:
        self.scenario = scenario
        self.response_html = None
        self.navigation_count = 0
        self.requested_urls.clear()
        self.request_started.clear()
        if scenario == "blocking":
            self.release_request.clear()
        else:
            self.release_request.set()

    def configure_html(self, html: str) -> None:
        """Serve caller-supplied captured HTML through the real HTTP route."""
        self.configure("captured-html")
        self.response_html = html

    def _local_url(self, path: str) -> str:
        host, port = cast("tuple[str, int]", self._server.server_address)
        return f"http://{host}:{port}{path}"

    @property
    def loopback_host(self) -> str:
        """The loopback address this boundary serves on."""
        return cast("tuple[str, int]", self._server.server_address)[0]

    @property
    def proxy_url(self) -> str:
        """This server as the browser's proxy, which carries every unrouted hop."""
        return self._local_url("")

    def stands_in_for(self, host: str) -> bool:
        """Report whether the tunnel serves ``host``, one of the domains this boundary fakes."""
        return any(host == domain or host.endswith(f".{domain}") for domain in _STOOD_IN_DOMAINS)

    def record_request(self, requested_url: str) -> str:
        """Record one browser request and return the local path that answers it."""
        with self._record_lock:
            self.navigation_count += 1
            self.requested_urls.append(requested_url)
            return self._local_path_for_request(requested_url)

    def _retry_path(self) -> str | None:
        scenario = self.scenario
        if scenario == "first-failure-then-success":
            return "/failure" if self.navigation_count == 1 else "/success"
        if scenario == "failure":
            return "/failure"
        if scenario == "blocking":
            return "/blocking"
        return None

    def _redirect_path(self, requested_url: str) -> str | None:
        scenario = self.scenario
        if scenario == "wrong-host":
            return "/redirect-wrong-host" if requested_url == AEAT_CERTIFICATE_PROTECTED_URL else "/success"
        if scenario == "wrong-path":
            return "/redirect-wrong-path" if requested_url == AEAT_CERTIFICATE_PROTECTED_URL else "/success"
        if scenario == "sensitive-error":
            return "/redirect-sensitive" if requested_url == AEAT_CERTIFICATE_PROTECTED_URL else "/disconnect"
        if scenario == "sensitive-redirect":
            return "/redirect-sensitive" if requested_url == AEAT_CERTIFICATE_PROTECTED_URL else "/success"
        return None

    def _retry_or_failure_path(self, requested_url: str) -> str | None:
        local_path = self._retry_path()
        if local_path is not None:
            return local_path
        return self._redirect_path(requested_url)

    def _clave_movil_path(self, requested_url: str) -> str | None:
        scenario = self.scenario
        if scenario == "clave-movil-pending":
            return (
                "/clave-movil-selector-pending"
                if _CLAVE_MOVIL.selector_access_path_marker in requested_url
                else "/clave-movil-pending"
            )
        if scenario not in {"clave-movil-representation", "clave-movil-representation-missing"}:
            return None
        if _CLAVE_MOVIL.selector_access_path_marker in requested_url:
            return "/clave-movil-selector-representation"
        if _CLAVE_MOVIL.dialogo_representacion_path_marker in requested_url:
            return (
                "/clave-movil-representation-missing"
                if scenario.endswith("-missing")
                else "/clave-movil-representation"
            )
        return "/clave-success"

    def _clave_permanente_path(self, requested_url: str) -> str | None:
        scenario = self.scenario
        if scenario == "clave-permanente-success":
            return (
                "/clave-permanente-form-success"
                if _CLAVE_PERMANENTE.selector_access_path_marker in requested_url
                else "/clave-success"
            )
        if scenario == "clave-permanente-invalid":
            return (
                "/clave-permanente-form-invalid"
                if _CLAVE_PERMANENTE.selector_access_path_marker in requested_url
                else "/clave-permanente-invalid"
            )
        return None

    def _local_path_for_request(self, requested_url: str) -> str:
        for resolver in (self._retry_or_failure_path, self._clave_movil_path, self._clave_permanente_path):
            local_path = resolver(requested_url)
            if local_path is not None:
                return local_path
        return "/success"

    async def route(self, route: Route) -> None:
        local_path = self.record_request(route.request.url)
        try:
            response = await route.fetch(
                url=self._local_url(local_path),
                max_redirects=0,
            )
        except PlaywrightError:
            await route.abort("failed")
            return
        await route.fulfill(response=response)

    async def wait_until_blocked(self) -> None:
        started = await asyncio.to_thread(self.request_started.wait, 10)
        if not started:
            raise AssertionError("real HTTP boundary did not observe the blocking navigation")

    def close(self) -> None:
        self.release_request.set()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
        self._tunnel_material.cleanup()


class RoutedStealthEvasion:
    """Apply production stealth and route navigation through a real local server."""

    def __init__(self, boundary: LocalHttpBoundary) -> None:
        self._boundary = boundary
        self._stealth = PlaywrightStealthEvasion()

    async def apply(self, context: BrowserContext) -> None:
        await self._stealth.apply(context)
        await context.route("**/*", self._boundary.route)


@asynccontextmanager
async def opened_http_boundary() -> AsyncGenerator[LocalHttpBoundary]:
    boundary = LocalHttpBoundary()
    try:
        yield boundary
    finally:
        boundary.close()


def real_browser_factory(
    *,
    boundary: LocalHttpBoundary,
    profile_name: str,
) -> BrowserSessionFactoryPort:
    """Return a factory composed entirely from the production browser adapters."""

    async def factory(settings: Settings) -> DefaultBrowserSession:
        playwright, session = await open_real_browser_session(
            boundary=boundary,
            settings=settings,
            profile_name=profile_name,
        )
        return DefaultBrowserSession(playwright=playwright, session=session)

    return factory


class _BoundaryTrustingBrowserSession(BrowserSession):
    """The production session, told to accept the boundary tunnel's own certificate.

    Every other request is fulfilled by the route and negotiates no TLS, so the
    only certificate this relaxes is the one minted for this boundary.
    """

    @override
    def _build_context_kwargs(
        self,
        *,
        storage_state: Mapping[str, object] | None,
        provisioner: BrowserContextProvisioner | None,
    ) -> dict[str, Any]:
        context_kwargs = super()._build_context_kwargs(storage_state=storage_state, provisioner=provisioner)
        context_kwargs["ignore_https_errors"] = True
        return context_kwargs


async def open_real_browser_session(
    *,
    boundary: LocalHttpBoundary,
    settings: Settings,
    profile_name: str,
) -> tuple[Playwright, BrowserSession]:
    """Open the canonical production session over the routed real boundary.

    The boundary is also the browser's proxy, through the production proxy
    settings, so a redirect hop the route never sees is still served locally;
    the route's own loopback fetches bypass it.

    The browser always launches headless. The routed pages are read by the
    test, never by a person, and a provider that asks for a visible window (a
    fresh Cl@ve Movil login, so the operator can scan its QR) would otherwise
    need a display server that a headless host does not have. That request is
    the provider's own contract and is pinned by the provider's unit tests.
    """
    playwright = await async_playwright().start()
    session = _BoundaryTrustingBrowserSession(
        playwright=playwright,
        settings=settings.model_copy(
            update={
                "cadrumo_browser_headless": True,
                "cadrumo_proxy_url": boundary.proxy_url,
                "cadrumo_proxy_bypass": boundary.loopback_host,
            }
        ),
        profile=Profile(name=profile_name),
        evasion_strategy=RoutedStealthEvasion(boundary),
    )
    return playwright, session


__all__ = [
    "LocalHttpBoundary",
    "RoutedStealthEvasion",
    "open_real_browser_session",
    "opened_http_boundary",
    "real_browser_factory",
]
