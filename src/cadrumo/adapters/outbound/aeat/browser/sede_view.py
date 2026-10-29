"""The Sede view's browser: its unrestricted context, the page it shows, and the person's hands on it.

:class:`SedeViewPage` implements the application's
:class:`~cadrumo.application.live.sede_view_ports.SedeViewBrowser`. It opens
the view context seeded from custody, shows one page at a time through
:class:`~.screencast.ViewScreencast` and :class:`~.view_input.ViewInputAdapter`,
and relays the page's popups, dialogs, downloads and file choosers to the
window through the view stream. A popup takes over the panel; when it closes,
its opener returns. The view sets no idle or absolute bound: it browses until
the person closes it, the stream ends or the operation is asked to stop.

Signing in happens in the view too. When the shown page loads an AEAT page the
view tells the application, which checks through the provider's own
verification whether the person has signed in and publishes the session. The
view also lends its context to the configured provider's assisted login
through :attr:`SedeViewPage.login_session_factory`: the provider's pages open
in the panel, headless, and the person's press, key, text or navigation
cancels that login at once and then reaches the page.

Outside an assisted login Cadrumo issues no request in the view: the only
navigation it starts is the Sede home page, which the person's ``home`` verb
also opens. It evaluates no script; the toolbar's URL and title come from ``Page.getNavigationHistory``
through the input adapter. A download's bytes pass from the browser's own
transient file straight to the stream, and the file is deleted when the
transfer ends, however it ends: completed, cancelled, failed or cut short by
the view's close; an upload reaches the page from memory. URLs, titles, images,
input and file bytes are never logged, persisted or journaled.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, Self

from cadrumo_client.contracts.view_stream import (
    ViewClose,
    ViewDialog,
    ViewImage,
    ViewInput,
    ViewNavigate,
    ViewNotice,
    ViewNoticeCode,
    ViewPhase,
    ViewResize,
    ViewSinkInput,
    ViewStreamSink,
)
from cadrumo_client.contracts.view_transfer import (
    VIEW_MAX_TRANSFER_ID,
    ViewDownload,
    ViewDownloadAnswer,
    ViewFileChooser,
    ViewFileChooserAnswer,
    ViewFileChooserOutcome,
    ViewTransferCancel,
    ViewTransferDirection,
    ViewUploadCancelled,
    ViewUploadedFile,
)

from .....application.live.sede_view_ports import SedeViewEnd, SedeViewOpening, SedeViewSignIn
from .....core.async_cleanup import AsyncCloseable, close_async_resources
from .....core.config import Settings
from .....core.logging import get_logger
from .._playwright import BrowserContext, Page, PlaywrightError
from .factory import default_browser_session_factory
from .screencast import ScreencastImage, ScreencastProfile, ViewScreencast
from .session import BrowserSession
from .view_download import deliver_download, discard_download
from .view_input import ViewInputAdapter
from .view_login_session import ViewLoginSessionFactory
from .view_presentation import interrupts_assisted_login, is_aeat_page, safe_filename, view_state

if TYPE_CHECKING:
    from playwright.async_api import Dialog, Download, FileChooser, FilePayload

logger = get_logger(__name__)

#: How long one wait for the person's next input lasts before the view checks its stop conditions.
_RECEIVE_SECONDS: Final[float] = 0.25
#: The screencast's own credit is kept full: the stream keeps only the newest image under the window's credit.
_SCREENCAST_CREDIT: Final[int] = 2
_FALLBACK_MIME: Final[str] = "application/octet-stream"


@dataclass(slots=True)
class _Chooser:
    """A file chooser the page opened, waiting for the window's files."""

    chooser: FileChooser
    multiple: bool
    expected: int | None = None
    files: list[ViewUploadedFile] = field(default_factory=list)


