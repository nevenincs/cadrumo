"""Mis Expedientes names the person an AEAT session belongs to, from a request that names nobody.

``resumen-vlt-modelo-100-expanded.html`` is a captured Mis Expedientes page
with its private values replaced by synthetic ones. The live reads run in real
headless Chromium behind the local HTTP boundary.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest

from ......application.auth.protocols import BrowserContextPort
from ......core.config import Settings
from ......tests.inventory import FIXTURES_DIR
from ...browser.tests.real_http_boundary import LocalHttpBoundary, open_real_browser_session, opened_http_boundary
from ..errors import SedeNavigationError
from ..signed_in_identity import parse_signed_in_nif, read_signed_in_nif

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_EXTERNAL = Settings.external_constants()
_EXPEDIENTES_URL = f"{_EXTERNAL.aeat.domains.www6}{_EXTERNAL.aeat.sede_paths.expedientes_resumen}"
_FIXTURES = FIXTURES_DIR / "aeat-sede"
_HOLDER_NIF = "00000000T"
_REPRESENTED_NIF = "12345678Z"


@asynccontextmanager
async def _context(boundary: LocalHttpBoundary, name: str) -> AsyncGenerator[BrowserContextPort]:
    playwright, session = await open_real_browser_session(boundary=boundary, settings=Settings(), profile_name=name)
    try:
        context = await session.create_context(storage_state={})
        try:
            yield context
        finally:
            await context.close()
    finally:
        await session.close()
        await playwright.stop()


def test_the_captured_page_names_its_persona_consultada() -> None:
    html = (_FIXTURES / "resumen-vlt-modelo-100-expanded.html").read_text(encoding="utf-8")

    assert parse_signed_in_nif(html) == "Y0000001Z"


def test_a_page_without_persona_consultada_names_nobody() -> None:
    html = (_FIXTURES / "censal-datos-mdcacceso.html").read_text(encoding="utf-8")

    assert parse_signed_in_nif(html) is None


@pytest.mark.asyncio
async def test_a_representatives_session_reads_as_the_representative() -> None:
    """The request names no taxpayer, so a power of attorney for one cannot change whom it shows."""
    async with opened_http_boundary() as boundary:
        boundary.signed_in_nif = _HOLDER_NIF
        boundary.represented_nif = _REPRESENTED_NIF
        async with _context(boundary, "signed-in-identity-representative") as context:
            observed = await read_signed_in_nif(context)

        assert observed == _HOLDER_NIF
        assert boundary.requested_urls == [_EXPEDIENTES_URL]


@pytest.mark.asyncio
async def test_a_landing_that_is_not_mis_expedientes_is_refused() -> None:
    async with opened_http_boundary() as boundary:
        boundary.configure("wrong-path")
        async with _context(boundary, "signed-in-identity-wrong-path") as context:
            with pytest.raises(SedeNavigationError):
                await read_signed_in_nif(context)
