"""Python test peer for view windows speaking the downstream wire protocol."""

from __future__ import annotations

from dataclasses import dataclass

from cadrumo_client.contracts.contracts import ByteChannel, RefusalError
from cadrumo_client.contracts.view_stream import (
    ViewClosed,
    ViewImage,
    ViewNotice,
    ViewState,
)
from cadrumo_client.contracts.view_transfer import (
    ViewConnectionDownstreamFrame,
    ViewConnectionUpstreamDocument,
    ViewConnectionUpstreamFrame,
    ViewTransferDownstreamDocument,
)
from cadrumo_client.transport.frame_io import DOCUMENT_FRAME_KIND, decode_document, read_frame_of_kinds
from cadrumo_client.transport.transport_cleanup import close_transport_after_failure
from cadrumo_client.transport.view_stream import (
    VIEW_CHUNK_BODY_BYTES,
    VIEW_CHUNK_FRAME_KIND,
    VIEW_CHUNK_HEADER_BYTES,
    ViewChunkHeader,
    ViewTransferChunk,
    ViewTransferReceiver,
    is_view_transfer_chunk,
    view_stream_violation,
)

_DOWNSTREAM_KINDS = frozenset({DOCUMENT_FRAME_KIND, VIEW_CHUNK_FRAME_KIND})
_UPSTREAM_KINDS = frozenset({DOCUMENT_FRAME_KIND})


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
        return view_stream_violation(check)

    def _require_usable(self) -> None:
        if self._refused:
            raise view_stream_violation("view_stream_refused")


class ViewDownstreamReader:
    """Read documents, complete images and transfer chunks toward a window peer."""

    def __init__(self, channel: ByteChannel, *, transfers: ViewTransferReceiver | None = None) -> None:
        """Bind the peer reader to one view connection."""
        self._channel = channel
        self._assembler = ViewImageAssembler()
        self._transfers = transfers

    @property
    def assembling(self) -> bool:
        """Whether an announced image still awaits chunks."""
        return self._assembler.assembling

    def read(
        self, *, deadline: float
    ) -> ViewState | ViewNotice | ViewClosed | AssembledViewImage | ViewTransferDownstreamDocument | ViewTransferChunk:
        """Return the next control document, complete image or transfer chunk."""
        try:
            while True:
                kind, payload = read_frame_of_kinds(self._channel, kinds=_DOWNSTREAM_KINDS, deadline=deadline)
                if kind == VIEW_CHUNK_FRAME_KIND:
                    item = self._accept_chunk(payload)
                    if item is not None:
                        return item
                    continue
                if self._assembler.assembling:
                    self._assembler.discard()
                    raise view_stream_violation("view_image_interleaved")
                document = decode_document(payload, ViewConnectionDownstreamFrame).root
                if self._transfers is not None:
                    self._transfers.observe(document)
                elif not isinstance(document, (ViewImage, ViewState, ViewNotice, ViewClosed)):
                    raise view_stream_violation("view_transfer_unexpected")
                if isinstance(document, ViewImage):
                    self._assembler.announce(document)
                    continue
                return document
        except BaseException as error:
            self._assembler.discard()
            close_transport_after_failure(self._channel, error)
            raise

    def _accept_chunk(self, payload: bytes) -> AssembledViewImage | ViewTransferChunk | None:
        if is_view_transfer_chunk(payload):
            return self._accept_transfer_chunk(payload)
        return self._assembler.accept(payload)

    def _accept_transfer_chunk(self, payload: bytes) -> ViewTransferChunk | None:
        if self._transfers is None:
            raise view_stream_violation("view_transfer_unexpected")
        if self._assembler.assembling:
            raise view_stream_violation("view_image_interleaved")
        return self._transfers.accept(payload)


def read_view_upstream(channel: ByteChannel, *, deadline: float) -> ViewConnectionUpstreamDocument:
    """Read one control document sent from the test window peer."""
    try:
        _, payload = read_frame_of_kinds(channel, kinds=_UPSTREAM_KINDS, deadline=deadline)
        return decode_document(payload, ViewConnectionUpstreamFrame).root
    except BaseException as error:
        close_transport_after_failure(channel, error)
        raise
