"""Validate window and worker transfer frames at the relay boundary."""

from __future__ import annotations

import time

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.view_stream import ViewImage
from cadrumo_client.contracts.view_transfer import ViewConnectionUpstreamDocument, ViewConnectionUpstreamFrame
from cadrumo_client.transport.frame_io import DOCUMENT_FRAME_KIND, decode_document, read_frame_of_kinds
from cadrumo_client.transport.view_stream import (
    VIEW_CHUNK_FRAME_KIND,
    ViewChunkHeader,
    ViewTransferChunkHeader,
    is_view_transfer_chunk,
)

from .view_stream_state import ViewWindowLeg

_FRAME_SECONDS = 5.0
_WORKER_KINDS = frozenset({DOCUMENT_FRAME_KIND, VIEW_CHUNK_FRAME_KIND})


def read_window_frame(leg: ViewWindowLeg) -> ViewConnectionUpstreamDocument | bytes:
    """Read one upstream document, or the payload of one well-formed upload chunk."""
    kind, payload = read_frame_of_kinds(leg.channel, kinds=_WORKER_KINDS, deadline=time.monotonic() + _FRAME_SECONDS)
    if kind == VIEW_CHUNK_FRAME_KIND:
        if not is_view_transfer_chunk(payload):
            raise RefusalError(RefusalCode.INVALID_FRAME, check="view_image_chunk_upstream")
        ViewTransferChunkHeader.decode(payload)
        return payload
    return decode_document(payload, ViewConnectionUpstreamFrame).root


def validate_worker_transfer(payload: bytes) -> None:
    """Refuse unannounced or malformed transfer chunks from the worker."""
    if not is_view_transfer_chunk(payload):
        raise RefusalError(RefusalCode.INVALID_FRAME, check="view_chunk_unannounced")
    ViewTransferChunkHeader.decode(payload)


def validate_image_chunk(payload: bytes, announcement: ViewImage, expected: int) -> ViewChunkHeader:
    """Check that an image chunk belongs to the announced image and arrives in order."""
    header = ViewChunkHeader.decode(payload)
    if (
        header.sequence != announcement.sequence
        or header.image_length != announcement.byte_length
        or header.chunk_index != expected
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME, check="view_chunk_order")
    return header
