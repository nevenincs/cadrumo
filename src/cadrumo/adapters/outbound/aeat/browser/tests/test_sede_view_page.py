"""The Sede view's browser driver, proven in real headless Chromium.

Each case opens :class:`SedeViewPage` on the production view context of a
real :class:`BrowserSession`. Synthetic pages stand in for the Sede through
the evasion seam's context route, and the browser's proxy is a closed
loopback port, so no request leaves the host. The stream is a recording
stand-in: its relay to the window has its own runtime tests.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import pytest
from playwright.async_api import BrowserContext, Page, Route, async_playwright

from cadrumo_client.contracts.view_stream import (
    VIEW_MAX_URL_LENGTH,
    ViewClose,
    ViewClosedReason,
    ViewPageSecurity,
    ViewPhase,
    ViewResize,
    ViewState,
)
from cadrumo_client.contracts.view_transfer import (
    ViewDownload,
    ViewDownloadAnswer,
    ViewDownloadOutcome,
    ViewFileChooser,
    ViewFileChooserAnswer,
    ViewFileChooserOutcome,
    ViewUploadCancelled,
    ViewUploadedFile,
)

from ......application.live.sede_view_ports import SedeViewEnd, SedeViewOpening
from ......core.config import Settings
from ......tests.component_record_support import record_shared_browser
from ..profile import Profile
from ..sede_view import SedeViewPage, safe_filename, view_state
from ..session import BrowserSession
from .view_page_support import RecordingViewSink, until

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SEDE: Final[str] = Settings.external_constants().aeat.domains.sede.rstrip("/")
_CLOSED_PROXY: Final[str] = "http://127.0.0.1:9"
_PAYLOAD: Final[bytes] = b"%PDF-1.4 synthetic justificante " + bytes(range(256)) * 300


@dataclass
class _Site:
    """Synthetic pages for the stood-in Sede, with optional response headers."""

    pages: dict[str, tuple[str, bytes, dict[str, str]]] = field(default_factory=dict)

    def page(self, path: str, body: str) -> str:
        url = f"{_SEDE}{path}"
        self.pages[url] = ("text/html; charset=utf-8", body.encode(), {})
        return url

    def file(self, path: str, data: bytes) -> str:
        url = f"{_SEDE}{path}"
        self.pages[url] = ("application/pdf", data, {"content-disposition": 'attachment; filename="justificante.pdf"'})
        return url

    async def apply(self, context: BrowserContext) -> None:
        await context.route("**/*", self._fulfil)

    async def _fulfil(self, route: Route) -> None:
        served = self.pages.get(route.request.url)
        if served is None:
            await route.fulfill(status=404, body="")
            return
        content_type, body, headers = served
        await route.fulfill(status=200, content_type=content_type, body=body, headers=headers)


@dataclass
class _Running:
    view: SedeViewPage
    sink: RecordingViewSink
    browsing: asyncio.Task[SedeViewEnd]
    stop: list[bool]

    @property
    def page(self) -> Page:
        return self.view.context.pages[0]


@asynccontextmanager
async def _view(tmp_path: Path, site: _Site) -> AsyncGenerator[_Running]:
    settings = Settings(
        cadrumo_local_storage_root=tmp_path, cadrumo_browser_headless=True, cadrumo_proxy_url=_CLOSED_PROXY
    )
    record_shared_browser(settings)
    sink = RecordingViewSink()
    opening = SedeViewOpening(
        settings=settings,
        sink=sink,
        viewport=ViewResize(css_width=640, css_height=480, scale=1.0),
        storage_state={"cookies": [], "origins": []},
        provisioner=None,
    )
    async with async_playwright() as playwright:
        session = BrowserSession(playwright, settings, Profile(name="sede-view"), evasion_strategy=site)
        try:
            view = await SedeViewPage.open(session, None, opening)
            stop = [False]
            browsing = asyncio.ensure_future(view.browse(stop_requested=lambda: stop[0]))
            try:
                yield _Running(view=view, sink=sink, browsing=browsing, stop=stop)
            finally:
                stop[0] = True
                await asyncio.wait_for(browsing, timeout=10)
                await view.close()
        finally:
            await session.close()


def _home(site: _Site, body: str) -> None:
    site.page("", body)
    site.page("/", body)


def _files_holding(root: Path, data: bytes) -> list[Path]:
    return [path for path in root.rglob("*") if path.is_file() and data[:64] in path.read_bytes()]


def _transient_downloads(root: Path) -> list[Path]:
    """The browser's own download files that hold the payload; the rest of its profile stays locked while it runs."""
    return [path for path in root.rglob("artifacts/*") if path.is_file() and path.read_bytes() == _PAYLOAD]


