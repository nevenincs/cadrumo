"""The view connection codec reads the shared vectors exactly, and B stays confined to it."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from typing import Any

import pytest

from cadrumo.core.hashing import canonical_json_bytes

from ...contracts.contracts import RefusalCode, RefusalError
from ...contracts.submission_payload import SubmissionPayloadDescriptor
from ...contracts.tests.view_stream_vector_source import VECTORS_PATH
from ...contracts.view_stream import (
    VIEW_IMAGE_MAX_BYTES,
    ViewCredit,
    ViewImage,
    ViewNavigate,
    ViewNavigateVerb,
    ViewState,
)
from ..frame_io import (
    DOCUMENT_FRAME_KIND,
    MAXIMUM_FRAME_BYTES,
    SESSION_EVENT_FRAME_KIND,
    encode_frame,
    read_document,
    read_document_transfer,
    read_reply_or_event,
    read_secret,
)
from ..view_stream import (
    VIEW_CHUNK_BODY_BYTES,
    VIEW_CHUNK_FRAME_KIND,
    VIEW_CHUNK_HEADER_BYTES,
    AssembledViewImage,
    ViewChunkHeader,
    ViewDownstreamReader,
    ViewImageOutbox,
    read_view_upstream,
    view_image_frames,
    write_view_document,
    write_view_image,
)
from .memory_channel import MemoryChannel

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_VECTORS: dict[str, Any] = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
_MODULUS = _VECTORS["layout"]["image_pattern_modulus"]


def _deadline(seconds: float = 5.0) -> float:
    return time.monotonic() + seconds


def _pair() -> tuple[MemoryChannel, MemoryChannel]:
    writer, reader = MemoryChannel(), MemoryChannel()
    writer.pair(reader)
    return writer, reader


def _pattern(offset: int, length: int) -> bytes:
    return bytes(position % _MODULUS for position in range(offset, offset + length))


def _step_frame(step: dict[str, Any]) -> bytes:
    if "announce" in step:
        return encode_frame(DOCUMENT_FRAME_KIND, canonical_json_bytes(step["announce"]))
    if "document" in step:
        return encode_frame(DOCUMENT_FRAME_KIND, canonical_json_bytes(step["document"]))
    chunk = step["chunk"]
    body = _pattern(chunk["body_offset"], chunk["body_length"])
    return encode_frame(VIEW_CHUNK_FRAME_KIND, bytes.fromhex(chunk["header"]) + body)


def _closed(writer: MemoryChannel) -> bool:
    """Whether the reader closed its end, seen as the writer's next write refusing."""
    try:
        writer.write_all(b"z", deadline=_deadline())
    except RefusalError as error:
        return error.reason is RefusalCode.CONNECTION_CLOSED
    return False


def _summary(item: object) -> dict[str, Any]:
    if isinstance(item, AssembledViewImage):
        return {
            "image": {
                "sequence": item.announcement.sequence,
                "byte_length": len(item.data),
                "sha256": hashlib.sha256(item.data).hexdigest(),
            }
        }
    assert isinstance(item, ViewState)
    return {"document": item.kind}


@pytest.mark.parametrize("case", _VECTORS["headers"], ids=lambda case: case["name"])
def test_an_accepted_header_decodes_and_encodes_exactly(case: dict[str, Any]) -> None:
    raw = bytes.fromhex(case["header"])
    header = ViewChunkHeader.decode(raw + bytes(case["body_length"]))
    assert (header.sequence, header.chunk_index, header.chunk_count, header.image_length, header.last) == (
        case["sequence"],
        case["chunk_index"],
        case["chunk_count"],
        case["image_length"],
        case["last"],
    )
    assert header.body_length == case["body_length"]
    assert header.encode() == raw
    assert len(raw) == VIEW_CHUNK_HEADER_BYTES


@pytest.mark.parametrize("case", _VECTORS["header_refusals"], ids=lambda case: case["name"])
def test_a_refused_header_names_its_check(case: dict[str, Any]) -> None:
    with pytest.raises(RefusalError) as refused:
        ViewChunkHeader.decode(bytes.fromhex(case["header"]) + bytes(case["body_length"]))
    assert refused.value.reason is RefusalCode.INVALID_FRAME
    assert refused.value.check == case["check"]


