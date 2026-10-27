"""The view connection codec: ``B`` image chunks and ``J`` control documents.

``B`` is legal only on a view connection, and only this module reads or writes
it; every other reader in the transport keeps refusing it. ``S`` and ``E``
never appear on a view connection.

A ``B`` frame's payload is a 16-byte header followed by the chunk body, all
integers in network order:

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
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from dataclasses import dataclass
from threading import Lock

from ..contracts.contracts import ByteChannel, RefusalCode, RefusalError
from ..contracts.view_stream import (
    VIEW_CREDIT_MAX_IMAGES,
    VIEW_IMAGE_MAX_BYTES,
    ViewClosed,
    ViewDownstreamDocument,
    ViewDownstreamFrame,
    ViewImage,
    ViewNotice,
    ViewState,
    ViewUpstreamDocument,
    ViewUpstreamFrame,
)
from .frame_io import (
    DOCUMENT_FRAME_KIND,
    MAXIMUM_FRAME_BYTES,
    decode_document,
    document_frame,
    encode_frame,
    read_frame_of_kinds,
)
from .transport_cleanup import close_transport_after_failure

VIEW_CHUNK_FRAME_KIND = b"B"
"""The binary chunk frame kind, legal only on view connections."""

VIEW_CHUNK_HEADER_BYTES = 16
VIEW_CHUNK_BODY_BYTES = MAXIMUM_FRAME_BYTES - VIEW_CHUNK_HEADER_BYTES
"""65,520: the body every chunk but an image's last carries."""

VIEW_CHUNK_VERSION = 1
VIEW_CHUNK_LAST_FLAG = 0x01

_HEADER = struct.Struct("!BBHIHHI")
_DOWNSTREAM_KINDS = frozenset({DOCUMENT_FRAME_KIND, VIEW_CHUNK_FRAME_KIND})
_UPSTREAM_KINDS = frozenset({DOCUMENT_FRAME_KIND})


def _violation(check: str) -> RefusalError:
    return RefusalError(RefusalCode.INVALID_FRAME, check=check)


def view_chunk_count(image_length: int) -> int:
    """Return how many chunks carry an image of ``image_length`` bytes."""
    if not 0 < image_length <= VIEW_IMAGE_MAX_BYTES:
        raise _violation("view_image_length")
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
            raise _violation("view_chunk_sequence")
        if self.chunk_count != view_chunk_count(self.image_length):
            raise _violation("view_chunk_count")
        if not 0 <= self.chunk_index < self.chunk_count:
            raise _violation("view_chunk_index")

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
            raise _violation("view_chunk_header_length")
        version, flags, reserved, sequence, index, count, length = _HEADER.unpack_from(payload)
        if version != VIEW_CHUNK_VERSION:
            raise _violation("view_chunk_version")
        if reserved != 0 or flags & ~VIEW_CHUNK_LAST_FLAG:
            raise _violation("view_chunk_reserved")
        header = cls(sequence=sequence, chunk_index=index, chunk_count=count, image_length=length)
        if bool(flags & VIEW_CHUNK_LAST_FLAG) != header.last:
            raise _violation("view_chunk_last_flag")
        if len(payload) - VIEW_CHUNK_HEADER_BYTES != header.body_length:
            raise _violation("view_chunk_body_length")
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
        raise _violation("view_image_announcement")
    yield document_frame(announcement)
    for payload in view_image_chunk_payloads(announcement.sequence, image):
        yield encode_frame(VIEW_CHUNK_FRAME_KIND, payload)


def write_view_image(channel: ByteChannel, announcement: ViewImage, image: bytes, *, deadline: float) -> None:
    """Write one announced image, closing the view connection on any failure."""
    try:
        for frame in view_image_frames(announcement, image):
            channel.write_all(frame, deadline=deadline)
    except BaseException as error:
        # A partly written image cannot be resumed; the reader would see an interleaving.
        close_transport_after_failure(channel, error)
        raise


def write_view_document(
    channel: ByteChannel, document: ViewDownstreamDocument | ViewUpstreamDocument, *, deadline: float
) -> None:
    """Write one control document; an image announcement travels only with its image."""
    try:
        if isinstance(document, ViewImage):
            raise _violation("view_image_without_chunks")
        channel.write_all(document_frame(document), deadline=deadline)
    except BaseException as error:
        close_transport_after_failure(channel, error)
        raise


@dataclass(frozen=True, slots=True)
class AssembledViewImage:
    """One complete image with the announcement that described it."""

    announcement: ViewImage
    data: bytes