@pytest.mark.asyncio
async def test_sede_view_opens_the_sede_home_and_draws_its_state(tmp_path: Path) -> None:
    site = _Site()
    _home(site, "<title>Inicio sintetico</title><p>sede</p>")
    async with _view(tmp_path, site) as running:
        await until(lambda: any(state.title == "Inicio sintetico" for state in running.sink.of(ViewState)))
        await until(lambda: len(running.sink.images) >= 1)
        state = next(state for state in running.sink.of(ViewState) if state.title == "Inicio sintetico")
        assert state.origin == _SEDE and state.path == "/" and state.phase is ViewPhase.BROWSING
        sequences = [image.sequence for image in running.sink.images]
        assert sequences == sorted(set(sequences))


@pytest.mark.asyncio
async def test_sede_view_streams_an_accepted_download_to_the_window_and_keeps_no_copy(tmp_path: Path) -> None:
    site = _Site()
    target = site.file("/wlpl/justificante.pdf", _PAYLOAD)
    _home(site, f'<a id="go" href="{target}">justificante</a>')
    async with _view(tmp_path, site) as running:
        await running.page.wait_for_selector("#go")
        await running.page.click("#go")
        await until(lambda: len(running.sink.of(ViewDownload)) == 1)
        offer = running.sink.of(ViewDownload)[0]
        assert offer.filename == "justificante.pdf"
        running.sink.put(ViewDownloadAnswer(transfer_id=offer.transfer_id, outcome=ViewDownloadOutcome.ACCEPTED))
        await until(lambda: offer.transfer_id in running.sink.downloaded)
        assert running.sink.downloaded[offer.transfer_id] == _PAYLOAD
    assert _files_holding(tmp_path, _PAYLOAD) == []


@pytest.mark.asyncio
async def test_sede_view_states_a_page_off_https_without_the_address_it_left(tmp_path: Path) -> None:
    site = _Site()
    plain = "http://plain.example.test/form?nif=synthetic"
    site.pages[plain] = ("text/html; charset=utf-8", b"<title>Sin cifrar</title>", {})
    _home(site, f'<title>Inicio</title><a id="plain" href="{plain}">fuera</a>')
    async with _view(tmp_path, site) as running:
        await until(lambda: any(state.title == "Inicio" for state in running.sink.of(ViewState)))
        await running.page.wait_for_selector("#plain")
        before = len(running.sink.of(ViewState))
        await running.page.click("#plain")
        await until(
            lambda: any(
                state.security is ViewPageSecurity.INSECURE and not state.loading
                for state in running.sink.of(ViewState)[before:]
            )
        )
        left = running.sink.of(ViewState)[before:]
        # Every state since the move is the marker alone: nothing of either page's address.
        assert [state.security for state in left if state.origin is not None] == []
        assert all(state.address is None and state.path is None for state in left)
        assert left[-1].title == "Sin cifrar"
        before = len(running.sink.of(ViewState))
        await running.page.goto("data:text/html,<title>datos</title>")
        await until(
            lambda: any(state.security is ViewPageSecurity.UNKNOWN for state in running.sink.of(ViewState)[before:])
        )


