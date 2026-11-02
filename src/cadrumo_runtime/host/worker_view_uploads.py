"""The files a window sends through the view stream, received whole in memory.

Each upload is granted credit chunk by chunk, topped up as the window spends it, and
handed over only after the receiver has checked its completion. Cancelling or ending
the view wipes the bytes held. The stream owns the channel and the locking; this holds
only the uploads in flight and returns what the stream must queue.
"""

from __future__ import annotations

from cadrumo_client.contracts.view_transfer import (
    VIEW_TRANSFER_CREDIT_MAX_CHUNKS,
    ViewTransferDirection,
    ViewTransferDownstreamDocument,
    ViewUpload,
    ViewUploadCancelled,
    ViewUploadedFile,
)
from cadrumo_client.transport.view_stream import ViewTransferChunk, ViewTransferReceiver

_UPLOAD_REGRANT = VIEW_TRANSFER_CREDIT_MAX_CHUNKS // 2
"""Top an upload's credit back up once the window has spent this much of it."""


class _Upload:
    """One file the window is sending, held in memory until its completion checks it."""

    __slots__ = ("credit", "data", "upload")

    def __init__(self, upload: ViewUpload) -> None:
        self.upload = upload
        self.data = bytearray()
        self.credit = 0

    def wipe(self) -> None:
        self.data[:] = bytes(len(self.data))
        self.data = bytearray()


class ViewUploadIntake:
    """The uploads the window has started and not yet completed or cancelled."""

    def __init__(self) -> None:
        """Start with no upload in flight."""
        self.receiver = ViewTransferReceiver(ViewTransferDirection.UPLOAD)
        self._receiving: dict[int, _Upload] = {}

    def begin(self, item: ViewUpload) -> ViewTransferDownstreamDocument:
        """Accept an announced upload and return the first credit to send the window."""
        self.receiver.expect(item.transfer_id, size=item.size)
        upload = _Upload(item)
        self._receiving[item.transfer_id] = upload
        return self._grant(upload, VIEW_TRANSFER_CREDIT_MAX_CHUNKS)

    def chunk(self, chunk: ViewTransferChunk) -> ViewTransferDownstreamDocument | None:
        """Keep one chunk; return fresh credit once the window has spent enough of it."""
        upload = self._receiving.get(chunk.transfer_id)
        if upload is None:
            return None
        upload.data.extend(chunk.data)
        upload.credit -= 1
        if not chunk.last and upload.credit <= _UPLOAD_REGRANT:
            return self._grant(upload, VIEW_TRANSFER_CREDIT_MAX_CHUNKS - upload.credit)
        return None

    def complete(self, transfer_id: int) -> ViewUploadedFile | None:
        """Hand over a file whose completion the receiver has already checked in size and digest."""
        upload = self._receiving.pop(transfer_id, None)
        if upload is None:
            return None
        uploaded = ViewUploadedFile(
            chooser_id=upload.upload.chooser_id,
            name=upload.upload.name,
            mime=upload.upload.mime,
            data=bytes(upload.data),
        )
        upload.wipe()
        return uploaded

    def cancel(self, transfer_id: int) -> ViewUploadCancelled | None:
        """Drop a cancelled upload; only its own chooser loses its files."""
        upload = self._receiving.pop(transfer_id, None)
        if upload is None:
            return None
        upload.wipe()
        return ViewUploadCancelled(chooser_id=upload.upload.chooser_id)

    def wipe(self) -> None:
        """Wipe and forget every upload in flight."""
        for upload in self._receiving.values():
            upload.wipe()
        self._receiving.clear()

    def _grant(self, upload: _Upload, chunks: int) -> ViewTransferDownstreamDocument:
        document = self.receiver.grant(upload.upload.transfer_id, chunks)
        upload.credit += chunks
        return document
