"""Real headless Chromium for the Sede view adapters' tests.

Each view test drives a page in a Chromium it launches itself. A route
registered before any test route aborts every request, so a test that serves
no page cannot reach the network; :class:`SyntheticSite` fulfils the pages a
test stands in for the Sede.
"""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Final

from playwright.async_api import BrowserContext, Page, Route, async_playwright

from cadrumo_client.contracts.view_stream import ViewClosedReason, ViewImage, ViewNotice, ViewSinkInput, ViewState
from cadrumo_client.contracts.view_transfer import (
    ViewDownload,
    ViewFileChooser,
    ViewTransferByteSource,
    ViewTransferCancel,
)

EVENT_TIMEOUT_SECONDS: Final[float] = 10.0
_POLL_SECONDS: Final[float] = 0.02


@dataclass
class SyntheticSite:
    """Pages served for the stood-in Sede, and every URL the browser asked for."""

    pages: dict[str, str] = field(default_factory=dict)
    received: list[str] = field(default_factory=list)

    def page(self, url: str, body: str) -> str:
        """Serve ``body`` as the HTML page at ``url``."""
        self.pages[url] = body
        return url

    async def apply(self, context: BrowserContext) -> None:
        """Route every request of ``context`` to this site; unserved URLs answer 404."""
        await context.route("**/*", self._fulfil)

    async def _fulfil(self, route: Route) -> None:
        url = route.request.url
        self.received.append(url)
        body = self.pages.get(url)
        if body is None:
            await route.fulfill(status=404, body="")
            return
        await route.fulfill(status=200, content_type="text/html; charset=utf-8", body=body)

    def requests_for(self, url: str) -> int:
        """How many times the browser asked for ``url``."""
        return sum(1 for received in self.received if received == url)


class RecordingViewSink:
    """Record what a view driver sends the window and hand it the window's input."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._inbox: deque[ViewSinkInput] = deque()
        self.images: list[ViewImage] = []
        self.documents: list[ViewState | ViewNotice | ViewDownload | ViewFileChooser | ViewTransferCancel] = []
        self.downloaded: dict[int, bytes] = {}
        self.closed: list[ViewClosedReason] = []
        self.cancelled_downloads: list[int] = []
        self.streaming: list[int] = []
        #: When set, a download waits, its source open, for window credit that never comes, as a stalled window's does.
        self.stall_downloads = False
        self._changed = threading.Condition(self._lock)

    @property
    def connected(self) -> bool:
        return True

    @property
    def ended(self) -> bool:
        return bool(self.closed)

    def offer_image(self, announcement: ViewImage, image: bytes) -> None:
        assert announcement.byte_length == len(image)
        with self._lock:
            self.images.append(announcement)

    def send(self, document: ViewState | ViewNotice | ViewDownload | ViewFileChooser | ViewTransferCancel) -> None:
        with self._lock:
            self.documents.append(document)

    def put(self, item: ViewSinkInput) -> None:
        with self._lock:
            self._inbox.append(item)

    def receive(self, *, timeout: float) -> ViewSinkInput | None:
        with self._lock:
            if self._inbox:
                return self._inbox.popleft()
        threading.Event().wait(min(timeout, 0.02))
        return None

    def send_download(self, transfer_id: int, source: ViewTransferByteSource) -> bool:
        if self.stall_downloads:
            source.read(4096)
            with self._changed:
                self.streaming.append(transfer_id)
                self._changed.wait_for(lambda: transfer_id in self.cancelled_downloads or bool(self.closed))
            return False
        chunks: list[bytes] = []
        while chunk := source.read(4096):
            chunks.append(chunk)
        with self._lock:
            self.downloaded[transfer_id] = b"".join(chunks)
        return True

    def cancel_download(self, transfer_id: int) -> None:
        with self._changed:
            self.cancelled_downloads.append(transfer_id)
            self._changed.notify_all()

    def close(self, reason: ViewClosedReason) -> None:
        with self._changed:
            self.closed.append(reason)
            self._changed.notify_all()

    def of[DocumentT](self, kind: type[DocumentT]) -> list[DocumentT]:
        with self._lock:
            return [document for document in self.documents if isinstance(document, kind)]


@asynccontextmanager
async def view_browser(*, width: int = 400, height: int = 300) -> AsyncGenerator[tuple[BrowserContext, Page]]:
    """Launch headless Chromium with one page at the given CSS size and no network."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            context = await browser.new_context(viewport={"width": width, "height": height}, service_workers="block")
            await context.route("**/*", _abort)
            page = await context.new_page()
            yield context, page
        finally:
            await browser.close()


async def _abort(route: Route) -> None:
    await route.abort()


async def until(condition: Callable[[], bool], *, timeout: float = EVENT_TIMEOUT_SECONDS) -> None:
    """Wait until ``condition`` holds, failing the test after ``timeout`` seconds."""

    async def poll() -> None:
        while not condition():
            await asyncio.sleep(_POLL_SECONDS)

    await asyncio.wait_for(poll(), timeout=timeout)
