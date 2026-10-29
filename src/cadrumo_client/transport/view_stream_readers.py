"""The view connection codec: ``B`` chunks and ``J`` control documents.

``B`` is legal only on a view connection, and only this module reads or writes
it; every other reader in the transport keeps refusing it. ``S`` and ``E``
never appear on a view connection.

A ``B`` frame's payload is a 16-byte header followed by the chunk body, all
integers in network order. Flag bit 1 says what the chunk carries. Clear, the
chunk carries part of an image and the header reads:

====== ===== ===========================================================
offset bytes field
====== ===== ===========================================================
0      1     version, always 1
1      1     flags: bit 0 marks the last chunk, every other bit is zero
2      2     reserved, zero
4      4     image sequence, u32, equal to the announcing ``view.image``
8      2     chunk index, u16, from zero
10     2     chunk count, u16, ``ceil(image length / 65,520)``
12     4     image length, u32, 1 to 2 MiB, equal to ``byte_length``
====== ===== ===========================================================

Every chunk but the last carries exactly 65,520 body bytes, so a frame is at
most the 64 KiB frame bound; the last carries the remainder. An image is
announced by ``view.image`` and its chunks follow at once, contiguous and in
order, before any other frame. Anything else is a protocol violation that
refuses as an invalid frame and closes the view connection.

Set, the chunk carries part of a download or upload and the header reads:

====== ===== ===========================================================
offset bytes field
====== ===== ===========================================================
0      1     version, always 1
1      1     flags: bit 0 marks the last chunk, bit 1 is set, every other bit is zero
2      2     reserved, zero
4      4     transfer id, u32, from 1, of a transfer its receiver expects
8      8     byte offset, u64, of the chunk's first body byte
====== ===== ===========================================================

Every chunk but the last carries exactly 65,520 body bytes and the offset is
the byte count before it, so offsets are multiples of 65,520. The last carries
the rest, up to 65,520 bytes, and none only for an empty file. Nothing in the
header or the codec bounds a transfer's total size beyond the 64-bit offset.
A transfer ends with its sender's ``view.transfer_complete``, whose size and
sha256 the receiver checks against what it received.

Transfers share the connection with images. A ``J`` document or a whole image
may sit between two chunks of a transfer, so a file never holds the connection
against the picture; chunks of two transfers never alternate, and no transfer
chunk may sit inside an image's chunk run. Each transfer has its own credit in
chunks, so at most one credit window of file bytes separates one image from
the next, and no file byte is ever dropped. Image semantics are unchanged by
all of this: an image reader still refuses a header that sets flag bit 1.
"""

from __future__ import annotations

from threading import Lock

from ..contracts.contracts import ByteChannel
from ..contracts.view_stream import (
    VIEW_CREDIT_MAX_IMAGES,
    ViewImage,
)
from ..contracts.view_transfer import (
    ViewConnectionUpstreamDocument,
    ViewConnectionUpstreamFrame,
)
from .frame_io import (
    DOCUMENT_FRAME_KIND,
    decode_document,
    read_frame_of_kinds,
)
from .transport_cleanup import close_transport_after_failure
from .view_stream import (
    VIEW_CHUNK_FRAME_KIND,
    ViewTransferChunk,
    ViewTransferReceiver,
    is_view_transfer_chunk,
    view_stream_violation,
)

_UPSTREAM_TRANSFER_KINDS = frozenset({DOCUMENT_FRAME_KIND, VIEW_CHUNK_FRAME_KIND})


class ViewUpstreamReader:
    """Read the control documents and upload chunks a view connection carries from the window.

    Only transfer chunks travel upstream, the bytes of files the person

    supplied; an image chunk refuses. Chunks come back as

    :class:`ViewTransferChunk` through the receiver of uploads, and every

    document comes back after the receiver has applied it. Any violation

    closes the connection.

    """

    def __init__(self, channel: ByteChannel, transfers: ViewTransferReceiver) -> None:
        """Bind the reader to one view connection and the receiver of its uploads."""
        self._channel = channel

        self._transfers = transfers

    def read(self, *, deadline: float) -> ViewConnectionUpstreamDocument | ViewTransferChunk:
        """Return the next control document or upload chunk."""
        try:
            while True:
                kind, payload = read_frame_of_kinds(self._channel, kinds=_UPSTREAM_TRANSFER_KINDS, deadline=deadline)

                if kind == VIEW_CHUNK_FRAME_KIND:
                    if not is_view_transfer_chunk(payload):
                        raise view_stream_violation("view_image_chunk_upstream")

                    chunk = self._transfers.accept(payload)

                    if chunk is not None:
                        return chunk

                    continue

                document = decode_document(payload, ViewConnectionUpstreamFrame).root

                self._transfers.observe(document)

                return document

        except BaseException as error:
            close_transport_after_failure(self._channel, error)

            raise


class ViewImageOutbox:
    """Hold at most one pending image under credit, the newest replacing the older.

    A view connection starts with no credit. Each ``view.credit`` adds to it,

    and credit beyond two outstanding images is a violation. ``take`` spends

    one credit for the pending image; without credit the image waits, and a

    newer ``offer`` replaces it, so nothing is buffered beyond one image.

    """

    def __init__(self) -> None:
        """Start with no credit and no pending image."""
        self._lock = Lock()

        self._credit = 0

        self._pending: tuple[ViewImage, bytes] | None = None

        self._last_sequence: int | None = None

    @property
    def credit(self) -> int:
        """Images the producer may still send."""
        with self._lock:
            return self._credit

    def grant(self, images: int) -> None:
        """Add credit the consumer granted after drawing."""
        with self._lock:
            if images < 1 or self._credit + images > VIEW_CREDIT_MAX_IMAGES:
                raise view_stream_violation("view_credit")

            self._credit += images

    def offer(self, announcement: ViewImage, image: bytes) -> None:
        """Make this the pending image, dropping any older one not yet sent."""
        if announcement.byte_length != len(image):
            raise view_stream_violation("view_image_announcement")

        with self._lock:
            if self._last_sequence is not None and announcement.sequence <= self._last_sequence:
                raise view_stream_violation("view_image_sequence")

            self._last_sequence = announcement.sequence

            self._pending = (announcement, image)

    def take(self) -> tuple[ViewImage, bytes] | None:
        """Spend one credit for the pending image, or return nothing."""
        with self._lock:
            if self._credit == 0 or self._pending is None:
                return None

            pending, self._pending = self._pending, None

            self._credit -= 1

            return pending

    def clear(self) -> None:
        """Drop the pending image."""
        with self._lock:
            self._pending = None
