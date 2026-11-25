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

import hashlib
import struct
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

from ..contracts.contracts import ByteChannel, RefusalCode, RefusalError
from ..contracts.view_stream import (
    VIEW_IMAGE_MAX_BYTES,
    ViewDownstreamDocument,
    ViewImage,
    ViewUpstreamDocument,
)
from ..contracts.view_transfer import (
    VIEW_MAX_TRANSFER_ID,
    VIEW_MAX_TRANSFER_SIZE,
    VIEW_TRANSFER_CREDIT_MAX_CHUNKS,
    ViewConnectionDownstreamDocument,
    ViewConnectionUpstreamDocument,
    ViewTransferCancel,
    ViewTransferComplete,
    ViewTransferCredit,
    ViewTransferDirection,
    ViewTransferDownstreamDocument,
    ViewTransferUpstreamDocument,
)
from .frame_io import (
    MAXIMUM_FRAME_BYTES,
    document_frame,
    encode_frame,
)
from .transport_cleanup import close_transport_after_failure

VIEW_CHUNK_FRAME_KIND = b"B"

"""The binary chunk frame kind, legal only on view connections."""


VIEW_CHUNK_HEADER_BYTES = 16

VIEW_CHUNK_BODY_BYTES = MAXIMUM_FRAME_BYTES - VIEW_CHUNK_HEADER_BYTES

"""65,520: the body every chunk but an image's last carries."""


VIEW_CHUNK_VERSION = 1

VIEW_CHUNK_LAST_FLAG = 0x01

VIEW_CHUNK_TRANSFER_FLAG = 0x02

"""Set on the chunks of a download or upload, clear on the chunks of an image."""


_HEADER = struct.Struct("!BBHIHHI")

_TRANSFER_HEADER = struct.Struct("!BBHIQ")


def view_stream_violation(check: str) -> RefusalError:
    """Refuse an invalid view frame with its precise check."""
    return RefusalError(RefusalCode.INVALID_FRAME, check=check)