@pytest.mark.parametrize(
    "case", [case for case in _VECTORS["streams"] if "expect" in case], ids=lambda case: case["name"]
)
def test_an_accepted_stream_yields_its_images_and_documents(case: dict[str, Any]) -> None:
    writer, reader_channel = _pair()
    for step in case["steps"]:
        writer.write_all(_step_frame(step), deadline=_deadline())
    reader = ViewDownstreamReader(reader_channel)
    assert [_summary(reader.read(deadline=_deadline())) for _ in case["expect"]] == case["expect"]
    assert not reader_channel.read_ready()


@pytest.mark.parametrize(
    "case", [case for case in _VECTORS["streams"] if "refused_at" in case], ids=lambda case: case["name"]
)
def test_a_violating_stream_refuses_at_its_step_and_closes(case: dict[str, Any]) -> None:
    refused_at = case["refused_at"]
    writer, reader_channel = _pair()
    for step in case["steps"][:refused_at]:
        writer.write_all(_step_frame(step), deadline=_deadline())
    prefix_reader = ViewDownstreamReader(reader_channel)
    with pytest.raises(RefusalError) as waited:
        while True:
            prefix_reader.read(deadline=_deadline(0.2))
    assert waited.value.reason is RefusalCode.DEADLINE_EXCEEDED

    writer, reader_channel = _pair()
    for step in case["steps"][: refused_at + 1]:
        writer.write_all(_step_frame(step), deadline=_deadline())
    reader = ViewDownstreamReader(reader_channel)
    with pytest.raises(RefusalError) as refused:
        while True:
            reader.read(deadline=_deadline())
    assert refused.value.reason is RefusalCode.INVALID_FRAME
    assert _closed(writer)


