"""The Sede view context's request guard, proven in real headless Chromium.

Each case opens the production :meth:`BrowserSession.create_view_context`
with the real operator-view guard. Synthetic Sede pages are fulfilled by a
context route registered before the guard, so the guard runs first and only
an admitted request reaches the synthetic server. The browser's proxy is a
closed loopback port, so a request no route answers cannot leave the host.
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
from playwright.async_api import BrowserContext, Page, Route, async_playwright
from playwright.async_api import Error as PlaywrightError

from ......core.config import Settings
from ......tests.component_record_support import record_shared_browser
from ..profile import Profile
from ..request_guard import (
    ContextRequestGuard,
    ViewNotice,
    ViewNoticeCode,
    operator_view_request_guard,
)
from ..session import BrowserSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_DOMAINS = Settings.external_constants().aeat.domains
_SEDE: Final[str] = _DOMAINS.sede
_OFF_HOST: Final[str] = "https://www.example.com"
#: A loopback port nothing listens on, so an unrouted request fails locally.
_CLOSED_PROXY: Final[str] = "http://127.0.0.1:9"
_EVENT_TIMEOUT_SECONDS: Final[float] = 10.0


@dataclass
class _SyntheticSede:
    """Fulfil synthetic pages for the stood-in hosts and record what reached it."""

    pages: dict[str, tuple[str, str]] = field(default_factory=dict)
    redirects: dict[str, str] = field(default_factory=dict)
    received: list[tuple[str, str]] = field(default_factory=list)

    def page(self, url: str, body: str, content_type: str = "text/html; charset=utf-8") -> str:
        self.pages[url] = (content_type, body)
        return url

    def redirect(self, url: str, location: str) -> str:
        self.redirects[url] = location
        return url

    async def apply(self, context: BrowserContext) -> None:
        await context.route("**/*", self._fulfil)

    async def _fulfil(self, route: Route) -> None:
        request = route.request
        self.received.append((request.method, request.url))
        location = self.redirects.get(request.url)
        if location is not None:
            await route.fulfill(status=302, headers={"Location": location}, body="")
            return
        served = self.pages.get(request.url)
        if served is None:
            await route.fulfill(status=404, body="")
            return
        content_type, body = served
        await route.fulfill(status=200, content_type=content_type, body=body)

    def reached(self, url: str) -> bool:
        return any(received_url == url for _, received_url in self.received)


@dataclass
class _RecordingObserver:
    """The page-observer hook, recording what the view would report to the panel."""

    pages: list[Page] = field(default_factory=list)
    notices: list[ViewNotice] = field(default_factory=list)
    changed: asyncio.Event = field(default_factory=asyncio.Event)

    def page_opened(self, page: Page) -> None:
        self.pages.append(page)
        self.changed.set()

    def notice(self, notice: ViewNotice) -> None:
        self.notices.append(notice)
        self.changed.set()

    async def wait_for(self, code: ViewNoticeCode) -> ViewNotice:
        async def matched() -> ViewNotice:
            while True:
                for notice in self.notices:
                    if notice.code is code:
                        return notice
                self.changed.clear()
                await self.changed.wait()

        return await asyncio.wait_for(matched(), timeout=_EVENT_TIMEOUT_SECONDS)


@asynccontextmanager
async def _view_context(
    tmp_path: Path,
    sede: _SyntheticSede,
    *,
    guard: ContextRequestGuard | None = None,
) -> AsyncGenerator[tuple[BrowserContext, _RecordingObserver]]:
    settings = Settings(
        cadrumo_local_storage_root=tmp_path,
        cadrumo_browser_headless=True,
        cadrumo_proxy_url=_CLOSED_PROXY,
    )
    record_shared_browser(settings)
    observer = _RecordingObserver()
    async with async_playwright() as playwright:
        session = BrowserSession(playwright, settings, Profile(name="sede-view-guard"), evasion_strategy=sede)
        try:
            context = await session.create_view_context(
                request_guard=guard if guard is not None else operator_view_request_guard(None),
                observer=observer,
            )
            try:
                yield context, observer
            finally:
                await context.close()
        finally:
            await session.close()


async def _open_page(context: BrowserContext, observer: _RecordingObserver, url: str) -> Page:
    page = await context.new_page()
    await asyncio.wait_for(_until(lambda: page in observer.pages), timeout=_EVENT_TIMEOUT_SECONDS)
    await page.goto(url)
    return page


async def _until(predicate: Callable[[], bool]) -> None:
    while not predicate():
        await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_view_admits_a_sede_read_and_exposes_the_page(tmp_path: Path) -> None:
    sede = _SyntheticSede()
    start = sede.page(f"{_SEDE}/Sede/inicio.html", "<title>sede</title>")
    async with _view_context(tmp_path, sede) as (context, observer):
        page = await _open_page(context, observer, start)
        assert await page.title() == "sede"
        assert observer.pages == [page]
        assert observer.notices == []
        assert sede.received == [("GET", start)]


@pytest.mark.asyncio
async def test_view_refuses_an_undeclared_post(tmp_path: Path) -> None:
    sede = _SyntheticSede()
    target = f"{_SEDE}/wlpl/BUGC-JDIT/Consulta"
    start = sede.page(
        f"{_SEDE}/Sede/formulario.html",
        f'<form id="f" method="post" action="{target}"><input name="q" value="1"></form>',
    )
    sede.page(target, "<title>posted</title>")
    async with _view_context(tmp_path, sede) as (context, observer):
        page = await _open_page(context, observer, start)
        await page.locator("#f").evaluate("form => form.submit()")
        notice = await observer.wait_for(ViewNoticeCode.NAVIGATION_REFUSED)
        assert notice.offer_url == target
        assert not sede.reached(target)


@pytest.mark.asyncio
async def test_view_refuses_a_get_carrying_a_forbidden_token(tmp_path: Path) -> None:
    sede = _SyntheticSede()
    target = sede.page(f"{_SEDE}/wlpl/PRES-MODE/PresentarDeclaracion", "<title>presentar</title>")
    start = sede.page(f"{_SEDE}/Sede/inicio.html", f'<a id="go" href="{target}">go</a>')
    async with _view_context(tmp_path, sede) as (context, observer):
        page = await _open_page(context, observer, start)
        await page.click("#go")
        notice = await observer.wait_for(ViewNoticeCode.NAVIGATION_REFUSED)
        assert notice.offer_url == target
        assert not sede.reached(target)


@pytest.mark.asyncio
async def test_view_refuses_an_off_host_subresource(tmp_path: Path) -> None:
    sede = _SyntheticSede()
    image = f"{_OFF_HOST}/pixel.png"
    start = sede.page(f"{_SEDE}/Sede/inicio.html", f'<img src="{image}">')
    async with _view_context(tmp_path, sede) as (context, observer):
        await _open_page(context, observer, start)
        notice = await observer.wait_for(ViewNoticeCode.REQUEST_REFUSED)
        assert notice.offer_url is None
        assert not sede.reached(image)


@pytest.mark.asyncio
async def test_view_offers_an_off_host_top_level_navigation(tmp_path: Path) -> None:
    sede = _SyntheticSede()
    target = f"{_OFF_HOST}/somewhere"
    start = sede.page(f"{_SEDE}/Sede/inicio.html", f'<a id="go" href="{target}">go</a>')
    async with _view_context(tmp_path, sede) as (context, observer):
        page = await _open_page(context, observer, start)
        await page.click("#go")
        notice = await observer.wait_for(ViewNoticeCode.NAVIGATION_REFUSED)
        assert notice.offer_url == target
        assert not sede.reached(target)


@pytest.mark.asyncio
async def test_view_offers_an_off_host_redirect_target(tmp_path: Path) -> None:
    sede = _SyntheticSede()
    target = f"{_OFF_HOST}/after-redirect"
    hop = sede.redirect(f"{_SEDE}/Sede/salto", target)
    start = sede.page(f"{_SEDE}/Sede/inicio.html", f'<a id="go" href="{hop}">go</a>')
    async with _view_context(tmp_path, sede) as (context, observer):
        page = await _open_page(context, observer, start)
        await page.click("#go")
        notice = await observer.wait_for(ViewNoticeCode.NAVIGATION_REFUSED)
        assert notice.offer_url == target
        assert sede.reached(hop)
        assert not sede.reached(target)
        assert page.url != target


@pytest.mark.asyncio
async def test_view_closes_a_popup_and_offers_it(tmp_path: Path) -> None:
    sede = _SyntheticSede()
    target = f"{_OFF_HOST}/popup"
    start = sede.page(f"{_SEDE}/Sede/inicio.html", f'<a id="go" target="_blank" href="{target}">go</a>')
    async with _view_context(tmp_path, sede) as (context, observer):
        page = await _open_page(context, observer, start)
        await page.click("#go")
        notice = await observer.wait_for(ViewNoticeCode.POPUP_REFUSED)
        assert notice.offer_url == target
        await asyncio.wait_for(_until(lambda: context.pages == [page]), timeout=_EVENT_TIMEOUT_SECONDS)
        assert observer.pages == [page]
        assert all(notice.code is not ViewNoticeCode.NAVIGATION_REFUSED for notice in observer.notices)
        assert not sede.reached(target)


@pytest.mark.asyncio
async def test_view_offers_a_download_without_saving_it(tmp_path: Path) -> None:
    sede = _SyntheticSede()
    target = sede.page(f"{_SEDE}/wlpl/DOCU-MENT/justificante.pdf", "%PDF-1.4 synthetic", "application/pdf")
    start = sede.page(f"{_SEDE}/Sede/inicio.html", f'<a id="go" download href="{target}">go</a>')
    async with _view_context(tmp_path, sede) as (context, observer):
        page = await _open_page(context, observer, start)
        await page.click("#go")
        notice = await observer.wait_for(ViewNoticeCode.DOWNLOAD_REFUSED)
        assert notice.offer_url == target


@pytest.mark.asyncio
async def test_view_offers_the_page_of_a_file_chooser(tmp_path: Path) -> None:
    sede = _SyntheticSede()
    start = sede.page(f"{_SEDE}/Sede/aportar.html", '<input id="file" type="file">')
    async with _view_context(tmp_path, sede) as (context, observer):
        page = await _open_page(context, observer, start)
        await page.click("#file")
        notice = await observer.wait_for(ViewNoticeCode.FILE_CHOOSER_REFUSED)
        assert notice.offer_url == start


def _service_worker_pages(sede: _SyntheticSede) -> tuple[str, str]:
    """Serve a page that registers a service worker and titles itself with the outcome."""
    worker = sede.page(f"{_SEDE}/Sede/sw.js", "self.addEventListener('fetch', () => {});", "text/javascript")
    start = sede.page(
        f"{_SEDE}/Sede/inicio.html",
        """<script>
        navigator.serviceWorker.register('/Sede/sw.js')
            .then(() => navigator.serviceWorker.getRegistrations())
            .then(
                (registrations) => { document.title = 'registrations:' + registrations.length; },
                () => { document.title = 'refused'; });
        </script>""",
    )
    return worker, start


@pytest.mark.asyncio
async def test_view_blocks_a_service_worker_registration(tmp_path: Path) -> None:
    sede = _SyntheticSede()
    worker, start = _service_worker_pages(sede)
    async with _view_context(tmp_path, sede) as (context, observer):
        page = await _open_page(context, observer, start)
        await page.wait_for_function("document.title !== ''", timeout=_EVENT_TIMEOUT_SECONDS * 1000)
        assert await page.title() in {"registrations:0", "refused"}
        assert context.service_workers == []
        assert not sede.reached(worker)


@pytest.mark.asyncio
async def test_view_closes_a_websocket(tmp_path: Path) -> None:
    sede = _SyntheticSede()
    socket_url = f"wss://{urlsplit(_SEDE).netloc}/socket"
    start = sede.page(
        f"{_SEDE}/Sede/inicio.html",
        f"""<script>
        const socket = new WebSocket('{socket_url}');
        socket.onopen = () => {{ document.title = 'open'; }};
        socket.onclose = () => {{ document.title = 'closed'; }};
        </script>""",
    )
    async with _view_context(tmp_path, sede) as (context, observer):
        page = await _open_page(context, observer, start)
        await observer.wait_for(ViewNoticeCode.REQUEST_REFUSED)
        await page.wait_for_function("document.title === 'closed'", timeout=_EVENT_TIMEOUT_SECONDS * 1000)
        assert not sede.reached(socket_url)


@pytest.mark.asyncio
async def test_view_with_an_empty_policy_set_refuses_everything(tmp_path: Path) -> None:
    sede = _SyntheticSede()
    start = sede.page(f"{_SEDE}/Sede/inicio.html", "<title>sede</title>")
    async with _view_context(tmp_path, sede, guard=ContextRequestGuard(())) as (context, observer):
        page = await context.new_page()
        with pytest.raises(PlaywrightError, match="ERR_BLOCKED_BY_CLIENT"):
            await page.goto(start)
        notice = await observer.wait_for(ViewNoticeCode.NAVIGATION_REFUSED)
        assert notice.offer_url == start
        assert sede.received == []


@pytest.mark.asyncio
async def test_plain_context_carries_no_request_guard(tmp_path: Path) -> None:
    """Every context but the view's is unchanged: no guard, service workers allowed."""
    sede = _SyntheticSede()
    target = sede.page(f"{_SEDE}/wlpl/PRES-MODE/PresentarDeclaracion", "<title>presentar</title>")
    settings = Settings(
        cadrumo_local_storage_root=tmp_path,
        cadrumo_browser_headless=True,
        cadrumo_proxy_url=_CLOSED_PROXY,
    )
    record_shared_browser(settings)
    async with async_playwright() as playwright:
        session = BrowserSession(playwright, settings, Profile(name="plain-context"), evasion_strategy=sede)
        try:
            context = await session.create_context()
            try:
                page = await context.new_page()
                await page.goto(target)
                assert await page.title() == "presentar"
                assert sede.reached(target)
                worker, start = _service_worker_pages(sede)
                await page.goto(start)
                await page.wait_for_function("document.title !== ''", timeout=_EVENT_TIMEOUT_SECONDS * 1000)
                assert await page.title() == "registrations:1"
                assert sede.reached(worker)
            finally:
                await context.close()
        finally:
            await session.close()