@pytest.mark.asyncio
async def test_sede_view_close_deletes_a_download_still_streaming(tmp_path: Path) -> None:
    site = _Site()
    target = site.file("/wlpl/justificante.pdf", _PAYLOAD)
    _home(site, f'<a id="go" href="{target}">justificante</a>')
    async with _view(tmp_path, site) as running:
        running.sink.stall_downloads = True
        try:
            await running.page.wait_for_selector("#go")
            await running.page.click("#go")
            await until(lambda: len(running.sink.of(ViewDownload)) == 1)
            offer = running.sink.of(ViewDownload)[0]
            running.sink.put(ViewDownloadAnswer(transfer_id=offer.transfer_id, outcome=ViewDownloadOutcome.ACCEPTED))
            await until(lambda: offer.transfer_id in running.sink.streaming)
            # The browser's transient file is on disk and open while its bytes stream.
            assert _transient_downloads(tmp_path) != []
            running.stop[0] = True
            await asyncio.wait_for(running.browsing, timeout=10)
            await asyncio.wait_for(running.view.close(), timeout=10)
            # Gone before the stream itself ends, so no later cleanup can be what removed it.
            assert _transient_downloads(tmp_path) == []
            assert running.sink.cancelled_downloads == [offer.transfer_id]
        finally:
            running.sink.close(ViewClosedReason.CANCELLED)
    assert _files_holding(tmp_path, _PAYLOAD) == []


@pytest.mark.asyncio
async def test_sede_view_hands_an_uploaded_file_to_the_page_from_memory(tmp_path: Path) -> None:
    site = _Site()
    _home(site, """<input id="file" type="file" onchange="document.title = 'chosen:' + this.files[0].size">""")
    upload = b"synthetic aportacion " * 50
    async with _view(tmp_path, site) as running:
        await running.page.wait_for_selector("#file")
        await running.page.click("#file")
        await until(lambda: len(running.sink.of(ViewFileChooser)) == 1)
        chooser = running.sink.of(ViewFileChooser)[0]
        assert not chooser.multiple
        running.sink.put(
            ViewFileChooserAnswer(chooser_id=chooser.chooser_id, outcome=ViewFileChooserOutcome.SUPPLIED, file_count=1)
        )
        running.sink.put(ViewUploadedFile(chooser_id=chooser.chooser_id, name="a.txt", mime="text/plain", data=upload))
        page = running.page
        await asyncio.wait_for(_titled(page, f"chosen:{len(upload)}"), timeout=10)
    assert _files_holding(tmp_path, upload) == []


@pytest.mark.asyncio
async def test_sede_view_cancelling_one_upload_leaves_the_other_chooser_waiting(tmp_path: Path) -> None:
    site = _Site()
    _home(
        site,
        """<input id="a" type="file" onchange="document.title = 'a:' + this.files[0].size">"""
        """<input id="b" type="file" onchange="document.title = 'b:' + this.files[0].size">""",
    )
    upload = b"synthetic aportacion " * 20
    async with _view(tmp_path, site) as running:
        page = running.page
        await page.wait_for_selector("#b")
        await page.click("#a")
        await until(lambda: len(running.sink.of(ViewFileChooser)) == 1)
        await page.click("#b")
        await until(lambda: len(running.sink.of(ViewFileChooser)) == 2)
        first, second = running.sink.of(ViewFileChooser)
        for chooser in (first, second):
            running.sink.put(
                ViewFileChooserAnswer(
                    chooser_id=chooser.chooser_id, outcome=ViewFileChooserOutcome.SUPPLIED, file_count=1
                )
            )
        running.sink.put(ViewUploadCancelled(chooser_id=first.chooser_id))
        running.sink.put(ViewUploadedFile(chooser_id=first.chooser_id, name="a.txt", mime="text/plain", data=upload))
        running.sink.put(ViewUploadedFile(chooser_id=second.chooser_id, name="b.txt", mime="text/plain", data=upload))
        await asyncio.wait_for(_titled(page, f"b:{len(upload)}"), timeout=10)
        assert await page.evaluate("document.getElementById('a').files.length") == 0