class ViewImageAssembler:
    """Reassemble announced images from their chunks, refusing every violation.

    Sequences strictly increase across images and may skip values. A refusal
    zeroes the partial image and leaves the assembler unusable.
    """

    def __init__(self) -> None:
        """Start with no image announced."""
        self._announcement: ViewImage | None = None
        self._buffer = bytearray()
        self._next_index = 0
        self._last_sequence: int | None = None
        self._refused = False

    @property
    def assembling(self) -> bool:
        """Whether an announced image still awaits chunks."""
        return self._announcement is not None

    def announce(self, announcement: ViewImage) -> None:
        """Begin the announced image; one already in progress makes this an interleaving."""
        self._require_usable()
        if self._announcement is not None:
            raise self._refuse("view_image_interleaved")
        if self._last_sequence is not None and announcement.sequence <= self._last_sequence:
            raise self._refuse("view_image_sequence")
        self._announcement = announcement
        self._last_sequence = announcement.sequence
        self._buffer = bytearray(announcement.byte_length)
        self._next_index = 0

    def accept(self, payload: bytes) -> AssembledViewImage | None:
        """Add one ``B`` payload; return the image once its last chunk arrives."""
        self._require_usable()
        announcement = self._announcement
        if announcement is None:
            raise self._refuse("view_chunk_unannounced")
        try:
            header = ViewChunkHeader.decode(payload)
        except RefusalError:
            raise self._refuse("view_chunk_header") from None
        if header.sequence != announcement.sequence:
            raise self._refuse("view_image_interleaved")
        if header.image_length != announcement.byte_length:
            raise self._refuse("view_image_announcement")
        if header.chunk_index != self._next_index:
            raise self._refuse("view_chunk_order")
        offset = header.chunk_index * VIEW_CHUNK_BODY_BYTES
        self._buffer[offset : offset + header.body_length] = payload[VIEW_CHUNK_HEADER_BYTES:]
        self._next_index += 1
        if not header.last:
            return None
        image = AssembledViewImage(announcement=announcement, data=bytes(self._buffer))
        self._clear()
        return image

    def discard(self) -> None:
        """Zero and drop any partial image."""
        self._clear()

    def _clear(self) -> None:
        self._buffer[:] = bytes(len(self._buffer))
        self._buffer = bytearray()
        self._announcement = None
        self._next_index = 0

    def _refuse(self, check: str) -> RefusalError:
        self._clear()
        self._refused = True
        return _violation(check)

    def _require_usable(self) -> None:
        if self._refused:
            raise _violation("view_stream_refused")


class ViewDownstreamReader:
    """Read the documents and complete images a view connection carries toward the window.

    ``view.image`` is consumed here and returned only with its assembled
    bytes. A ``B`` frame without an announcement, a document inside an
    image, or any other kind refuses and closes the connection.
    """

    def __init__(self, channel: ByteChannel) -> None:
        """Bind the reader to one view connection."""
        self._channel = channel
        self._assembler = ViewImageAssembler()

    def read(self, *, deadline: float) -> ViewState | ViewNotice | ViewClosed | AssembledViewImage:
        """Return the next control document or complete image."""
        try:
            while True:
                kind, payload = read_frame_of_kinds(self._channel, kinds=_DOWNSTREAM_KINDS, deadline=deadline)
                if kind == VIEW_CHUNK_FRAME_KIND:
                    image = self._assembler.accept(payload)
                    if image is not None:
                        return image
                    continue
                if self._assembler.assembling:
                    self._assembler.discard()
                    raise _violation("view_image_interleaved")
                document = decode_document(payload, ViewDownstreamFrame).root
                if isinstance(document, ViewImage):
                    self._assembler.announce(document)
                    continue
                return document
        except BaseException as error:
            self._assembler.discard()
            close_transport_after_failure(self._channel, error)
            raise


def read_view_upstream(channel: ByteChannel, *, deadline: float) -> ViewUpstreamDocument:
    """Read one control document sent from the window; ``B`` never travels upstream."""
    try:
        _, payload = read_frame_of_kinds(channel, kinds=_UPSTREAM_KINDS, deadline=deadline)
        return decode_document(payload, ViewUpstreamFrame).root
    except BaseException as error:
        close_transport_after_failure(channel, error)
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
                raise _violation("view_credit")
            self._credit += images

    def offer(self, announcement: ViewImage, image: bytes) -> None:
        """Make this the pending image, dropping any older one not yet sent."""
        if announcement.byte_length != len(image):
            raise _violation("view_image_announcement")
        with self._lock:
            if self._last_sequence is not None and announcement.sequence <= self._last_sequence:
                raise _violation("view_image_sequence")
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
