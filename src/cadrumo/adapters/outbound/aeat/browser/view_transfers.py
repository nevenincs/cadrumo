"""The Sede view's file transfers: downloads offered to the person and uploads a page asks for.

A download waits in the browser's own transient file until the window answers it; an upload
waits for every file the window announced before the page's chooser receives them, from memory.
The view owns the page and the stream; this holds only the transfers in flight.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from cadrumo_client.contracts.view_stream import ViewStreamSink
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

from .....application.live.sede_view_ports import SedeViewEnd
from .view_download import deliver_download, discard_download
from .view_presentation import safe_filename

if TYPE_CHECKING:
    from playwright.async_api import Download, FileChooser, FilePayload

_FALLBACK_MIME: Final[str] = "application/octet-stream"

type TransferItem = (
    ViewDownloadAnswer | ViewFileChooserAnswer | ViewUploadedFile | ViewUploadCancelled | ViewTransferCancel
)


@dataclass(slots=True)
class _Chooser:
    """A file chooser the page opened, waiting for the window's files."""

    chooser: FileChooser
    multiple: bool
    expected: int | None = None
    files: list[ViewUploadedFile] = field(default_factory=list)


class ViewTransfers:
    """The downloads and file choosers the view has offered the window and not yet settled."""

    def __init__(self, sink: ViewStreamSink, spawn: Callable[[Coroutine[object, object, None]], None]) -> None:
        """Send offers to ``sink`` and run background work through ``spawn``."""
        self._sink = sink
        self._spawn = spawn
        self._last_transfer_id = 0
        self._last_chooser_id = 0
        self._downloads: dict[int, Download] = {}
        self._choosers: dict[int, _Chooser] = {}

    def download_started(self, download: Download, *, closed: bool) -> None:
        """Offer the download to the person; its bytes wait in the browser's transient file."""
        if closed or self._last_transfer_id >= VIEW_MAX_TRANSFER_ID:
            self._spawn(discard_download(download))
            return
        self._last_transfer_id += 1
        self._downloads[self._last_transfer_id] = download
        self._sink.send(
            ViewDownload(transfer_id=self._last_transfer_id, filename=safe_filename(download.suggested_filename))
        )

    def file_chooser_opened(self, file_chooser: FileChooser, *, closed: bool) -> None:
        """Ask the person for the files the page wants."""
        if closed or self._last_chooser_id >= VIEW_MAX_TRANSFER_ID:
            return
        self._last_chooser_id += 1
        multiple = file_chooser.is_multiple()
        self._choosers[self._last_chooser_id] = _Chooser(chooser=file_chooser, multiple=multiple)
        self._sink.send(ViewFileChooser(chooser_id=self._last_chooser_id, accept=(), multiple=multiple))

    def dispatch(self, item: TransferItem) -> SedeViewEnd | None:
        """Act on one transfer item from the window; return how the view ends, if it does."""
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

    async def close(self) -> None:
        """Discard every download still waiting and forget every chooser."""
        downloads, self._downloads = tuple(self._downloads.values()), {}
        for download in downloads:
            await discard_download(download)
        self._choosers.clear()

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

    @staticmethod
    async def _supply(pending: _Chooser) -> None:
        payloads: list[FilePayload] = [
            {"name": uploaded.name, "mimeType": uploaded.mime or _FALLBACK_MIME, "buffer": uploaded.data}
            for uploaded in pending.files
        ]
        pending.files.clear()
        await pending.chooser.set_files(payloads)