async def _titled(page: Page, title: str) -> None:
    while await page.title() != title:
        await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_sede_view_shows_a_popup_and_returns_to_its_opener_when_it_closes(tmp_path: Path) -> None:
    site = _Site()
    popup_url = site.page("/popup.html", "<title>Ventana emergente</title>")
    _home(site, f'<title>Inicio</title><a id="go" target="_blank" href="{popup_url}">abrir</a>')
    async with _view(tmp_path, site) as running:
        await running.page.wait_for_selector("#go")
        await running.page.click("#go")
        await until(lambda: any(state.path == "/popup.html" for state in running.sink.of(ViewState)))
        popup = running.view.context.pages[1]
        before = len(running.sink.of(ViewState))
        await popup.close()
        await until(lambda: any(state.path == "/" for state in running.sink.of(ViewState)[before:]))
        assert not running.browsing.done()


@pytest.mark.asyncio
async def test_sede_view_ends_on_the_windows_close_and_on_its_last_page_closing(tmp_path: Path) -> None:
    site = _Site()
    _home(site, "<title>Inicio</title>")
    async with _view(tmp_path, site) as running:
        running.sink.put(ViewClose())
        assert await asyncio.wait_for(running.browsing, timeout=10) is SedeViewEnd.CLOSED
    async with _view(tmp_path, site) as running:
        await running.page.close()
        assert await asyncio.wait_for(running.browsing, timeout=10) is SedeViewEnd.PAGE_LOST


@pytest.mark.asyncio
async def test_sede_view_without_input_keeps_browsing_until_it_is_stopped(tmp_path: Path) -> None:
    site = _Site()
    _home(site, "<title>Inicio</title>")
    async with _view(tmp_path, site) as running:
        await asyncio.sleep(2)
        assert not running.browsing.done()
        running.stop[0] = True
        assert await asyncio.wait_for(running.browsing, timeout=10) is SedeViewEnd.STOPPED


def test_sede_view_state_keeps_origin_and_path_only() -> None:
    state = view_state(
        "https://Sede.Example.ES:8443/a/b?nif=synthetic#frag",
        "t",
        back=True,
        forward=False,
        loading=False,
        phase=ViewPhase.BROWSING,
    )
    assert state.security is ViewPageSecurity.SECURE
    assert (state.origin, state.path) == ("https://sede.example.es:8443", "/a/b")
    # A URL whose host does not read as its origin carries no address.
    assert state.address is None


def test_sede_view_state_marks_a_page_it_cannot_state_and_names_no_address() -> None:
    for url, security in (
        ("http://sede.example.es/Sede/inicio.html?nif=synthetic", ViewPageSecurity.INSECURE),
        ("about:blank", ViewPageSecurity.UNKNOWN),
        ("data:text/html,<p>x</p>", ViewPageSecurity.UNKNOWN),
        ("chrome-error://chromewebdata/", ViewPageSecurity.UNKNOWN),
        ("https://[::1/", ViewPageSecurity.UNKNOWN),
        ("", ViewPageSecurity.UNKNOWN),
    ):
        state = view_state(url, "t", back=True, forward=False, loading=False, phase=ViewPhase.BROWSING)
        assert state.security is security, url
        assert (state.origin, state.path, state.address) == (None, None, None), url
        assert state.can_go_back


def test_sede_view_state_carries_the_whole_address_for_the_host() -> None:
    url = "https://sede.example.es/wlpl/BUGC-JDIT/Consulta?ejercicio=2025&modelo=303#resumen"
    state = view_state(url, "t", back=False, forward=False, loading=False, phase=ViewPhase.BROWSING)
    assert (state.origin, state.path, state.address) == (
        "https://sede.example.es",
        "/wlpl/BUGC-JDIT/Consulta",
        url,
    )
    long_query = "https://sede.example.es/x?q=" + "a" * VIEW_MAX_URL_LENGTH
    state = view_state(long_query, "t", back=False, forward=False, loading=False, phase=ViewPhase.BROWSING)
    assert (state.path, state.address) == ("/x", None)


def test_sede_view_download_names_are_plain_file_names() -> None:
    assert safe_filename("../../etc/passwd") == ".._.._etc_passwd"
    assert safe_filename("a\\b\x00c.pdf") == "a_b_c.pdf"
    assert safe_filename("..") == "download"
    assert len(safe_filename("x" * 400)) == 255
