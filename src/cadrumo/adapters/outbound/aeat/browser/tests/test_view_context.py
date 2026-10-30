"""The Sede view context, proven in real headless Chromium.

Each case opens the production :meth:`BrowserSession.create_view_context`.
Synthetic pages, Sede and off-host alike, are fulfilled by a context route
the evasion seam registers, so every request the browser sends reaches that
route and is recorded. The browser's proxy is a closed loopback port, so a
request no route answers cannot leave the host. The cases show that the
page-observer hook reports each event and that the view blocks nothing.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

import pytest
from playwright.async_api import (
    BrowserContext,
    Dialog,
    Download,
    FileChooser,
    Page,
    Route,
    WebSocketRoute,
    async_playwright,
)

from ......core.config import Settings
from ......tests.aeat_literal_fixtures import (
    VIEW_DOCUMENT_PATH_FIXTURE,
    VIEW_HOME_PATH_FIXTURE,
    VIEW_SUBMIT_PATH_CANARY,
    VIEW_UPLOAD_PATH_FIXTURE,
    VIEW_WORKER_PATH_FIXTURE,
)
from ..profile import Profile
from ..session import BrowserSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SEDE: Final[str] = Settings.external_constants().aeat.domains.sede
_OFF_HOST: Final[str] = "https://www.example.com"
#: A loopback port nothing listens on, so an unrouted request fails locally.
_CLOSED_PROXY: Final[str] = "http://127.0.0.1:9"
_EVENT_TIMEOUT_SECONDS: Final[float] = 10.0


@dataclass
class _SyntheticPages:
    """Fulfil synthetic pages for any host and record every request that reached them."""

    pages: dict[str, tuple[str, str]] = field(default_factory=dict)
    received: list[tuple[str, str]] = field(default_factory=list)

    def page(self, url: str, body: str, content_type: str = "text/html; charset=utf-8") -> str:
        self.pages[url] = (content_type, body)
        return url

    async def apply(self, context: BrowserContext) -> None:
        await context.route("**/*", self._fulfil)

    async def _fulfil(self, route: Route) -> None:
        request = route.request
        self.received.append((request.method, request.url))
        served = self.pages.get(request.url)
        if served is None:
            await route.fulfill(status=404, body="")
            return
        content_type, body = served
        await route.fulfill(status=200, content_type=content_type, body=body)

    def reached(self, method: str, url: str) -> bool:
        return (method, url) in self.received


@dataclass
class _RecordingObserver:
    """The page-observer hook, recording what the view would hand the panel."""

    pages: list[Page] = field(default_factory=list)
    popups: list[tuple[Page, Page]] = field(default_factory=list)
    downloads: list[Download] = field(default_factory=list)
    file_choosers: list[FileChooser] = field(default_factory=list)
    dialogs: list[Dialog] = field(default_factory=list)

    def page_opened(self, page: Page) -> None:
        self.pages.append(page)

    def popup_opened(self, popup: Page, opener: Page) -> None:
        self.popups.append((popup, opener))

    def download_started(self, page: Page, download: Download) -> None:
        del page
        self.downloads.append(download)

    def file_chooser_opened(self, page: Page, file_chooser: FileChooser) -> None:
        del page
        self.file_choosers.append(file_chooser)

    def dialog_opened(self, page: Page, dialog: Dialog) -> None:
        del page
        self.dialogs.append(dialog)


async def _until(predicate: Callable[[], bool]) -> None:
    async def poll() -> None:
        while not predicate():
            await asyncio.sleep(0.02)

    await asyncio.wait_for(poll(), timeout=_EVENT_TIMEOUT_SECONDS)


@asynccontextmanager
async def _view_context(
    tmp_path: Path, synthetic: _SyntheticPages
) -> AsyncGenerator[tuple[BrowserContext, _RecordingObserver]]:
    settings = Settings(
        cadrumo_storage_root=tmp_path,
        cadrumo_browser_headless=True,
        cadrumo_proxy_url=_CLOSED_PROXY,
    )
    observer = _RecordingObserver()
    async with async_playwright() as playwright:
        session = BrowserSession(playwright, settings, Profile(name="sede-view"), evasion_strategy=synthetic)
        try:
            context = await session.create_view_context(observer=observer)
            try:
                yield context, observer
            finally:
                await context.close()
        finally:
            await session.close()


async def _open_page(context: BrowserContext, observer: _RecordingObserver, url: str) -> Page:
    page = await context.new_page()
    await _until(lambda: page in observer.pages)
    await page.goto(url)
    return page


async def _titled(page: Page, title: str) -> None:
    await page.wait_for_function(f"document.title === {title!r}", timeout=_EVENT_TIMEOUT_SECONDS * 1000)


@pytest.mark.asyncio
async def test_view_reports_a_page_opened_by_code(tmp_path: Path) -> None:
    synthetic = _SyntheticPages()
    start = synthetic.page(f"{_SEDE}{VIEW_HOME_PATH_FIXTURE}", "<title>sede</title>")
    async with _view_context(tmp_path, synthetic) as (context, observer):
        page = await _open_page(context, observer, start)
        assert await page.title() == "sede"
        assert observer.pages == [page]
        assert observer.popups == []


@pytest.mark.asyncio
async def test_view_reports_a_popup_and_leaves_it_open(tmp_path: Path) -> None:
    synthetic = _SyntheticPages()
    target = synthetic.page(f"{_OFF_HOST}/popup", "<title>popup</title>")
    start = synthetic.page(f"{_SEDE}{VIEW_HOME_PATH_FIXTURE}", f'<a id="go" target="_blank" href="{target}">go</a>')
    async with _view_context(tmp_path, synthetic) as (context, observer):
        page = await _open_page(context, observer, start)
        await page.click("#go")
        await _until(lambda: len(observer.popups) == 1)
        popup, opener = observer.popups[0]
        assert opener is page
        assert popup not in observer.pages
        await _titled(popup, "popup")
        assert popup.url == target
        assert not popup.is_closed()
        assert synthetic.reached("GET", target)


@pytest.mark.asyncio
async def test_view_reports_a_download(tmp_path: Path) -> None:
    synthetic = _SyntheticPages()
    target = synthetic.page(f"{_SEDE}{VIEW_DOCUMENT_PATH_FIXTURE}", "%PDF-1.4 synthetic", "application/pdf")
    start = synthetic.page(f"{_SEDE}{VIEW_HOME_PATH_FIXTURE}", f'<a id="go" download="j.pdf" href="{target}">go</a>')
    async with _view_context(tmp_path, synthetic) as (context, observer):
        page = await _open_page(context, observer, start)
        await page.click("#go")
        await _until(lambda: len(observer.downloads) == 1)
        assert observer.downloads[0].url == target
        assert observer.downloads[0].suggested_filename == "j.pdf"


@pytest.mark.asyncio
async def test_view_reports_a_file_chooser_the_observer_can_answer(tmp_path: Path) -> None:
    synthetic = _SyntheticPages()
    start = synthetic.page(
        f"{_SEDE}{VIEW_UPLOAD_PATH_FIXTURE}",
        """<input id="file" type="file" onchange="document.title = 'chosen:' + this.files[0].name">""",
    )
    async with _view_context(tmp_path, synthetic) as (context, observer):
        page = await _open_page(context, observer, start)
        await page.click("#file")
        await _until(lambda: len(observer.file_choosers) == 1)
        await observer.file_choosers[0].set_files(
            {"name": "aportacion.txt", "mimeType": "text/plain", "buffer": b"synthetic"}
        )
        await _titled(page, "chosen:aportacion.txt")


@pytest.mark.asyncio
async def test_view_reports_a_dialog_the_observer_can_answer(tmp_path: Path) -> None:
    synthetic = _SyntheticPages()
    start = synthetic.page(
        f"{_SEDE}{VIEW_HOME_PATH_FIXTURE}",
        """<button id="ask" onclick="document.title = confirm('seguir') ? 'accepted' : 'dismissed'">ask</button>""",
    )
    async with _view_context(tmp_path, synthetic) as (context, observer):
        page = await _open_page(context, observer, start)
        click = asyncio.ensure_future(page.click("#ask"))
        await _until(lambda: len(observer.dialogs) == 1)
        assert observer.dialogs[0].type == "confirm"
        await observer.dialogs[0].accept()
        await click
        await _titled(page, "accepted")


@pytest.mark.asyncio
async def test_view_blocks_no_request(tmp_path: Path) -> None:
    """POSTs, token-bearing URLs, off-host requests and service workers all reach the server."""
    synthetic = _SyntheticPages()
    posted = synthetic.page(f"{_SEDE}{VIEW_SUBMIT_PATH_CANARY}", "<title>posted</title>")
    image = synthetic.page(f"{_OFF_HOST}/pixel.png", "", "image/png")
    worker = synthetic.page(
        f"{_SEDE}{VIEW_WORKER_PATH_FIXTURE}", "self.addEventListener('fetch', () => {});", "text/javascript"
    )
    start = synthetic.page(
        f"{_SEDE}{VIEW_HOME_PATH_FIXTURE}",
        f"""<img src="{image}">
        <form id="f" method="post" action="{posted}"><input name="q" value="1"></form>
        <script>
        navigator.serviceWorker.register('{VIEW_WORKER_PATH_FIXTURE}')
            .then(() => navigator.serviceWorker.getRegistrations())
            .then((registrations) => {{ document.title = 'registrations:' + registrations.length; }});
        </script>""",
    )
    async with _view_context(tmp_path, synthetic) as (context, observer):
        page = await _open_page(context, observer, start)
        await _titled(page, "registrations:1")
        assert synthetic.reached("GET", image)
        assert synthetic.reached("GET", worker)
        await page.locator("#f").evaluate("form => form.submit()")
        await _titled(page, "posted")
        assert synthetic.reached("POST", posted)


@pytest.mark.asyncio
async def test_view_leaves_websockets_open(tmp_path: Path) -> None:
    synthetic = _SyntheticPages()
    socket_url = f"wss://{urlsplit(_SEDE).netloc}/socket"
    start = synthetic.page(
        f"{_SEDE}{VIEW_HOME_PATH_FIXTURE}",
        f"""<script>
        const socket = new WebSocket('{socket_url}');
        socket.onmessage = (event) => {{ document.title = 'message:' + event.data; }};
        socket.onclose = () => {{ document.title = 'closed'; }};
        </script>""",
    )
    opened: list[str] = []

    def stand_in_server(web_socket: WebSocketRoute) -> None:
        opened.append(web_socket.url)
        web_socket.send("hola")

    async with _view_context(tmp_path, synthetic) as (context, observer):
        # The stand-in server answers the socket the browser opens; the view
        # itself installs no WebSocket handling.
        await context.route_web_socket(socket_url, stand_in_server)
        page = await _open_page(context, observer, start)
        await _titled(page, "message:hola")
        assert opened == [socket_url]