@pytest.mark.parametrize("length", [1, VIEW_CHUNK_BODY_BYTES, VIEW_CHUNK_BODY_BYTES + 1, VIEW_IMAGE_MAX_BYTES])
def test_an_image_round_trips_at_the_chunk_and_image_bounds(length: int) -> None:
    image = os.urandom(length)
    announcement = ViewImage(
        sequence=2, byte_length=length, pixel_width=8, pixel_height=8, css_width=8, css_height=8, scale=1.0
    )
    frames = list(view_image_frames(announcement, image))
    assert all(len(frame) <= 5 + MAXIMUM_FRAME_BYTES for frame in frames)
    assert len(frames) == 1 + -(-length // VIEW_CHUNK_BODY_BYTES)
    writer, reader_channel = _pair()
    write_view_image(writer, announcement, image, deadline=_deadline())
    assembled = ViewDownstreamReader(reader_channel).read(deadline=_deadline())
    assert isinstance(assembled, AssembledViewImage)
    assert assembled.announcement == announcement
    assert assembled.data == image


def test_an_image_beyond_two_mebibytes_is_refused_before_any_write() -> None:
    writer, _ = _pair()
    with pytest.raises(ValueError):
        ViewImage(
            sequence=1,
            byte_length=VIEW_IMAGE_MAX_BYTES + 1,
            pixel_width=8,
            pixel_height=8,
            css_width=8,
            css_height=8,
            scale=1.0,
        )
    announcement = ViewImage(
        sequence=1,
        byte_length=VIEW_IMAGE_MAX_BYTES,
        pixel_width=8,
        pixel_height=8,
        css_width=8,
        css_height=8,
        scale=1.0,
    )
    with pytest.raises(RefusalError):
        write_view_image(writer, announcement, bytes(VIEW_IMAGE_MAX_BYTES + 1), deadline=_deadline())
    assert writer.writes == []


def _chunk_frame() -> bytes:
    header = ViewChunkHeader(sequence=1, chunk_index=0, chunk_count=1, image_length=1)
    return encode_frame(VIEW_CHUNK_FRAME_KIND, header.encode() + b"\x00")


_DOCUMENT_READERS: dict[str, Callable[[MemoryChannel], object]] = {
    "read_document": lambda channel: read_document(channel, ViewCredit, deadline=_deadline()),
    "read_reply_or_event": lambda channel: read_reply_or_event(channel, ViewCredit, deadline=_deadline()),
    "read_document_transfer": lambda channel: read_document_transfer(
        channel,
        SubmissionPayloadDescriptor(byte_count=2, payload_digest="0" * 64),
        ViewCredit,
        deadline=_deadline(),
    ),
    "read_view_upstream": lambda channel: read_view_upstream(channel, deadline=_deadline()),
}


def _read_secret(channel: MemoryChannel) -> None:
    with read_secret(channel, deadline=_deadline()):
        pass


@pytest.mark.parametrize("read", [*_DOCUMENT_READERS.values(), _read_secret], ids=[*_DOCUMENT_READERS, "read_secret"])
def test_every_other_reader_refuses_a_chunk_frame_and_closes(read: Callable[[MemoryChannel], object]) -> None:
    writer, reader_channel = _pair()
    writer.write_all(_chunk_frame(), deadline=_deadline())
    with pytest.raises(RefusalError) as refused:
        read(reader_channel)
    assert refused.value.reason is RefusalCode.INVALID_FRAME
    assert _closed(writer)


@pytest.mark.parametrize("kind", [SESSION_EVENT_FRAME_KIND, b"S"])
def test_a_view_connection_refuses_event_and_secret_frames(kind: bytes) -> None:
    writer, reader_channel = _pair()
    writer.write_all(encode_frame(kind, b"{}"), deadline=_deadline())
    with pytest.raises(RefusalError) as refused:
        ViewDownstreamReader(reader_channel).read(deadline=_deadline())
    assert refused.value.reason is RefusalCode.INVALID_FRAME
    assert _closed(writer)


def test_upstream_documents_round_trip_and_downstream_ones_are_refused() -> None:
    writer, reader_channel = _pair()
    navigate = ViewNavigate(verb=ViewNavigateVerb.BACK)
    write_view_document(writer, navigate, deadline=_deadline())
    assert read_view_upstream(reader_channel, deadline=_deadline()) == navigate

    writer.write_all(
        encode_frame(DOCUMENT_FRAME_KIND, canonical_json_bytes({"kind": "view.closed", "reason": "cancelled"})),
        deadline=_deadline(),
    )
    with pytest.raises(RefusalError):
        read_view_upstream(reader_channel, deadline=_deadline())
    assert _closed(writer)


def test_an_announcement_is_never_written_without_its_image() -> None:
    writer, _ = _pair()
    announcement = ViewImage(
        sequence=1, byte_length=1, pixel_width=1, pixel_height=1, css_width=1, css_height=1, scale=1.0
    )
    with pytest.raises(RefusalError):
        write_view_document(writer, announcement, deadline=_deadline())
    assert writer.writes == []


def _announcement(sequence: int) -> ViewImage:
    return ViewImage(
        sequence=sequence, byte_length=1, pixel_width=1, pixel_height=1, css_width=1, css_height=1, scale=1.0
    )


def test_the_outbox_keeps_only_the_newest_image_until_credit_arrives() -> None:
    outbox = ViewImageOutbox()
    outbox.offer(_announcement(1), b"a")
    assert outbox.take() is None
    outbox.offer(_announcement(2), b"b")
    outbox.grant(2)
    assert outbox.take() == (_announcement(2), b"b")
    assert outbox.take() is None
    assert outbox.credit == 1
    outbox.offer(_announcement(3), b"c")
    assert outbox.take() == (_announcement(3), b"c")
    outbox.offer(_announcement(4), b"d")
    assert outbox.credit == 0
    assert outbox.take() is None


def test_the_outbox_refuses_credit_beyond_two_and_stale_sequences() -> None:
    outbox = ViewImageOutbox()
    outbox.grant(1)
    with pytest.raises(RefusalError):
        outbox.grant(2)
    outbox.offer(_announcement(5), b"x")
    with pytest.raises(RefusalError):
        outbox.offer(_announcement(5), b"y")
    with pytest.raises(RefusalError):
        outbox.offer(_announcement(6), b"too long")