class SedeViewPage:
    """The view's browser; open it with :meth:`open` or :func:`open_sede_view`."""

    def __init__(self, *, sink: ViewStreamSink, settings: Settings, viewport: ViewResize) -> None:
        """Hold the stream and the panel size; :meth:`open` builds the context and the page."""
        self._sink = sink
        self._settings = settings
        self._viewport = viewport
        self._home_url = settings.external_constants().aeat.domains.sede
        self._context: BrowserContext | None = None
        self._owner: AsyncCloseable | None = None
        self._pages: list[Page] = []
        self._shown: Page | None = None
        self._screencast: ViewScreencast | None = None
        self._input: ViewInputAdapter | None = None
        self._show_lock = asyncio.Lock()
        self._phase = ViewPhase.BROWSING
        self._loading = False
        self._next_sequence = 0
        self._last_transfer_id = 0
        self._last_chooser_id = 0
        self._downloads: dict[int, Download] = {}
        self._choosers: dict[int, _Chooser] = {}
        self._background: set[asyncio.Task[None]] = set()
        self._sign_in: SedeViewSignIn | None = None
        self._assist: asyncio.Task[None] | None = None
        self._sign_in_check: asyncio.Task[None] | None = None
        self._sign_in_loads = 0
        self._lost = False
        self._closed = False

    @classmethod
    async def open(cls, session: BrowserSession, owner: AsyncCloseable | None, opening: SedeViewOpening) -> Self:
        """Build the view context from the seed, open its page and load the Sede home page.

        ``owner`` closes the browser behind ``session``; the view closes it on
        :meth:`close`, and the operation's resource scope holds it too.
        """
        view = cls(sink=opening.sink, settings=opening.settings, viewport=opening.viewport)
        view._owner = owner
        try:
            context = await session.create_view_context(
                observer=view, provisioner=opening.provisioner, storage_state=opening.storage_state
            )
            view._context = context
            context.on("close", lambda _context: view._mark_lost())
            page = await context.new_page()
            view._adopt(page)
            await view._show(page)
            await page.goto(view._home_url, wait_until="commit")
        except BaseException:
            await view.close()
            raise
        return view

    @property
    def context(self) -> BrowserContext:
        """The view context, open until :meth:`close`."""
        if self._context is None:
            raise PlaywrightError("the Sede view has no context")
        return self._context

    @property
    def login_session_factory(self) -> ViewLoginSessionFactory:
        """Browser sessions that lend a provider's assisted login this view's context and panel."""
        return ViewLoginSessionFactory(self)

    async def browse(self, *, stop_requested: Callable[[], bool], sign_in: SedeViewSignIn | None = None) -> SedeViewEnd:
        """Relay the page and the person's input until the view ends.

        ``sign_in`` is started at once and told of every AEAT page the shown
        page loads; any assisted login it runs is cancelled by the person's
        input while it is interruptible. Before this returns, an interruptible
        login is cancelled and any sign-in work still running is awaited.
        """
        await self.announce_phase(ViewPhase.BROWSING)
        self._sign_in = sign_in
        if sign_in is not None:
            self._assist = self._track(sign_in.assist())
        try:
            while True:
                if stop_requested():
                    return SedeViewEnd.STOPPED
                if self._lost:
                    return SedeViewEnd.PAGE_LOST
                item = await asyncio.to_thread(self._sink.receive, timeout=_RECEIVE_SECONDS)
                if item is None:
                    if self._sink.ended:
                        return SedeViewEnd.STREAM_ENDED
                    continue
                end = await self._apply(item)
                if end is not None:
                    return end
        finally:
            await self._settle_sign_in()

    async def announce_phase(self, phase: ViewPhase) -> None:
        """Send the window the current page's state in ``phase``."""
        self._phase = phase
        await self._send_state()

    async def announce_notice(self, code: ViewNoticeCode) -> None:
        """Send the window a notice that carries no dialog."""
        self._sink.send(ViewNotice(code=code))

    async def close(self) -> None:
        """Stop showing the page, cancel pending transfers and close the browser; safe to repeat."""
        if self._closed:
            return
        self._closed = True
        await self._detach()
        for task in tuple(self._background):
            task.cancel()
        await asyncio.gather(*self._background, return_exceptions=True)
        downloads, self._downloads = tuple(self._downloads.values()), {}
        for download in downloads:
            await discard_download(download)
        self._choosers.clear()
        context, self._context = self._context, None
        await close_async_resources(context, self._owner, task_name="cadrumo-sede-view-close")

    # -- page observer ---------------------------------------------------------------------------------------------

    def page_opened(self, page: Page) -> None:
        """Show a page the context opened by code, unless it is the view's own first page."""
        if page in self._pages or not self._pages:
            return
        self._adopt(page)
        self._spawn(self._show(page))

    def popup_opened(self, popup: Page, opener: Page) -> None:
        """Show the popup in the panel; its opener returns when it closes."""
        del opener
        if popup in self._pages:
            return
        self._adopt(popup)
        self._spawn(self._show(popup))

    def download_started(self, page: Page, download: Download) -> None:
        """Offer the download to the person; its bytes wait in the browser's transient file."""
        del page
        if self._closed or self._last_transfer_id >= VIEW_MAX_TRANSFER_ID:
            self._spawn(discard_download(download))
            return
        self._last_transfer_id += 1
        self._downloads[self._last_transfer_id] = download
        self._sink.send(
            ViewDownload(transfer_id=self._last_transfer_id, filename=safe_filename(download.suggested_filename))
        )

    def file_chooser_opened(self, page: Page, file_chooser: FileChooser) -> None:
        """Ask the person for the files the page wants."""
        del page
        if self._closed or self._last_chooser_id >= VIEW_MAX_TRANSFER_ID:
            return
        self._last_chooser_id += 1
        multiple = file_chooser.is_multiple()
        self._choosers[self._last_chooser_id] = _Chooser(chooser=file_chooser, multiple=multiple)
        self._sink.send(ViewFileChooser(chooser_id=self._last_chooser_id, accept=(), multiple=multiple))

    def dialog_opened(self, page: Page, dialog: Dialog) -> None:
        """Hand the dialog to the input adapter, which asks the person."""
        del page
        adapter = self._input
        if adapter is None or self._closed:
            self._spawn(self._dismiss(dialog))
            return
        adapter.dialog_opened(dialog)

    # -- person input ----------------------------------------------------------------------------------------------

    async def _apply(self, item: ViewSinkInput) -> SedeViewEnd | None:
        """Act on one item from the window; return how the view ends, if it does."""
        try:
            return await self._dispatch(item)
        except PlaywrightError as exc:
            # A page that went away under the person's hands; the next page, if any, takes over.
            logger.info("aeat view input skipped exc_type=%s", type(exc).__name__)
            return None

    async def _dispatch(self, item: ViewSinkInput) -> SedeViewEnd | None:
        if interrupts_assisted_login(item):
            await self._interrupt_assist()
        if isinstance(item, ViewClose):
            return SedeViewEnd.CLOSED
        if isinstance(item, ViewInput):
            adapter = self._input
            if adapter is not None and (await adapter.input(item)).refused:
                return SedeViewEnd.PROTOCOL_VIOLATION
        elif isinstance(item, ViewNavigate):
            adapter = self._input
            if adapter is not None:
                self._spawn(self._navigate(adapter, item))
        elif isinstance(item, ViewResize):
            await self._resize(item)
        elif isinstance(item, ViewDialog):
            await self._answer_dialog(item)
        else:
            return self._dispatch_transfer(item)
        return None

    async def _resize(self, item: ViewResize) -> None:
        self._viewport = item
        if self._screencast is not None:
            await self._screencast.resize(item)

    async def _answer_dialog(self, item: ViewDialog) -> None:
        if self._input is not None:
            await self._input.answer_dialog(item)

    def _dispatch_transfer(
        self,
        item: ViewDownloadAnswer | ViewFileChooserAnswer | ViewUploadedFile | ViewUploadCancelled | ViewTransferCancel,
    ) -> SedeViewEnd | None:
        if isinstance(item, ViewDownloadAnswer):
            download = self._downloads.pop(item.transfer_id, None)
            if download is not None:
                self._spawn(deliver_download(self._sink, item.transfer_id, download, item.outcome))
        elif isinstance(item, ViewFileChooserAnswer):
            return self._answer_chooser(item)
        elif isinstance(item, ViewUploadedFile):
            self._receive_file(item)
        elif isinstance(item, ViewUploadCancelled):
            self._cancel_upload(item.chooser_id)
        else:
            self._cancel_transfer(item)
        return None

    async def _navigate(self, adapter: ViewInputAdapter, verb: ViewNavigate) -> None:
        await adapter.navigate(verb)
        await self._send_state()

    def _answer_chooser(self, answer: ViewFileChooserAnswer) -> SedeViewEnd | None:
        pending = self._choosers.get(answer.chooser_id)
        if pending is None or pending.expected is not None:
            return None
        if answer.outcome is ViewFileChooserOutcome.CANCELLED:
            del self._choosers[answer.chooser_id]
            return None
        if answer.file_count > 1 and not pending.multiple:
            return SedeViewEnd.PROTOCOL_VIOLATION
        pending.expected = answer.file_count
        return None

    def _receive_file(self, uploaded: ViewUploadedFile) -> None:
        pending = self._choosers.get(uploaded.chooser_id)
        if pending is None or pending.expected is None:
            return
        pending.files.append(uploaded)
        if len(pending.files) == pending.expected:
            del self._choosers[uploaded.chooser_id]
            self._spawn(self._supply(pending))

    def _cancel_transfer(self, cancel: ViewTransferCancel) -> None:
        if cancel.direction is ViewTransferDirection.DOWNLOAD:
            download = self._downloads.pop(cancel.transfer_id, None)
            if download is not None:
                self._spawn(discard_download(download))

    def _cancel_upload(self, chooser_id: int) -> None:
        # A cancelled upload leaves its chooser without all its files; the page keeps no partial set.
        pending = self._choosers.get(chooser_id)
        if pending is not None and pending.expected is not None:
            del self._choosers[chooser_id]

    async def _supply(self, pending: _Chooser) -> None:
        payloads: list[FilePayload] = [
            {"name": uploaded.name, "mimeType": uploaded.mime or _FALLBACK_MIME, "buffer": uploaded.data}
            for uploaded in pending.files
        ]
        pending.files.clear()
        await pending.chooser.set_files(payloads)

    # -- signing in ------------------------------------------------------------------------------------------------

    async def _interrupt_assist(self) -> None:
        """Cancel an interruptible assisted login and wait until it has let go of the page."""
        task, sign_in = self._assist, self._sign_in
        if task is None or task.done() or sign_in is None or not sign_in.interruptible:
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def _settle_sign_in(self) -> None:
        await self._interrupt_assist()
        running = [task for task in (self._assist, self._sign_in_check) if task is not None and not task.done()]
        await asyncio.gather(*running, return_exceptions=True)
        self._sign_in = None

    def _watch_sign_in(self, page: Page) -> None:
        """Ask the application whether the person has signed in once an AEAT page has loaded."""
        sign_in = self._sign_in
        if sign_in is None or self._closed or (self._assist is not None and not self._assist.done()):
            return
        if not is_aeat_page(page.url):
            return
        check = self._sign_in_check
        if check is not None and not check.done():
            self._sign_in_loads += 1
            return
        self._sign_in_check = self._track(self._check_sign_in(sign_in))

    async def _check_sign_in(self, sign_in: SedeViewSignIn) -> None:
        """Run the application's check, once more if another page loaded while it ran."""
        while True:
            checked = self._sign_in_loads
            await sign_in.page_loaded()
            if self._sign_in_loads == checked:
                return

    @staticmethod
    async def _dismiss(dialog: Dialog) -> None:
        try:
            await dialog.dismiss()
        except PlaywrightError as exc:
            logger.debug("aeat view dialog dismiss skipped exc_type=%s", type(exc).__name__)

    # -- the shown page --------------------------------------------------------------------------------------------

    def _adopt(self, page: Page) -> None:
        """Track a page of the view; the newest page is the one the panel shows."""
        self._pages.append(page)
        page.on("close", lambda closed: self._page_closed(closed))
        page.on("framenavigated", lambda frame: self._navigated(page, frame.parent_frame is None))
        page.on("load", lambda _page: self._loaded(page))

    def _page_closed(self, page: Page) -> None:
        if page in self._pages:
            self._pages.remove(page)
        if not self._pages:
            self._mark_lost()
            return
        if page is self._shown:
            self._spawn(self._show(self._pages[-1]))

    def _navigated(self, page: Page, main_frame: bool) -> None:
        if main_frame and page is self._shown:
            self._loading = True
            self._spawn(self._send_state())

    def _loaded(self, page: Page) -> None:
        if page is self._shown:
            self._loading = False
            self._spawn(self._send_state())
            self._watch_sign_in(page)

    def _mark_lost(self) -> None:
        self._lost = True

    async def _show(self, page: Page) -> None:
        """Point the screencast and the input at ``page``, releasing those of the page shown before."""
        async with self._show_lock:
            if self._closed or page is self._shown or page.is_closed():
                return
            await self._detach()
            context = self.context
            try:
                self._input = await ViewInputAdapter.attach(
                    context, page, settings=self._settings, notices=self._sink.send
                )
                self._screencast = await ViewScreencast.start(
                    context, page, self._viewport, self._offer, profile=ScreencastProfile()
                )
            except PlaywrightError:
                if not page.is_closed():
                    raise
            else:
                self._screencast.grant_credit(_SCREENCAST_CREDIT)
                self._shown = page
        if page.is_closed():
            # The page closed while it was being shown, before its close could move the panel on.
            await self._show_newest()
            return
        await self._send_state()

    async def _show_newest(self) -> None:
        newest = next((page for page in reversed(self._pages) if not page.is_closed()), None)
        if newest is not None:
            await self._show(newest)

    async def _detach(self) -> None:
        screencast, self._screencast = self._screencast, None
        adapter, self._input = self._input, None
        self._shown = None
        if screencast is not None:
            await screencast.stop()
        if adapter is not None:
            await adapter.close()

    async def _offer(self, image: ScreencastImage) -> None:
        """Hand the newest image to the stream, numbered across every page the view has shown."""
        announcement = image.announcement
        renumbered = ViewImage(
            sequence=self._next_sequence,
            byte_length=announcement.byte_length,
            pixel_width=announcement.pixel_width,
            pixel_height=announcement.pixel_height,
            css_width=announcement.css_width,
            css_height=announcement.css_height,
            scale=announcement.scale,
        )
        self._next_sequence += 1
        self._sink.offer_image(renumbered, image.data)
        if self._screencast is not None:
            self._screencast.grant_credit(1)

    async def _send_state(self) -> None:
        """State the shown page; a page whose entry cannot be read is stated as unknown, never left unsaid."""
        adapter = self._input
        if adapter is None:
            return
        try:
            entry = await adapter.current_entry()
        except PlaywrightError as exc:
            logger.debug("aeat view state unreadable exc_type=%s", type(exc).__name__)
            entry = None
        if entry is None:
            state = view_state("", "", back=False, forward=False, loading=self._loading, phase=self._phase)
        else:
            state = view_state(
                entry.url,
                entry.title,
                back=entry.availability.can_go_back,
                forward=entry.availability.can_go_forward,
                loading=self._loading,
                phase=self._phase,
            )
        self._sink.send(state)

    def _spawn(self, work: Coroutine[object, object, None]) -> None:
        self._track(work)

    def _track(self, work: Coroutine[object, object, None]) -> asyncio.Task[None]:
        task = asyncio.get_running_loop().create_task(_settle(work))
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        return task


async def _settle(work: Coroutine[object, object, None]) -> None:
    try:
        await work
    except PlaywrightError as exc:
        logger.debug("aeat view page work ended exc_type=%s", type(exc).__name__)
    except Exception as exc:
        logger.error("aeat view page work failed exc_type=%s", type(exc).__name__)


async def open_sede_view(opening: SedeViewOpening) -> SedeViewPage:
    """Open the view in a browser of its own, owned by the running operation's browser scope."""
    owner = await default_browser_session_factory(opening.settings)
    return await SedeViewPage.open(owner.session, owner, opening)


__all__ = [
    "SedeViewPage",
    "open_sede_view",
]