def view_chunk_count(image_length: int) -> int:
    """Return how many chunks carry an image of ``image_length`` bytes."""
    if not 0 < image_length <= VIEW_IMAGE_MAX_BYTES:
        raise view_stream_violation("view_image_length")

    return -(-image_length // VIEW_CHUNK_BODY_BYTES)


@dataclass(frozen=True, slots=True)
class ViewChunkHeader:
    """One validated chunk header; ``last`` follows from index and count."""

    sequence: int

    chunk_index: int

    chunk_count: int

    image_length: int

    def __post_init__(self) -> None:
        """Refuse any header the layout does not admit."""
        if not 0 <= self.sequence <= 0xFFFFFFFF:
            raise view_stream_violation("view_chunk_sequence")

        if self.chunk_count != view_chunk_count(self.image_length):
            raise view_stream_violation("view_chunk_count")

        if not 0 <= self.chunk_index < self.chunk_count:
            raise view_stream_violation("view_chunk_index")

    @property
    def last(self) -> bool:
        """Whether this chunk ends its image."""
        return self.chunk_index == self.chunk_count - 1

    @property
    def body_length(self) -> int:
        """The exact body length this chunk must carry."""
        if self.last:
            return self.image_length - VIEW_CHUNK_BODY_BYTES * (self.chunk_count - 1)

        return VIEW_CHUNK_BODY_BYTES

    def encode(self) -> bytes:
        """Return the 16 header bytes."""
        flags = VIEW_CHUNK_LAST_FLAG if self.last else 0

        return _HEADER.pack(
            VIEW_CHUNK_VERSION, flags, 0, self.sequence, self.chunk_index, self.chunk_count, self.image_length
        )

    @classmethod
    def decode(cls, payload: bytes) -> ViewChunkHeader:
        """Validate a ``B`` payload's header and body length, returning the header."""
        if len(payload) < VIEW_CHUNK_HEADER_BYTES:
            raise view_stream_violation("view_chunk_header_length")

        version, flags, reserved, sequence, index, count, length = _HEADER.unpack_from(payload)

        if version != VIEW_CHUNK_VERSION:
            raise view_stream_violation("view_chunk_version")

        if reserved != 0 or flags & ~VIEW_CHUNK_LAST_FLAG:
            raise view_stream_violation("view_chunk_reserved")

        header = cls(sequence=sequence, chunk_index=index, chunk_count=count, image_length=length)

        if bool(flags & VIEW_CHUNK_LAST_FLAG) != header.last:
            raise view_stream_violation("view_chunk_last_flag")

        if len(payload) - VIEW_CHUNK_HEADER_BYTES != header.body_length:
            raise view_stream_violation("view_chunk_body_length")

        return header


def view_image_chunk_payloads(sequence: int, image: bytes) -> Iterator[bytes]:
    """Split one image into its ordered ``B`` payloads, header included."""
    count = view_chunk_count(len(image))

    for index in range(count):
        header = ViewChunkHeader(sequence=sequence, chunk_index=index, chunk_count=count, image_length=len(image))

        offset = index * VIEW_CHUNK_BODY_BYTES

        yield header.encode() + image[offset : offset + VIEW_CHUNK_BODY_BYTES]


def view_image_frames(announcement: ViewImage, image: bytes) -> Iterator[bytes]:
    """Yield the announcing ``J`` frame and then every ``B`` frame of one image."""
    if announcement.byte_length != len(image):
        raise view_stream_violation("view_image_announcement")

    yield document_frame(announcement)

    for payload in view_image_chunk_payloads(announcement.sequence, image):
        yield encode_frame(VIEW_CHUNK_FRAME_KIND, payload)


def _write_frames(channel: ByteChannel, frames: Iterable[bytes], *, deadline: float) -> None:
    """Write frames in order; any failure, building a frame included, closes the view connection."""
    try:
        for frame in frames:
            channel.write_all(frame, deadline=deadline)

    except BaseException as error:
        # A partly written run cannot be resumed; the reader would see an interleaving.

        close_transport_after_failure(channel, error)

        raise


def write_view_image(channel: ByteChannel, announcement: ViewImage, image: bytes, *, deadline: float) -> None:
    """Write one announced image, closing the view connection on any failure."""
    _write_frames(channel, view_image_frames(announcement, image), deadline=deadline)


def _document_frames(document: ViewDownstreamDocument | ViewUpstreamDocument) -> Iterator[bytes]:

    if isinstance(document, ViewImage):
        raise view_stream_violation("view_image_without_chunks")

    yield document_frame(document)


def write_view_document(
    channel: ByteChannel, document: ViewDownstreamDocument | ViewUpstreamDocument, *, deadline: float
) -> None:
    """Write one control document; an image announcement travels only with its image."""
    _write_frames(channel, _document_frames(document), deadline=deadline)


def is_view_transfer_chunk(payload: bytes) -> bool:
    """Whether a ``B`` payload's flags say it carries a transfer rather than an image."""
    return len(payload) > 1 and bool(payload[1] & VIEW_CHUNK_TRANSFER_FLAG)


@dataclass(frozen=True, slots=True)
class ViewTransferChunkHeader:
    """One validated transfer chunk header; ``body_length`` is what the chunk carries."""

    transfer_id: int

    offset: int

    last: bool

    body_length: int

    def __post_init__(self) -> None:
        """Refuse any header the layout does not admit."""
        if not 1 <= self.transfer_id <= VIEW_MAX_TRANSFER_ID:
            raise view_stream_violation("view_transfer_id")

        if not 0 <= self.offset <= VIEW_MAX_TRANSFER_SIZE or self.offset % VIEW_CHUNK_BODY_BYTES:
            raise view_stream_violation("view_transfer_offset")

        if self.last:
            # Only an empty file has an empty chunk, and then it is the one chunk.

            admitted = 0 <= self.body_length <= VIEW_CHUNK_BODY_BYTES and (self.body_length > 0 or self.offset == 0)

        else:
            admitted = self.body_length == VIEW_CHUNK_BODY_BYTES

        if not admitted:
            raise view_stream_violation("view_transfer_body_length")

    def encode(self) -> bytes:
        """Return the 16 header bytes."""
        flags = VIEW_CHUNK_TRANSFER_FLAG | (VIEW_CHUNK_LAST_FLAG if self.last else 0)

        return _TRANSFER_HEADER.pack(VIEW_CHUNK_VERSION, flags, 0, self.transfer_id, self.offset)

    @classmethod
    def decode(cls, payload: bytes) -> ViewTransferChunkHeader:
        """Validate a transfer ``B`` payload's header and body length, returning the header."""
        if len(payload) < VIEW_CHUNK_HEADER_BYTES:
            raise view_stream_violation("view_chunk_header_length")

        version, flags, reserved, transfer_id, offset = _TRANSFER_HEADER.unpack_from(payload)

        if version != VIEW_CHUNK_VERSION:
            raise view_stream_violation("view_chunk_version")

        if reserved != 0 or flags & ~(VIEW_CHUNK_LAST_FLAG | VIEW_CHUNK_TRANSFER_FLAG):
            raise view_stream_violation("view_chunk_reserved")

        if not flags & VIEW_CHUNK_TRANSFER_FLAG:
            raise view_stream_violation("view_transfer_flag")

        return cls(
            transfer_id=transfer_id,
            offset=offset,
            last=bool(flags & VIEW_CHUNK_LAST_FLAG),
            body_length=len(payload) - VIEW_CHUNK_HEADER_BYTES,
        )


@dataclass(frozen=True, slots=True)
class ViewTransferChunk:
    """One checked chunk of an expected transfer, for the receiver to write out in order."""

    transfer_id: int

    offset: int

    data: bytes

    last: bool


class _InboundTransfer:
    """What a receiver knows about one transfer it expects."""

    __slots__ = ("cancelled", "credit", "declared_size", "digest", "last_seen", "received")

    def __init__(self, declared_size: int | None) -> None:

        self.declared_size = declared_size

        self.received = 0

        self.credit = 0

        self.last_seen = False

        self.cancelled = False

        self.digest = hashlib.sha256()


class ViewTransferReceiver:
    """Check the transfers one end of a view connection receives, refusing every violation.

    The application names each transfer it is ready to take with ``expect`` and

    admits chunks with ``grant``. A chunk of any other transfer, one beyond the

    credit granted, or one out of order is a violation. At most one transfer

    streams at a time: once a transfer's first chunk has arrived, a chunk of

    another transfer before its last is an interleaving, while documents and

    whole images may sit between chunks. A transfer ends with the sender's

    ``view.transfer_complete``, which must agree in size and sha256 with the

    bytes received, and in size with the sender's declared size when it gave

    one. A violation leaves the receiver unusable and must close the view

    connection; bytes the application already wrote out are its to discard.



    ``expect``, ``grant`` and ``cancel`` belong to the application; ``accept``

    and ``observe`` belong to the connection's reader, which may run on

    another thread.

    """

    def __init__(self, direction: ViewTransferDirection) -> None:
        """Receive the transfers whose bytes travel in ``direction``."""
        self._direction = direction

        self._lock = Lock()

        self._transfers: dict[int, _InboundTransfer] = {}

        self._last_id = 0

        self._streaming: int | None = None

        self._refused = False

    @property
    def direction(self) -> ViewTransferDirection:
        """The direction of the transfers this end receives."""
        return self._direction

    def expect(self, transfer_id: int, *, size: int | None = None) -> None:
        """Register a transfer this end will receive; ids strictly increase.

        ``size`` is the exact byte count the sender declared, or ``None``.

        """
        with self._lock:
            self._require_usable()

            if not self._last_id < transfer_id <= VIEW_MAX_TRANSFER_ID:
                raise view_stream_violation("view_transfer_id")

            if size is not None and not 0 <= size <= VIEW_MAX_TRANSFER_SIZE:
                raise view_stream_violation("view_transfer_size")

            self._last_id = transfer_id

            self._transfers[transfer_id] = _InboundTransfer(size)

    def grant(self, transfer_id: int, chunks: int) -> ViewTransferCredit:
        """Admit ``chunks`` more chunks of a transfer; return the credit document to send."""
        with self._lock:
            self._require_usable()

            transfer = self._transfers.get(transfer_id)

            if transfer is None:
                raise view_stream_violation("view_transfer_unknown")

            if transfer.cancelled or transfer.last_seen:
                raise view_stream_violation("view_transfer_closed")

            if chunks < 1 or transfer.credit + chunks > VIEW_TRANSFER_CREDIT_MAX_CHUNKS:
                raise view_stream_violation("view_transfer_credit")

            transfer.credit += chunks

        return ViewTransferCredit(transfer_id=transfer_id, chunks=chunks)

    def cancel(self, transfer_id: int) -> ViewTransferCancel | None:
        """Stop receiving a transfer; return the cancel document to send, if one is due.

        Chunks the sender had already sent are discarded until the sender's own

        cancel or completion arrives.

        """
        with self._lock:
            transfer = self._transfers.get(transfer_id)

            if transfer is None or transfer.cancelled:
                return None

            transfer.cancelled = True

        return ViewTransferCancel(direction=self._direction, transfer_id=transfer_id)

    def accept(self, payload: bytes) -> ViewTransferChunk | None:
        """Check one transfer ``B`` payload; return its chunk, or ``None`` when a cancel discards it."""
        with self._lock:
            self._require_usable()

            try:
                header = ViewTransferChunkHeader.decode(payload)

            except RefusalError:
                raise self._refuse("view_transfer_header") from None

            transfer = self._transfers.get(header.transfer_id)

            if transfer is None:
                raise self._refuse("view_transfer_unknown")

            self._validate_chunk_order(header, transfer)
            transfer.credit -= 1

            transfer.received += header.body_length

            transfer.last_seen = header.last

            self._streaming = None if header.last else header.transfer_id

            if transfer.cancelled:
                return None

            body = payload[VIEW_CHUNK_HEADER_BYTES:]

            transfer.digest.update(body)

            return ViewTransferChunk(transfer_id=header.transfer_id, offset=header.offset, data=body, last=header.last)

    def _validate_chunk_order(self, header: ViewTransferChunkHeader, transfer: _InboundTransfer) -> None:
        if self._streaming not in {None, header.transfer_id}:
            raise self._refuse("view_transfer_interleaved")

        if transfer.last_seen or header.offset != transfer.received:
            raise self._refuse("view_transfer_order")

        if transfer.credit == 0:
            raise self._refuse("view_transfer_credit")

        received = transfer.received + header.body_length

        limit = VIEW_MAX_TRANSFER_SIZE if transfer.declared_size is None else transfer.declared_size

        if received > limit:
            raise self._refuse("view_transfer_size")

    def observe(self, document: ViewConnectionDownstreamDocument | ViewConnectionUpstreamDocument) -> None:
        """Apply a document read from the same connection: the completion or cancel of an inbound transfer."""
        with self._lock:
            self._require_usable()

            if isinstance(document, ViewTransferComplete):
                self._complete(document)

            elif isinstance(document, ViewTransferCancel) and document.direction is self._direction:
                self._transfers.pop(document.transfer_id, None)

                if self._streaming == document.transfer_id:
                    self._streaming = None

    def _complete(self, document: ViewTransferComplete) -> None:

        transfer = self._transfers.get(document.transfer_id)

        if transfer is None:
            raise self._refuse("view_transfer_unknown")

        if not transfer.last_seen:
            raise self._refuse("view_transfer_incomplete")

        if document.size != transfer.received or transfer.declared_size not in {None, transfer.received}:
            raise self._refuse("view_transfer_size")

        if not transfer.cancelled and document.sha256 != transfer.digest.hexdigest():
            raise self._refuse("view_transfer_digest")

        del self._transfers[document.transfer_id]

    def _refuse(self, check: str) -> RefusalError:

        self._transfers.clear()

        self._streaming = None

        self._refused = True

        return view_stream_violation(check)

    def _require_usable(self) -> None:

        if self._refused:
            raise view_stream_violation("view_stream_refused")


class ViewTransferSource(Protocol):
    """Where a sender reads a transfer's bytes from, such as a binary file object."""

    def read(self, size: int, /) -> bytes:
        """Return at most ``size`` bytes, and nothing once the bytes end."""
        ...


class ViewTransferSender:
    """Cut one transfer's bytes into ordered ``B`` payloads, one per unit of credit.

    A transfer starts with no credit. The peer's ``view.transfer_credit``

    documents add to it through ``grant``, and ``next_payload`` spends one unit

    per chunk, so the sender never sends a chunk the receiver has not admitted

    and never drops a byte: without credit it yields nothing and the bytes

    stay in the source. The source is read one chunk ahead, so a file of any

    size passes through without being held, and the chunk that ends it is

    known to be last. After the last chunk, ``completion`` is the

    ``view.transfer_complete`` to send.



    ``grant`` and ``cancel`` may be called from another thread than

    ``next_payload`` and ``completion``, which belong to the single writer.

    """

    def __init__(self, transfer_id: int, source: ViewTransferSource) -> None:
        """Send ``source`` as transfer ``transfer_id``."""
        if not 1 <= transfer_id <= VIEW_MAX_TRANSFER_ID:
            raise view_stream_violation("view_transfer_id")

        self._transfer_id = transfer_id

        self._source = source

        self._lock = Lock()

        self._credit = 0

        self._cancelled = False

        self._done = False

        self._started = False

        self._pending = b""

        self._offset = 0

        self._digest = hashlib.sha256()

    @property
    def transfer_id(self) -> int:
        """The id this sender's chunks carry."""
        return self._transfer_id

    @property
    def credit(self) -> int:
        """Chunks the receiver has admitted and this sender has not yet sent."""
        with self._lock:
            return self._credit

    @property
    def done(self) -> bool:
        """Whether the last chunk has been produced."""
        with self._lock:
            return self._done

    def grant(self, chunks: int) -> None:
        """Add the credit a ``view.transfer_credit`` document granted."""
        with self._lock:
            if chunks < 1 or self._credit + chunks > VIEW_TRANSFER_CREDIT_MAX_CHUNKS:
                raise view_stream_violation("view_transfer_credit")

            self._credit += chunks

    def cancel(self) -> None:
        """Stop producing chunks; the caller sends the cancel document."""
        with self._lock:
            self._cancelled = True

            self._credit = 0

    def next_payload(self) -> bytes | None:
        """Return the next ``B`` payload, or ``None`` without credit, once done or once cancelled."""
        with self._lock:
            if self._cancelled:
                self._pending = b""

                return None

            if self._done or self._credit == 0:
                return None

            self._credit -= 1

        if not self._started:
            self._pending = self._read_chunk()

            self._started = True

        body = self._pending

        last = len(body) < VIEW_CHUNK_BODY_BYTES

        if last:
            self._pending = b""

        else:
            self._pending = self._read_chunk()

            last = not self._pending

        header = ViewTransferChunkHeader(
            transfer_id=self._transfer_id, offset=self._offset, last=last, body_length=len(body)
        )

        self._offset += len(body)

        self._digest.update(body)

        with self._lock:
            self._done = last

        return header.encode() + body

    def completion(self) -> ViewTransferComplete:
        """Return the completion document for the bytes sent; valid once the last chunk is produced."""
        with self._lock:
            if not self._done:
                raise view_stream_violation("view_transfer_incomplete")

        return ViewTransferComplete(transfer_id=self._transfer_id, size=self._offset, sha256=self._digest.hexdigest())

    def _read_chunk(self) -> bytes:
        """Read a full chunk, or the short remainder that ends the source."""
        parts: list[bytes] = []

        remaining = VIEW_CHUNK_BODY_BYTES

        while remaining:
            block = self._source.read(remaining)

            if not block:
                break

            if len(block) > remaining:
                raise view_stream_violation("view_transfer_source")

            parts.append(block)

            remaining -= len(block)

        return b"".join(parts)


def _transfer_chunk_frames(payload: bytes) -> Iterator[bytes]:

    ViewTransferChunkHeader.decode(payload)

    yield encode_frame(VIEW_CHUNK_FRAME_KIND, payload)


def write_view_transfer_chunk(channel: ByteChannel, payload: bytes, *, deadline: float) -> None:
    """Write one transfer ``B`` frame; an invalid chunk is refused before any write, a failure closes the connection."""
    _write_frames(channel, _transfer_chunk_frames(payload), deadline=deadline)


def _transfer_document_frames(
    document: ViewTransferDownstreamDocument | ViewTransferUpstreamDocument,
) -> Iterator[bytes]:

    yield document_frame(document)


def write_view_transfer_document(
    channel: ByteChannel,
    document: ViewTransferDownstreamDocument | ViewTransferUpstreamDocument,
    *,
    deadline: float,
) -> None:
    """Write one transfer control document, closing the view connection on any failure."""
    _write_frames(channel, _transfer_document_frames(document), deadline=deadline)
