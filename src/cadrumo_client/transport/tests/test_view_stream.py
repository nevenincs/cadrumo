"""The view connection codec reads the shared vectors exactly, and B stays confined to it."""

from __future__ import annotations

import hashlib
import io
import json
import os
import time
from collections.abc import Callable
from typing import Any

import pytest

from cadrumo.core.hashing import canonical_json_bytes
from cadrumo_client.transport.view_stream_readers import (
    ViewImageOutbox,
    ViewUpstreamReader,
)

from ...contracts.contracts import RefusalCode, RefusalError
from ...contracts.submission_payload import SubmissionPayloadDescriptor
from ...contracts.tests.view_stream_vector_source import VECTORS_PATH
from ...contracts.view_stream import (
    VIEW_IMAGE_MAX_BYTES,
    ViewCredit,
    ViewImage,
    ViewNavigate,
    ViewNavigateVerb,
)
from ...contracts.view_transfer import (
    VIEW_TRANSFER_CREDIT_MAX_CHUNKS,
    ViewTransferCancel,
    ViewTransferComplete,
    ViewTransferCredit,
    ViewTransferDirection,
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
    ViewChunkHeader,
    ViewTransferChunk,
    ViewTransferChunkHeader,
    ViewTransferReceiver,
    ViewTransferSender,
    is_view_transfer_chunk,
    view_image_frames,
    write_view_document,
    write_view_image,
    write_view_transfer_chunk,
    write_view_transfer_document,
)
from .memory_channel import MemoryChannel
from .view_stream_peer import AssembledViewImage, ViewDownstreamReader, read_view_upstream

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
    if isinstance(item, ViewTransferChunk):
        assert item.data == _pattern(item.offset, len(item.data))
        return {
            "chunk": {
                "transfer_id": item.transfer_id,
                "offset": item.offset,
                "length": len(item.data),
                "last": item.last,
                "sha256": hashlib.sha256(item.data).hexdigest(),
            }
        }
    kind = getattr(item, "kind", None)
    assert isinstance(kind, str)
    return {"document": kind}


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


def _stream_cases(field: str) -> list[Any]:
    """The image stream vectors and then the transfer ones that carry ``field``, each under its own id."""
    return [
        *(pytest.param(case, id=case["name"]) for case in _VECTORS["streams"] if field in case),
        *(pytest.param(case, id=f"transfer_{case['name']}") for case in _VECTORS["transfer_streams"] if field in case),
    ]


def _reader_for(case: dict[str, Any], channel: MemoryChannel) -> ViewDownstreamReader | ViewUpstreamReader:
    """The reader a vector names: images alone, or a transfer-capable one set up as its ``setup`` says."""
    if "setup" not in case:
        return ViewDownstreamReader(channel)
    downstream = case["direction"] == "downstream"
    receiver = ViewTransferReceiver(ViewTransferDirection.DOWNLOAD if downstream else ViewTransferDirection.UPLOAD)
    for action in case["setup"]:
        if "expect" in action:
            receiver.expect(action["expect"]["transfer_id"], size=action["expect"]["size"])
        elif "grant" in action:
            receiver.grant(action["grant"]["transfer_id"], action["grant"]["chunks"])
        else:
            receiver.cancel(action["cancel"]["transfer_id"])
    return ViewDownstreamReader(channel, transfers=receiver) if downstream else ViewUpstreamReader(channel, receiver)


@pytest.mark.parametrize("case", _stream_cases("expect"))
def test_an_accepted_stream_yields_its_images_chunks_and_documents(case: dict[str, Any]) -> None:
    writer, reader_channel = _pair()
    for step in case["steps"]:
        writer.write_all(_step_frame(step), deadline=_deadline())
    reader = _reader_for(case, reader_channel)
    assert [_summary(reader.read(deadline=_deadline())) for _ in case["expect"]] == case["expect"]
    assert not reader_channel.read_ready()


@pytest.mark.parametrize("case", _stream_cases("refused_at"))
def test_a_violating_stream_refuses_at_its_step_and_closes(case: dict[str, Any]) -> None:
    refused_at = case["refused_at"]
    writer, reader_channel = _pair()
    for step in case["steps"][:refused_at]:
        writer.write_all(_step_frame(step), deadline=_deadline())
    prefix_reader = _reader_for(case, reader_channel)
    with pytest.raises(RefusalError) as waited:
        while True:
            prefix_reader.read(deadline=_deadline(0.2))
    assert waited.value.reason is RefusalCode.TIMEOUT

    writer, reader_channel = _pair()
    for step in case["steps"][: refused_at + 1]:
        writer.write_all(_step_frame(step), deadline=_deadline())
    reader = _reader_for(case, reader_channel)
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


