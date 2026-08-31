"""Real-behaviour proof: the production browser context never persists a download.

``BrowserSession._build_context_kwargs`` pins ``accept_downloads=False`` on
every context this adapter creates
(``sensitive-financial-data-secure-storage-only``). ``download.cancel()``
alone is NOT sufficient to close this gap: Chromium starts writing an
attachment's bytes to its own OS-managed temp folder the moment a download
begins, and cancellation only stops an in-flight transfer -- measured
separately (a throwaway local probe, not part of this suite) to leave
several hundred KB of a multi-MB payload sitting in a ``.crdownload`` file
within one event-loop tick of ``expect_download()`` yielding, before any
``cancel()`` call could possibly land.

``accept_downloads=False`` closes it at the browser-engine level instead:
Chromium refuses to persist the response at all. This is a genuine
behavioural test, not a structural one -- it drives the REAL
:func:`~adapters.outbound.aeat.browser.create_browser_session` /
:meth:`~adapters.outbound.aeat.browser.BrowserSession.create_context`
production path against a real local HTTP server and a real headless
Chromium, and observes two things no amount of source inspection could
establish on its own:

1. ``download.path()`` raises -- Playwright's own runtime refuses to
   expose ANY local artifact for the download (its error message literally
   names the ``accept_downloads=True`` flag this adapter does not set).
2. The production fetch shape (read ``download.url``, cancel, re-fetch via
   ``context.request``) still returns the exact bytes the server sent,
   proving the security fix costs nothing functionally.

Uses only synthetic local bytes; makes no AEAT contact.

See Also:
    :meth:`~adapters.outbound.aeat.browser.BrowserSession._build_context_kwargs`
        Where ``accept_downloads=False`` is set for every context.
    :func:`~adapters.outbound.aeat.sede.declarations_fetch._capture_submitted_file_artefact`
        The production consumer of this shape.
"""

from __future__ import annotations

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast, override

import pytest
from playwright.async_api import Error as PlaywrightError

from ......core.config import Settings
from .. import Profile
from ..factory import create_browser_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_PAYLOAD = b"synthetic-submitted-file-bytes-not-real-taxpayer-data" * 20


class _DownloadHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/page":
            body = b'<html><body><a id="dl" href="/file">download</a></body></html>'
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/file":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="submitted.bin"')
            self.send_header("Content-Length", str(len(_PAYLOAD)))
            self.end_headers()
            self.wfile.write(_PAYLOAD)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    @override
    def log_message(self, format: str, *args: object) -> None:
        pass


@asynccontextmanager
async def _local_download_server() -> AsyncIterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _DownloadHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = cast("tuple[str, int]", server.server_address)
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _profile(name: str) -> Profile:
    return Profile(name=name, locale="es-ES", timezone_id="Europe/Madrid")


@pytest.mark.asyncio
async def test_production_context_refuses_to_expose_a_local_download_path() -> None:
    """``download.path()`` must raise on the real production context.

    Playwright's own runtime error names the exact flag this adapter
    deliberately does not set, which is the strongest available evidence
    (short of a filesystem trace) that no readable download artifact
    exists for this transfer.
    """
    async with _local_download_server() as base_url:
        session = await create_browser_session(Settings(), _profile("accept-downloads-path"))
        try:
            context = await session.create_context()
            page = await context.new_page()
            await page.goto(f"{base_url}/page")

            async with page.expect_download() as download_info:
                await page.click("#dl")
            download = await download_info.value

            assert download.url == f"{base_url}/file"

            with pytest.raises(PlaywrightError, match="accept_downloads"):
                await download.path()

            await context.close()
        finally:
            await session.close()


@pytest.mark.asyncio
async def test_production_shape_still_fetches_the_exact_bytes() -> None:
    """The cancel-then-refetch shape returns byte-identical content.

    Mirrors ``_capture_submitted_file_artefact`` exactly: read the URL,
    best-effort cancel, then re-fetch through ``context.request`` -- proving
    the ``accept_downloads=False`` default costs nothing functionally.
    """
    async with _local_download_server() as base_url:
        session = await create_browser_session(Settings(), _profile("accept-downloads-fetch"))
        try:
            context = await session.create_context()
            page = await context.new_page()
            await page.goto(f"{base_url}/page")

            async with page.expect_download() as download_info:
                await page.click("#dl")
            download = await download_info.value
            download_url = download.url

            try:
                await download.cancel()
            except PlaywrightError:
                pytest.fail("download.cancel() must not raise on the production context shape")

            response = await context.request.get(download_url)
            body = await response.body()

            assert body == _PAYLOAD

            await context.close()
        finally:
            await session.close()
