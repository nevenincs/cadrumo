"""Transfer transient browser downloads while retaining cleanup ownership."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from cadrumo_client.contracts.view_stream import ViewStreamSink
from cadrumo_client.contracts.view_transfer import ViewDownloadOutcome, ViewTransferCancel, ViewTransferDirection

from .....core.logging import get_logger
from .._playwright import PlaywrightError

if TYPE_CHECKING:
    from playwright.async_api import Download
logger = get_logger(__name__)


async def deliver_download(
    sink: ViewStreamSink, transfer_id: int, download: Download, outcome: ViewDownloadOutcome
) -> None:
    """Stream an accepted download from the browser's transient file, then delete that file."""
    try:
        if outcome is not ViewDownloadOutcome.ACCEPTED:
            await download.cancel()
            return
        try:
            path = await download.path()
        except PlaywrightError as exc:
            logger.info("aeat view download failed exc_type=%s", type(exc).__name__)
            sink.send(ViewTransferCancel(direction=ViewTransferDirection.DOWNLOAD, transfer_id=transfer_id))
            return
        streaming = asyncio.ensure_future(asyncio.to_thread(_stream_file, sink, transfer_id, path))
        try:
            await asyncio.shield(streaming)
        except asyncio.CancelledError:
            # The thread still holds the transient file open, which would keep it on disk: stop the stream
            # and let the thread release the file before it is deleted.
            sink.cancel_download(transfer_id)
            await asyncio.wait({streaming})
            raise
    finally:
        await discard_download(download)


def _stream_file(sink: ViewStreamSink, transfer_id: int, path: Path) -> bool:
    with path.open("rb") as source:
        return sink.send_download(transfer_id, source)


async def discard_download(download: Download) -> None:
    """Cancel and delete a transient download, tolerating an already closed browser."""
    try:
        await download.cancel()
        await download.delete()
    except PlaywrightError as exc:
        logger.debug("aeat view download discard skipped exc_type=%s", type(exc).__name__)