def _transfer_chunk_frame() -> bytes:
    header = ViewTransferChunkHeader(transfer_id=1, offset=0, last=True, body_length=1)
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


@pytest.mark.parametrize("frame", [_chunk_frame, _transfer_chunk_frame], ids=["image_chunk", "transfer_chunk"])
@pytest.mark.parametrize("read", [*_DOCUMENT_READERS.values(), _read_secret], ids=[*_DOCUMENT_READERS, "read_secret"])
def test_every_other_reader_refuses_a_chunk_frame_and_closes(
    read: Callable[[MemoryChannel], object], frame: Callable[[], bytes]
) -> None:
    writer, reader_channel = _pair()
    writer.write_all(frame(), deadline=_deadline())
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


# --- transfers ---------------------------------------------------------------


@pytest.mark.parametrize("case", _VECTORS["transfer_headers"], ids=lambda case: case["name"])
def test_an_accepted_transfer_header_decodes_and_encodes_exactly(case: dict[str, Any]) -> None:
    raw = bytes.fromhex(case["header"])
    payload = raw + bytes(case["body_length"])
    header = ViewTransferChunkHeader.decode(payload)
    assert (header.transfer_id, header.offset, header.last, header.body_length) == (
        case["transfer_id"],
        case["offset"],
        case["last"],
        case["body_length"],
    )
    assert header.encode() == raw
    assert len(raw) == VIEW_CHUNK_HEADER_BYTES
    assert is_view_transfer_chunk(payload)
    with pytest.raises(RefusalError):
        ViewChunkHeader.decode(payload)


@pytest.mark.parametrize("case", _VECTORS["transfer_header_refusals"], ids=lambda case: case["name"])
def test_a_refused_transfer_header_names_its_check(case: dict[str, Any]) -> None:
    with pytest.raises(RefusalError) as refused:
        ViewTransferChunkHeader.decode(bytes.fromhex(case["header"]) + bytes(case["body_length"]))
    assert refused.value.reason is RefusalCode.INVALID_FRAME
    assert refused.value.check == case["check"]


def test_the_transfer_flag_alone_tells_a_transfer_chunk_from_an_image_chunk() -> None:
    assert not is_view_transfer_chunk(b"")
    assert not is_view_transfer_chunk(b"\x01")
    assert not is_view_transfer_chunk(_chunk_frame()[5:])
    assert is_view_transfer_chunk(_transfer_chunk_frame()[5:])
    for case in _VECTORS["headers"]:
        assert not is_view_transfer_chunk(bytes.fromhex(case["header"]))
    for case in _VECTORS["transfer_headers"]:
        assert is_view_transfer_chunk(bytes.fromhex(case["header"]))


class _Source:
    """A byte source that counts its reads and can answer in short pieces."""

    def __init__(self, data: bytes, *, piece: int | None = None, overrun: bool = False) -> None:
        self._data = io.BytesIO(data)
        self._piece = piece
        self._overrun = overrun
        self.reads = 0

    def read(self, size: int, /) -> bytes:
        self.reads += 1
        if self._overrun:
            return bytes(size + 1)
        return self._data.read(size if self._piece is None else min(size, self._piece))


def _receiving_end(
    direction: ViewTransferDirection = ViewTransferDirection.DOWNLOAD,
) -> tuple[MemoryChannel, MemoryChannel, ViewTransferReceiver, ViewDownstreamReader]:
    writer, reader_channel = _pair()
    receiver = ViewTransferReceiver(direction)
    return writer, reader_channel, receiver, ViewDownstreamReader(reader_channel, transfers=receiver)


