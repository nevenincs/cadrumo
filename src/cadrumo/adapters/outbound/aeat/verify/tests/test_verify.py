"""Real-browser and pure-parser proofs for AEAT CSV verification."""

from __future__ import annotations

from typing import cast

import pytest
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Playwright

from ......core.config import Settings
from ......domain.calculations.registry.errors import RegistryValidationError
from ...browser.factory import DefaultBrowserSession
from ...browser.tests.real_http_boundary import (
    open_real_browser_session,
    opened_http_boundary,
)
from .. import contract as verify_module
from ..contract import verify_csv

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_CSV = "ABCD1234EFGH5678"
_AEAT = Settings.external_constants().aeat
_RESULT_URL = f"{_AEAT.domains.www2}{_AEAT.sede_paths.cotejo_query}?CSV={_CSV}"


def _viewer_html(csv: str, *, origin: str = "") -> str:
    source = f"{origin}{_AEAT.sede_paths.cotejo_document}?CSV={csv}"
    return (
        '<title>Visualización de documentos</title><button id="botonPantallaCompleta"></button>'
        f'<iframe id="iframe-visualiza" src="{source}"></iframe>'
    )


@pytest.mark.parametrize(
    "body, expected",
    [
        (_viewer_html(_CSV), True),
        (_viewer_html(_CSV, origin=_AEAT.domains.www2), True),
        (_viewer_html(_CSV, origin="https://attacker.example"), False),
        (_viewer_html("WRONG12345678901"), False),
        ("<html><p>CSV incorrecto.</p></html>", False),
        ("<html><p>Documento no válido.</p></html>", False),
        ("<html><p>Documento no valido.</p></html>", False),
        ("<html><p>El documento no es válido.</p></html>", False),
        ("<html><p>Para el correcto funcionamiento de la sede.</p></html>", False),
        ("<html><p>Documento válido en el Registro General.</p></html>", False),
        (
            "<p>No se ha podido recuperar ningún documento catalogado con ese CSV (Código Seguro de Verificación).</p>",
            False,
        ),
        ("<p>No se ha encontrado ningún documento con los datos aportados.</p>", False),
        ("<html><p>El CSV no se encuentra en el registro.</p></html>", False),
        ("", False),
    ],
)
def test_verify_csv_parse_contract(body: str, expected: bool) -> None:
    """Only the exact CSV-bound document iframe satisfies the official contract."""
    assert verify_module._response_confirms_valid_csv(body, expected_csv=_CSV, final_url=_RESULT_URL) is expected


@pytest.mark.parametrize(
    "final_url",
    [
        f"https://attacker.example{_AEAT.sede_paths.cotejo_query}?CSV={_CSV}",
        f"{_AEAT.domains.www2}{_AEAT.sede_paths.cotejo_document}?CSV={_CSV}",
        f"{_AEAT.domains.www2.replace('https://', 'http://')}{_AEAT.sede_paths.cotejo_query}?CSV={_CSV}",
    ],
)
def test_verify_csv_rejects_wrong_final_surface(final_url: str) -> None:
    """A viewer-shaped body cannot override wrong scheme, host, or route."""
    assert not verify_module._response_confirms_valid_csv(
        _viewer_html(_CSV),
        expected_csv=_CSV,
        final_url=final_url,
    )


@pytest.mark.asyncio
async def test_verify_csv_keeps_borrowed_real_browser_available() -> None:
    """Borrowed ownership leaves the connected browser usable by its caller."""
    async with opened_http_boundary() as boundary:
        playwright, session = await open_real_browser_session(
            boundary=boundary,
            settings=Settings(),
            profile_name="verify-borrowed",
        )
        second_context = None
        try:
            concrete_session = session
            assert verify_module._is_verify_browser_session_like(session)
            assert await verify_csv(" abcd1234 ", browser=session) is False

            browser = concrete_session._browser
            assert browser is not None
            assert browser.is_connected()
            second_context = await browser.new_context()
            page = await second_context.new_page()
            await page.goto("data:text/html,<title>borrowed-still-open</title>")
            assert await page.title() == "borrowed-still-open"
        finally:
            if second_context is not None:
                await second_context.close()
            await session.close()
            await playwright.stop()


@pytest.mark.asyncio
async def test_verify_csv_closes_self_owned_real_playwright_runtime() -> None:
    """The self-owned path stops its actual Playwright runtime after use."""
    async with opened_http_boundary() as boundary:
        retained_runtime: Playwright | None = None

        async def factory() -> verify_module.VerifyBrowserSessionLike:
            nonlocal retained_runtime
            playwright, session = await open_real_browser_session(
                boundary=boundary,
                settings=Settings(),
                profile_name="verify-self-owned",
            )
            retained_runtime = playwright
            return cast(
                verify_module.VerifyBrowserSessionLike,
                DefaultBrowserSession(playwright=playwright, session=session),
            )

        assert await verify_csv("ABCD1234EFGH5678", browser_session_factory=factory) is False
        assert retained_runtime is not None
        with pytest.raises(PlaywrightError):
            await retained_runtime.chromium.launch(headless=True)


def test_verify_browser_session_type_guard_rejects_incompatible_object() -> None:
    """The production type guard rejects objects without the session contract."""
    assert not verify_module._is_verify_browser_session_like(object())


def test_browser_adapter_type_error_is_registered() -> None:
    """The adapter mismatch remains bound to the central error registry."""
    from ......core.errors.error_codes import ERROR_REGISTRY

    assert "ERROR_SEDE_BROWSER_ADAPTER_TYPE" in ERROR_REGISTRY


def test_browser_adapter_type_error_round_trips_build_error_envelope() -> None:
    """The registered adapter mismatch builds a typed public envelope."""
    from ......core.errors.error_codes import build_error_envelope
    from ...sede.errors import BrowserAdapterTypeError

    exc = BrowserAdapterTypeError("default_browser_session_factory returned an incompatible type")
    envelope = build_error_envelope(exc)

    assert envelope.code == "ERROR_SEDE_BROWSER_ADAPTER_TYPE"
    assert envelope.category == "ERROR"


def test_verify_csv_guard_rejects_non_read_method() -> None:
    with pytest.raises(RegistryValidationError, match="remote write method"):
        verify_module._assert_verify_http("POST", verify_module._VERIFY_URL)


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_verify_guard_refuses_every_write_method(method: str) -> None:
    """The verifier stays read-only: no write verb reaches the reviewed URL.

    Guarded explicitly because the cotejo verdict is now stamped onto a
    persisted capture, which gives the adapter a production caller for the
    first time. The caller may consume the answer; it may not widen how the
    answer is obtained.
    """
    with pytest.raises(RegistryValidationError, match="remote write method"):
        verify_module._assert_verify_http(method, verify_module._VERIFY_URL)


@pytest.mark.parametrize(
    "url",
    [
        f"https://attacker.example{_AEAT.sede_paths.cotejo_query}?CSV={_CSV}",
        f"{_AEAT.domains.www1}{_AEAT.sede_paths.cotejo_query}?CSV={_CSV}",
    ],
)
def test_verify_guard_refuses_a_host_outside_the_reviewed_surface(url: str) -> None:
    """Only the single reviewed cotejo host is reachable, on a read verb too."""
    with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
        verify_module._assert_verify_http("GET", url)
