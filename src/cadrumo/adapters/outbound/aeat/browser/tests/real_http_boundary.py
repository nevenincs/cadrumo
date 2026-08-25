"""Credential-free real HTTP and Playwright boundary for adapter tests."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final, cast, override
from urllib.parse import urlsplit

from playwright.async_api import BrowserContext, Playwright, Route, async_playwright
from playwright.async_api import Error as PlaywrightError

from ......application.auth.protocols import BrowserSessionFactoryPort
from ......core.config import AEAT_CERTIFICATE_PROTECTED_PATH, AEAT_CERTIFICATE_PROTECTED_URL, Settings
from .. import BrowserSession, DefaultBrowserSession, PlaywrightStealthEvasion, Profile

_EXTERNAL = Settings.external_constants()
_DOMAINS = _EXTERNAL.aeat.domains
_CLAVE_MOVIL = _EXTERNAL.aeat.clave_movil
_CLAVE_PERMANENTE = _EXTERNAL.aeat.clave_permanente
_PRE303 = _EXTERNAL.aeat.pre303
_PROTECTED_PARENT = AEAT_CERTIFICATE_PROTECTED_PATH.rpartition("/")[0]
_WRONG_HOST_URL: Final[str] = f"{_DOMAINS.www1}{AEAT_CERTIFICATE_PROTECTED_PATH}"
_WRONG_PATH_URL: Final[str] = f"{_DOMAINS.www6}{_PROTECTED_PARENT}/OtroRecurso"
_REDACTION_PROBE_VALUE: Final[str] = "certificate-query-7e2b"
_SENSITIVE_URL: Final[str] = f"{_DOMAINS.www6}{_PROTECTED_PARENT}/Interrumpido?probe={_REDACTION_PROBE_VALUE}"
_MOVIL_QR_URL: Final[str] = f"{_DOMAINS.www12}{_CLAVE_MOVIL.obtener_clave_movil_qr_path}"
_REPRESENTATION_URL: Final[str] = f"{_DOMAINS.www6}{_CLAVE_MOVIL.dialogo_representacion_path}"
_PRE303_TARGET_URL: Final[str] = f"{_DOMAINS.www1}{_PRE303.presentation_service_path}"
_PERMANENTE_IDP_URL: Final[str] = f"https://se-pasarela.{urlsplit(_DOMAINS.clave).netloc}/idp/login"
_DEFAULT_CLAVE_TARGET_URL: Final[str] = f"{_DOMAINS.www6}{_EXTERNAL.aeat.sede_paths.expedientes_resumen}"


class _BoundaryServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], boundary: LocalHttpBoundary) -> None:
        self.boundary = boundary
        super().__init__(server_address, _BoundaryHandler)


class _BoundaryHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
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
        requested_url = route.request.url
        self.navigation_count += 1
        self.requested_urls.append(requested_url)
        local_path = self._local_path_for_request(requested_url)
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


class RoutedStealthEvasion:
    """Apply production stealth and route navigation through a real local server."""

    def __init__(self, boundary: LocalHttpBoundary) -> None:
        self._boundary = boundary
        self._stealth = PlaywrightStealthEvasion()

    async def apply(self, context: BrowserContext) -> None:
        await self._stealth.apply(context)
        await context.route("**/*", self._boundary.route)


@asynccontextmanager
async def opened_http_boundary() -> AsyncIterator[LocalHttpBoundary]:
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


async def open_real_browser_session(
    *,
    boundary: LocalHttpBoundary,
    settings: Settings,
    profile_name: str,
) -> tuple[Playwright, BrowserSession]:
    """Open the canonical production session over the routed real boundary."""
    playwright = await async_playwright().start()
    session = BrowserSession(
        playwright=playwright,
        settings=settings,
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