def _run_transfer(data: bytes, *, declared: bool) -> tuple[bytes, int]:
    """Send ``data`` through real framing and credit; return the bytes written out and the largest burst."""
    writer, reader_channel, receiver, reader = _receiving_end()
    credit_writer, credit_channel = _pair()
    credit_reader = ViewUpstreamReader(credit_channel, ViewTransferReceiver(ViewTransferDirection.UPLOAD))
    sender = ViewTransferSender(1, io.BytesIO(data))
    receiver.expect(1, size=len(data) if declared else None)
    written = bytearray()
    outstanding = 0
    largest_burst = 0
    completion_sent = False
    complete = False
    for _ in range(len(data) // VIEW_CHUNK_BODY_BYTES + 8):
        grant = VIEW_TRANSFER_CREDIT_MAX_CHUNKS - outstanding
        if grant:
            write_view_transfer_document(credit_writer, receiver.grant(1, grant), deadline=_deadline())
            outstanding += grant
            granted = credit_reader.read(deadline=_deadline())
            assert isinstance(granted, ViewTransferCredit)
            sender.grant(granted.chunks)
        burst = 0
        while (payload := sender.next_payload()) is not None:
            write_view_transfer_chunk(writer, payload, deadline=_deadline())
            burst += 1
        largest_burst = max(largest_burst, burst)
        if sender.done and not completion_sent:
            write_view_transfer_document(writer, sender.completion(), deadline=_deadline())
            completion_sent = True
        while reader_channel.read_ready():
            item = reader.read(deadline=_deadline())
            if isinstance(item, ViewTransferChunk):
                written.extend(item.data)
                outstanding -= 1
            elif isinstance(item, ViewTransferComplete):
                complete = True
        if complete:
            break
    assert complete
    return bytes(written), largest_burst


@pytest.mark.parametrize(
    "size",
    [
        0,
        1,
        VIEW_CHUNK_BODY_BYTES - 1,
        VIEW_CHUNK_BODY_BYTES,
        VIEW_CHUNK_BODY_BYTES + 1,
        VIEW_TRANSFER_CREDIT_MAX_CHUNKS * VIEW_CHUNK_BODY_BYTES,
        VIEW_TRANSFER_CREDIT_MAX_CHUNKS * VIEW_CHUNK_BODY_BYTES + 1,
        2 * VIEW_IMAGE_MAX_BYTES + 3,
    ],
)
@pytest.mark.parametrize("declared", [False, True])
def test_a_transfer_of_any_size_round_trips_under_credit_without_loss(size: int, declared: bool) -> None:
    data = os.urandom(size)
    written, largest_burst = _run_transfer(data, declared=declared)
    assert written == data
    assert largest_burst <= VIEW_TRANSFER_CREDIT_MAX_CHUNKS


def test_a_sender_yields_nothing_and_reads_nothing_without_credit() -> None:
    source = _Source(b"abc")
    sender = ViewTransferSender(1, source)
    assert sender.next_payload() is None
    assert source.reads == 0
    sender.grant(1)
    payload = sender.next_payload()
    assert payload is not None
    header = ViewTransferChunkHeader.decode(payload)
    assert (header.transfer_id, header.offset, header.last, header.body_length) == (1, 0, True, 3)
    assert sender.next_payload() is None
    assert sender.done


def test_a_sender_cuts_chunks_of_exactly_the_chunk_size_and_digests_every_byte() -> None:
    data = os.urandom(2 * VIEW_CHUNK_BODY_BYTES + 5)
    sender = ViewTransferSender(7, _Source(data, piece=1000))
    sender.grant(3)
    payloads = [sender.next_payload() for _ in range(3)]
    assert all(payload is not None for payload in payloads)
    lengths = [len(payload) - VIEW_CHUNK_HEADER_BYTES for payload in payloads if payload is not None]
    assert lengths == [VIEW_CHUNK_BODY_BYTES, VIEW_CHUNK_BODY_BYTES, 5]
    headers = [ViewTransferChunkHeader.decode(payload) for payload in payloads if payload is not None]
    assert [header.offset for header in headers] == [0, VIEW_CHUNK_BODY_BYTES, 2 * VIEW_CHUNK_BODY_BYTES]
    assert [header.last for header in headers] == [False, False, True]
    completion = sender.completion()
    assert (completion.transfer_id, completion.size) == (7, len(data))
    assert completion.sha256 == hashlib.sha256(data).hexdigest()


def test_a_file_that_ends_on_a_chunk_boundary_flags_its_full_final_chunk_last() -> None:
    sender = ViewTransferSender(1, io.BytesIO(bytes(VIEW_CHUNK_BODY_BYTES)))
    sender.grant(2)
    payload = sender.next_payload()
    assert payload is not None
    header = ViewTransferChunkHeader.decode(payload)
    assert header.last
    assert header.body_length == VIEW_CHUNK_BODY_BYTES
    assert sender.next_payload() is None


def test_a_sender_refuses_credit_beyond_the_window_and_completion_before_its_end() -> None:
    sender = ViewTransferSender(1, io.BytesIO(bytes(3 * VIEW_CHUNK_BODY_BYTES)))
    for chunks in (0, VIEW_TRANSFER_CREDIT_MAX_CHUNKS + 1):
        with pytest.raises(RefusalError):
            sender.grant(chunks)
    sender.grant(VIEW_TRANSFER_CREDIT_MAX_CHUNKS)
    with pytest.raises(RefusalError):
        sender.grant(1)
    assert sender.next_payload() is not None
    with pytest.raises(RefusalError):
        sender.completion()


def test_a_cancelled_sender_sends_nothing_more() -> None:
    sender = ViewTransferSender(1, io.BytesIO(bytes(3 * VIEW_CHUNK_BODY_BYTES)))
    sender.grant(2)
    assert sender.next_payload() is not None
    sender.cancel()
    assert sender.credit == 0
    assert sender.next_payload() is None
    sender.cancel()


def test_a_source_that_returns_more_than_asked_is_refused() -> None:
    sender = ViewTransferSender(1, _Source(b"", overrun=True))
    sender.grant(1)
    with pytest.raises(RefusalError) as refused:
        sender.next_payload()
    assert refused.value.check == "view_transfer_source"


def test_a_receiver_takes_only_increasing_ids_and_the_credit_it_may_grant() -> None:
    receiver = ViewTransferReceiver(ViewTransferDirection.DOWNLOAD)
    receiver.expect(2)
    for transfer_id in (0, 1, 2):
        with pytest.raises(RefusalError):
            receiver.expect(transfer_id)
    with pytest.raises(RefusalError):
        receiver.grant(9, 1)
    for chunks in (0, VIEW_TRANSFER_CREDIT_MAX_CHUNKS + 1):
        with pytest.raises(RefusalError):
            receiver.grant(2, chunks)
    assert receiver.grant(2, VIEW_TRANSFER_CREDIT_MAX_CHUNKS) == ViewTransferCredit(
        transfer_id=2, chunks=VIEW_TRANSFER_CREDIT_MAX_CHUNKS
    )
    with pytest.raises(RefusalError):
        receiver.grant(2, 1)


def test_a_receiver_cancels_once_and_a_finished_transfer_needs_no_cancel() -> None:
    receiver = ViewTransferReceiver(ViewTransferDirection.UPLOAD)
    assert receiver.cancel(1) is None
    receiver.expect(1)
    assert receiver.cancel(1) == ViewTransferCancel(direction=ViewTransferDirection.UPLOAD, transfer_id=1)
    assert receiver.cancel(1) is None
    with pytest.raises(RefusalError):
        receiver.grant(1, 1)


def test_a_refused_receiver_stays_refused() -> None:
    receiver = ViewTransferReceiver(ViewTransferDirection.DOWNLOAD)
    receiver.expect(1)
    receiver.grant(1, 2)
    with pytest.raises(RefusalError):
        receiver.accept(b"short")
    for use in (
        lambda: receiver.expect(2),
        lambda: receiver.grant(1, 1),
        lambda: receiver.accept(_transfer_chunk_frame()[5:]),
    ):
        with pytest.raises(RefusalError) as refused:
            use()
        assert refused.value.check == "view_stream_refused"


def test_a_peer_without_a_receiver_refuses_transfer_frames() -> None:
    writer, reader_channel = _pair()
    writer.write_all(_transfer_chunk_frame(), deadline=_deadline())
    with pytest.raises(RefusalError) as refused:
        ViewDownstreamReader(reader_channel).read(deadline=_deadline())
    assert refused.value.reason is RefusalCode.INVALID_FRAME
    assert _closed(writer)

    writer, reader_channel = _pair()
    write_view_transfer_document(writer, ViewTransferCredit(transfer_id=1, chunks=1), deadline=_deadline())
    with pytest.raises(RefusalError) as refused:
        ViewDownstreamReader(reader_channel).read(deadline=_deadline())
    assert refused.value.reason is RefusalCode.INVALID_FRAME
    assert _closed(writer)


def test_an_upload_travels_upstream_and_an_image_chunk_never_does() -> None:
    writer, reader_channel = _pair()
    receiver = ViewTransferReceiver(ViewTransferDirection.UPLOAD)
    reader = ViewUpstreamReader(reader_channel, receiver)
    data = os.urandom(VIEW_CHUNK_BODY_BYTES + 9)
    sender = ViewTransferSender(1, io.BytesIO(data))
    receiver.expect(1, size=len(data))
    sender.grant(receiver.grant(1, 2).chunks)
    received = bytearray()
    while (payload := sender.next_payload()) is not None:
        write_view_transfer_chunk(writer, payload, deadline=_deadline())
        item = reader.read(deadline=_deadline())
        assert isinstance(item, ViewTransferChunk)
        received.extend(item.data)
    write_view_transfer_document(writer, sender.completion(), deadline=_deadline())
    assert isinstance(reader.read(deadline=_deadline()), ViewTransferComplete)
    assert bytes(received) == data
    writer.write_all(_chunk_frame(), deadline=_deadline())
    with pytest.raises(RefusalError):
        reader.read(deadline=_deadline())
    assert _closed(writer)


def test_the_writers_refuse_an_invalid_transfer_chunk_before_any_byte() -> None:
    writer, _ = _pair()
    misaligned = next(case for case in _VECTORS["transfer_header_refusals"] if case["name"] == "offset_one_byte")
    for payload in (_chunk_frame()[5:], b"short", bytes.fromhex(misaligned["header"]) + b"x"):
        with pytest.raises(RefusalError):
            write_view_transfer_chunk(writer, payload, deadline=_deadline())
    assert writer.writes == []


def test_a_cancel_crossing_chunks_in_flight_discards_them_and_ends_with_the_senders_cancel() -> None:
    writer, reader_channel, receiver, reader = _receiving_end()
    data = os.urandom(4 * VIEW_CHUNK_BODY_BYTES)
    sender = ViewTransferSender(1, io.BytesIO(data))
    receiver.expect(1)
    sender.grant(receiver.grant(1, 4).chunks)
    write_view_transfer_chunk(writer, sender.next_payload() or b"", deadline=_deadline())
    first = reader.read(deadline=_deadline())
    assert isinstance(first, ViewTransferChunk)
    cancel = receiver.cancel(1)
    assert cancel is not None
    # The sender had not yet seen the cancel, so two more chunks cross it.
    for _ in range(2):
        write_view_transfer_chunk(writer, sender.next_payload() or b"", deadline=_deadline())
    sender.cancel()
    write_view_transfer_document(writer, cancel, deadline=_deadline())
    echoed = reader.read(deadline=_deadline())
    assert echoed == cancel
    assert not reader_channel.read_ready()
    # The id is spent and the stream is still usable for the next transfer.
    receiver.expect(2)
    follow_up = ViewTransferSender(2, io.BytesIO(b"next"))
    follow_up.grant(receiver.grant(2, 1).chunks)
    write_view_transfer_chunk(writer, follow_up.next_payload() or b"", deadline=_deadline())
    write_view_transfer_document(writer, follow_up.completion(), deadline=_deadline())
    chunk = reader.read(deadline=_deadline())
    assert isinstance(chunk, ViewTransferChunk)
    assert chunk.data == b"next"
    assert isinstance(reader.read(deadline=_deadline()), ViewTransferComplete)


def test_a_stalled_transfer_never_holds_back_images_and_resumes_when_credit_arrives() -> None:
    writer, reader_channel, receiver, reader = _receiving_end()
    data = os.urandom(3 * VIEW_CHUNK_BODY_BYTES + 11)
    sender = ViewTransferSender(1, io.BytesIO(data))
    receiver.expect(1)
    sender.grant(receiver.grant(1, 2).chunks)
    outbox = ViewImageOutbox()
    outbox.grant(2)
    lanes: list[str] = []

    def turn(sequence: int) -> None:
        """One writer turn: the pending image if the window has credit, then one chunk if the transfer has."""
        outbox.offer(_announcement(sequence), b"i")
        pending = outbox.take()
        if pending is not None:
            write_view_image(writer, pending[0], pending[1], deadline=_deadline())
            outbox.grant(1)
            lanes.append("image")
        payload = sender.next_payload()
        if payload is not None:
            write_view_transfer_chunk(writer, payload, deadline=_deadline())
            lanes.append("chunk")

    for sequence in (1, 2, 3):
        turn(sequence)
    # Two chunks of credit are spent: the transfer is stalled, the images are not.
    assert lanes == ["image", "chunk", "image", "chunk", "image"]
    assert sender.credit == 0
    sender.grant(receiver.grant(1, 2).chunks)
    for sequence in (4, 5):
        turn(sequence)
    assert lanes[5:] == ["image", "chunk", "image", "chunk"]
    write_view_transfer_document(writer, sender.completion(), deadline=_deadline())

    images: list[int] = []
    written = bytearray()
    complete = False
    while not complete:
        item = reader.read(deadline=_deadline())
        if isinstance(item, AssembledViewImage):
            images.append(item.announcement.sequence)
        elif isinstance(item, ViewTransferChunk):
            written.extend(item.data)
        else:
            complete = isinstance(item, ViewTransferComplete)
    assert images == [1, 2, 3, 4, 5]
    assert bytes(written) == data
    assert not reader_channel.read_ready()
