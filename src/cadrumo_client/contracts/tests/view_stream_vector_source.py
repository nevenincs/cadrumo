"""Author the shared view stream conformance vectors and write them beside this module.

The vectors are written out here independently of any codec: header bytes are
composed field by field, and documents are plain JSON. The Python codec, the
Rust view stream client and the window read the same file, so a case here is a
case each implementation must agree on.

Regenerate with ``uv run --no-sync python -m cadrumo_client.contracts.tests.view_stream_vector_source``;
pass ``--check`` to fail when the file differs from fresh output.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

VECTORS_PATH = Path(__file__).with_name("view_stream_vectors.json")

_FRAME_MAX = 64 * 1024
_HEADER = 16
_BODY = _FRAME_MAX - _HEADER
_IMAGE_MAX = 2 * 1024 * 1024
_PATTERN_MODULUS = 251
_TRANSFER_FLAG = 2
_TRANSFER_ID_MAX = 2**32 - 1
_TRANSFER_SIZE_MAX = 2**64 - 1
_TRANSFER_CREDIT_WINDOW = 32

_ABOUT = (
    "Conformance vectors for the Sede view stream. A B frame payload is a 16-byte network-order header "
    "(u8 version 1, u8 flags with bit 0 the last chunk and no other bit, u16 reserved zero, u32 image sequence, "
    "u16 chunk index, u16 chunk count = ceil(image length / 65520), u32 image length 1..2097152) and a body of "
    "exactly 65520 bytes for every chunk but the last. headers: accepted headers with their fields and the body "
    "length each must carry. header_refusals: headers refused with the given body length; check is the Python "
    "diagnostic name. streams: frames read in order on a downstream view connection; announce is a view.image "
    "J document, document any other J document, chunk a B payload whose body is the image bytes from offset for "
    "length, where image byte k is k mod 251. expect lists what the reader returns in order, or refused_at names "
    "the step that refuses and closes the connection. documents: control documents each direction must accept "
    "or refuse, in their closed sets. Flag bit 1 (transfer_flag) marks a chunk of a download or upload instead of "
    "an image; its 16-byte header is u8 version 1, u8 flags (bit 0 the last chunk, bit 1 set, no other bit), u16 "
    "reserved zero, u32 transfer id from 1, u64 byte offset of the body's first byte. Every chunk but the last "
    "carries exactly 65520 body bytes and offsets are multiples of 65520; the last carries 0 to 65520 bytes, none "
    "only at offset 0. No total transfer size is bounded beyond the 64-bit offset. transfer_headers and "
    "transfer_header_refusals are the transfer analogues of headers and header_refusals, and an image header that "
    "sets flag bit 1 is refused. transfer_streams: direction names the reader, downstream for the window (which "
    "receives downloads) and upstream for the worker side (which receives uploads). setup lists the receiver calls "
    "made before any frame is read: expect a transfer with an optional exact size, grant credit in chunks, cancel "
    "locally. steps, expect and refused_at read as in streams; an expected chunk names its transfer id, offset, "
    "length, last flag and the sha256 of its body, and transfer byte k is k mod 251. A transfer chunk is refused "
    "when its transfer was not expected, arrives out of order, interleaves with another transfer or inside an "
    "image, or exceeds the credit granted; a completion is refused when it precedes the last chunk or disagrees "
    "with the bytes received in size or sha256, or with the declared size."
)


def _header(
    sequence: int, index: int, count: int, length: int, *, flags: int | None = None, version: int = 1, reserved: int = 0
) -> str:
    if flags is None:
        flags = 1 if index == count - 1 else 0
    raw = (
        version.to_bytes(1, "big")
        + flags.to_bytes(1, "big")
        + reserved.to_bytes(2, "big")
        + sequence.to_bytes(4, "big")
        + index.to_bytes(2, "big")
        + count.to_bytes(2, "big")
        + length.to_bytes(4, "big")
    )
    return raw.hex()


def _pattern(length: int) -> bytes:
    return bytes(offset % _PATTERN_MODULUS for offset in range(length))


def _chunk_count(length: int) -> int:
    return -(-length // _BODY)


def _image_document(sequence: int, length: int) -> dict[str, Any]:
    return {
        "kind": "view.image",
        "sequence": sequence,
        "byte_length": length,
        "pixel_width": 1600,
        "pixel_height": 1000,
        "css_width": 1280,
        "css_height": 800,
        "scale": 1.25,
    }


def _announce(sequence: int, length: int) -> dict[str, Any]:
    return {"announce": _image_document(sequence, length)}


def _chunk(
    sequence: int, index: int, length: int, *, header: str | None = None, body: int | None = None
) -> dict[str, Any]:
    count = _chunk_count(length)
    offset = index * _BODY
    default_body = min(_BODY, length - offset)
    return {
        "chunk": {
            "header": header if header is not None else _header(sequence, index, count, length),
            "body_offset": offset,
            "body_length": default_body if body is None else body,
        }
    }


def _image_chunks(sequence: int, length: int) -> list[dict[str, Any]]:
    return [_chunk(sequence, index, length) for index in range(_chunk_count(length))]


def _expected_image(sequence: int, length: int) -> dict[str, Any]:
    return {
        "image": {"sequence": sequence, "byte_length": length, "sha256": hashlib.sha256(_pattern(length)).hexdigest()}
    }


_STATE: dict[str, Any] = {
    "kind": "view.state",
    "origin": "https://sede.agenciatributaria.gob.es",
    "path": "/Sede/inicio.html",
    "title": "Sede electrónica",
    "can_go_back": False,
    "can_go_forward": False,
    "loading": False,
    "phase": "browsing",
}


def _headers() -> list[dict[str, Any]]:
    cases = [
        ("one_byte_image", 0, 0, 1),
        ("one_full_chunk", 1, 0, _BODY),
        ("first_of_two", 7, 0, _BODY + 1),
        ("last_of_two", 7, 1, _BODY + 1),
        ("largest_image_first", 0xFFFFFFFF, 0, _IMAGE_MAX),
        ("largest_image_last", 0xFFFFFFFF, _chunk_count(_IMAGE_MAX) - 1, _IMAGE_MAX),
    ]
    vectors = []
    for name, sequence, index, length in cases:
        count = _chunk_count(length)
        last = index == count - 1
        vectors.append(
            {
                "name": name,
                "header": _header(sequence, index, count, length),
                "sequence": sequence,
                "chunk_index": index,
                "chunk_count": count,
                "image_length": length,
                "last": last,
                "body_length": length - _BODY * (count - 1) if last else _BODY,
            }
        )
    return vectors


def _header_refusals() -> list[dict[str, Any]]:
    two = _BODY + 1
    return [
        {
            "name": "short_header",
            "header": _header(0, 0, 1, 1)[:30],
            "body_length": 0,
            "check": "view_chunk_header_length",
        },
        {
            "name": "version_two",
            "header": _header(0, 0, 1, 1, version=2),
            "body_length": 1,
            "check": "view_chunk_version",
        },
        {
            "name": "unknown_flag_bit",
            "header": _header(0, 0, 1, 1, flags=3),
            "body_length": 1,
            "check": "view_chunk_reserved",
        },
        {
            "name": "reserved_nonzero",
            "header": _header(0, 0, 1, 1, reserved=1),
            "body_length": 1,
            "check": "view_chunk_reserved",
        },
        {
            "name": "transfer_flag_on_image_header",
            "header": _header(0, 0, 1, 1, flags=_TRANSFER_FLAG),
            "body_length": 1,
            "check": "view_chunk_reserved",
        },
        {
            "name": "last_flag_missing",
            "header": _header(0, 0, 1, 1, flags=0),
            "body_length": 1,
            "check": "view_chunk_last_flag",
        },
        {
            "name": "last_flag_early",
            "header": _header(0, 0, 2, two, flags=1),
            "body_length": _BODY,
            "check": "view_chunk_last_flag",
        },
        {"name": "index_beyond_count", "header": _header(0, 2, 2, two), "body_length": 1, "check": "view_chunk_index"},
        {"name": "count_mismatch", "header": _header(0, 0, 1, two), "body_length": _BODY, "check": "view_chunk_count"},
        {"name": "zero_length", "header": _header(0, 0, 0, 0), "body_length": 0, "check": "view_image_length"},
        {
            "name": "oversize_image",
            "header": _header(0, 0, _chunk_count(_IMAGE_MAX + 1), _IMAGE_MAX + 1),
            "body_length": _BODY,
            "check": "view_image_length",
        },
        {
            "name": "body_short",
            "header": _header(0, 0, 2, two),
            "body_length": _BODY - 1,
            "check": "view_chunk_body_length",
        },
        {"name": "body_long", "header": _header(0, 0, 1, 1), "body_length": 2, "check": "view_chunk_body_length"},
    ]


def _streams() -> list[dict[str, Any]]:
    two = _BODY + 1
    return [
        {
            "name": "one_byte_image",
            "steps": [_announce(1, 1), *_image_chunks(1, 1)],
            "expect": [_expected_image(1, 1)],
        },
        {
            "name": "one_full_chunk",
            "steps": [_announce(1, _BODY), *_image_chunks(1, _BODY)],
            "expect": [_expected_image(1, _BODY)],
        },
        {
            "name": "two_chunks",
            "steps": [_announce(3, two), *_image_chunks(3, two)],
            "expect": [_expected_image(3, two)],
        },
        {
            "name": "largest_image",
            "steps": [_announce(4, _IMAGE_MAX), *_image_chunks(4, _IMAGE_MAX)],
            "expect": [_expected_image(4, _IMAGE_MAX)],
        },
        {
            "name": "latest_wins_skips_sequences",
            "steps": [
                _announce(1, 10),
                *_image_chunks(1, 10),
                {"document": _STATE},
                _announce(9, 20),
                *_image_chunks(9, 20),
            ],
            "expect": [_expected_image(1, 10), {"document": "view.state"}, _expected_image(9, 20)],
        },
        {"name": "chunk_without_announcement", "steps": _image_chunks(1, 10), "refused_at": 0},
        {
            "name": "out_of_order_chunk",
            "steps": [_announce(1, two), _chunk(1, 1, two), _chunk(1, 0, two)],
            "refused_at": 1,
        },
        {
            "name": "repeated_chunk",
            "steps": [_announce(1, two), _chunk(1, 0, two), _chunk(1, 0, two)],
            "refused_at": 2,
        },
        {
            "name": "interleaved_announcement",
            "steps": [_announce(1, two), _chunk(1, 0, two), _announce(2, 10)],
            "refused_at": 2,
        },
        {
            "name": "interleaved_chunk",
            "steps": [_announce(1, two), _chunk(1, 0, two), _chunk(2, 1, two)],
            "refused_at": 2,
        },
        {
            "name": "document_inside_image",
            "steps": [_announce(1, two), _chunk(1, 0, two), {"document": _STATE}],
            "refused_at": 2,
        },
        {"name": "oversize_announcement", "steps": [_announce(1, _IMAGE_MAX + 1)], "refused_at": 0},
        {
            "name": "oversize_chunk_header",
            "steps": [
                _announce(1, _IMAGE_MAX),
                _chunk(1, 0, _IMAGE_MAX, header=_header(1, 0, _chunk_count(_IMAGE_MAX + 1), _IMAGE_MAX + 1)),
            ],
            "refused_at": 1,
        },
        {
            "name": "length_differs_from_announcement",
            "steps": [_announce(1, 10), _chunk(1, 0, 10, header=_header(1, 0, 1, 11), body=11)],
            "refused_at": 1,
        },
        {
            "name": "sequence_not_increasing",
            "steps": [_announce(5, 10), *_image_chunks(5, 10), _announce(5, 10)],
            "refused_at": 2,
        },
    ]


def _transfer_header(
    transfer_id: int, offset: int, *, last: bool, flags: int | None = None, version: int = 1, reserved: int = 0
) -> str:
    if flags is None:
        flags = _TRANSFER_FLAG | (1 if last else 0)
    raw = (
        version.to_bytes(1, "big")
        + flags.to_bytes(1, "big")
        + reserved.to_bytes(2, "big")
        + transfer_id.to_bytes(4, "big")
        + offset.to_bytes(8, "big")
    )
    return raw.hex()


def _transfer_chunk_count(size: int) -> int:
    return max(1, -(-size // _BODY))


def _transfer_chunk(
    transfer_id: int, size: int, index: int, *, header: str | None = None, body: int | None = None
) -> dict[str, Any]:
    offset = index * _BODY
    last = index == _transfer_chunk_count(size) - 1
    default_body = min(_BODY, size - offset)
    return {
        "chunk": {
            "header": header if header is not None else _transfer_header(transfer_id, offset, last=last),
            "body_offset": offset,
            "body_length": default_body if body is None else body,
        }
    }


def _transfer_chunks(transfer_id: int, size: int) -> list[dict[str, Any]]:
    return [_transfer_chunk(transfer_id, size, index) for index in range(_transfer_chunk_count(size))]


def _complete(
    transfer_id: int, size: int, *, sha256: str | None = None, reported_size: int | None = None
) -> dict[str, Any]:
    return {
        "document": {
            "kind": "view.transfer_complete",
            "transfer_id": transfer_id,
            "size": size if reported_size is None else reported_size,
            "sha256": sha256 if sha256 is not None else hashlib.sha256(_pattern(size)).hexdigest(),
        }
    }


def _cancel(direction: str, transfer_id: int) -> dict[str, Any]:
    return {"document": {"kind": "view.transfer_cancel", "direction": direction, "transfer_id": transfer_id}}


def _expect(transfer_id: int, size: int | None = None) -> dict[str, Any]:
    return {"expect": {"transfer_id": transfer_id, "size": size}}


def _grant(transfer_id: int, chunks: int) -> dict[str, Any]:
    return {"grant": {"transfer_id": transfer_id, "chunks": chunks}}


def _expected_chunk(transfer_id: int, size: int, index: int) -> dict[str, Any]:
    offset = index * _BODY
    length = min(_BODY, size - offset)
    return {
        "chunk": {
            "transfer_id": transfer_id,
            "offset": offset,
            "length": length,
            "last": index == _transfer_chunk_count(size) - 1,
            "sha256": hashlib.sha256(_pattern(offset + length)[offset:]).hexdigest(),
        }
    }


def _expected_chunks(transfer_id: int, size: int) -> list[dict[str, Any]]:
    return [_expected_chunk(transfer_id, size, index) for index in range(_transfer_chunk_count(size))]


def _expected_document(kind: str) -> dict[str, Any]:
    return {"document": kind}


_COMPLETE = _expected_document("view.transfer_complete")


def _transfer_headers() -> list[dict[str, Any]]:
    far_offset = (2**40 // _BODY) * _BODY
    largest_offset = (_TRANSFER_SIZE_MAX // _BODY) * _BODY
    cases = [
        ("empty_file", 1, 0, True, 0),
        ("one_byte", 1, 0, True, 1),
        ("full_chunk_not_last", 1, 0, False, _BODY),
        ("full_chunk_last", 1, 0, True, _BODY),
        ("second_chunk_last", 2, _BODY, True, 10),
        ("largest_transfer_id", _TRANSFER_ID_MAX, 0, True, 5),
        ("offset_beyond_32_bits", 3, far_offset, False, _BODY),
        ("largest_offset", 3, largest_offset, True, 7),
    ]
    return [
        {
            "name": name,
            "header": _transfer_header(transfer_id, offset, last=last),
            "transfer_id": transfer_id,
            "offset": offset,
            "last": last,
            "body_length": body,
        }
        for name, transfer_id, offset, last, body in cases
    ]


def _transfer_header_refusals() -> list[dict[str, Any]]:
    return [
        {
            "name": "short_header",
            "header": _transfer_header(1, 0, last=True)[:30],
            "body_length": 0,
            "check": "view_chunk_header_length",
        },
        {
            "name": "version_two",
            "header": _transfer_header(1, 0, last=True, version=2),
            "body_length": 1,
            "check": "view_chunk_version",
        },
        {
            "name": "unknown_flag_bit",
            "header": _transfer_header(1, 0, last=True, flags=_TRANSFER_FLAG | 4),
            "body_length": 1,
            "check": "view_chunk_reserved",
        },
        {
            "name": "reserved_nonzero",
            "header": _transfer_header(1, 0, last=True, reserved=1),
            "body_length": 1,
            "check": "view_chunk_reserved",
        },
        {
            "name": "transfer_flag_clear",
            "header": _transfer_header(1, 0, last=True, flags=1),
            "body_length": 1,
            "check": "view_transfer_flag",
        },
        {
            "name": "transfer_id_zero",
            "header": _transfer_header(0, 0, last=True),
            "body_length": 1,
            "check": "view_transfer_id",
        },
        {
            "name": "offset_one_byte",
            "header": _transfer_header(1, 1, last=True),
            "body_length": 1,
            "check": "view_transfer_offset",
        },
        {
            "name": "offset_one_short_of_a_chunk",
            "header": _transfer_header(1, _BODY - 1, last=True),
            "body_length": 1,
            "check": "view_transfer_offset",
        },
        {
            "name": "offset_misaligned_beyond_32_bits",
            "header": _transfer_header(1, 2**40 + 1, last=True),
            "body_length": 1,
            "check": "view_transfer_offset",
        },
        {
            "name": "not_last_body_short",
            "header": _transfer_header(1, 0, last=False),
            "body_length": _BODY - 1,
            "check": "view_transfer_body_length",
        },
        {
            "name": "not_last_body_empty",
            "header": _transfer_header(1, 0, last=False),
            "body_length": 0,
            "check": "view_transfer_body_length",
        },
        {
            "name": "last_body_too_long",
            "header": _transfer_header(1, 0, last=True),
            "body_length": _BODY + 1,
            "check": "view_transfer_body_length",
        },
        {
            "name": "empty_last_chunk_after_data",
            "header": _transfer_header(1, _BODY, last=True),
            "body_length": 0,
            "check": "view_transfer_body_length",
        },
    ]


def _transfer_streams() -> list[dict[str, Any]]:
    two = 2 * _BODY
    three = 2 * _BODY + 1
    flipped = hashlib.sha256(_pattern(5)[:-1] + b"\xff").hexdigest()
    image_after_chunk = [_announce(1, two), _chunk(1, 0, two)]

    def accepted(
        name: str, setup: list[dict[str, Any]], steps: list[dict[str, Any]], expect: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {"name": name, "direction": "downstream", "setup": setup, "steps": steps, "expect": expect}

    def refused(
        name: str,
        setup: list[dict[str, Any]],
        steps: list[dict[str, Any]],
        refused_at: int,
        direction: str = "downstream",
    ) -> dict[str, Any]:
        return {"name": name, "direction": direction, "setup": setup, "steps": steps, "refused_at": refused_at}

    return [
        accepted(
            "empty_file",
            [_expect(1, 0), _grant(1, 1)],
            [*_transfer_chunks(1, 0), _complete(1, 0)],
            [*_expected_chunks(1, 0), _COMPLETE],
        ),
        accepted(
            "one_byte_file",
            [_expect(1), _grant(1, 1)],
            [*_transfer_chunks(1, 1), _complete(1, 1)],
            [*_expected_chunks(1, 1), _COMPLETE],
        ),
        accepted(
            "full_chunk_file",
            [_expect(1), _grant(1, 1)],
            [*_transfer_chunks(1, _BODY), _complete(1, _BODY)],
            [*_expected_chunks(1, _BODY), _COMPLETE],
        ),
        accepted(
            "two_full_chunks",
            [_expect(1), _grant(1, 2)],
            [*_transfer_chunks(1, two), _complete(1, two)],
            [*_expected_chunks(1, two), _COMPLETE],
        ),
        accepted(
            "three_chunks_with_declared_size",
            [_expect(1, three), _grant(1, 3)],
            [*_transfer_chunks(1, three), _complete(1, three)],
            [*_expected_chunks(1, three), _COMPLETE],
        ),
        accepted(
            "full_credit_window",
            [_expect(1), _grant(1, 32)],
            [*_transfer_chunks(1, 32 * _BODY), _complete(1, 32 * _BODY)],
            [*_expected_chunks(1, 32 * _BODY), _COMPLETE],
        ),
        accepted(
            "ids_increase_and_may_skip",
            [_expect(1), _expect(3), _grant(1, 1), _grant(3, 1)],
            [*_transfer_chunks(1, 5), _complete(1, 5), *_transfer_chunks(3, 6), _complete(3, 6)],
            [*_expected_chunks(1, 5), _COMPLETE, *_expected_chunks(3, 6), _COMPLETE],
        ),
        accepted(
            "images_and_documents_between_chunks",
            [_expect(1), _grant(1, 3)],
            [
                _transfer_chunk(1, three, 0),
                _announce(1, 10),
                *_image_chunks(1, 10),
                _transfer_chunk(1, three, 1),
                {"document": _STATE},
                _transfer_chunk(1, three, 2),
                _complete(1, three),
            ],
            [
                _expected_chunk(1, three, 0),
                _expected_image(1, 10),
                _expected_chunk(1, three, 1),
                _expected_document("view.state"),
                _expected_chunk(1, three, 2),
                _COMPLETE,
            ],
        ),
        accepted(
            "local_cancel_discards_crossing_chunks",
            [_expect(1), _grant(1, 2), {"cancel": {"transfer_id": 1}}],
            [
                _transfer_chunk(1, three, 0),
                _transfer_chunk(1, three, 1),
                _cancel("download", 1),
            ],
            [_expected_document("view.transfer_cancel")],
        ),
        accepted(
            "sender_cancel_ends_the_stream",
            [_expect(1), _expect(2), _grant(1, 1), _grant(2, 1)],
            [
                _transfer_chunk(1, three, 0),
                _cancel("download", 1),
                *_transfer_chunks(2, 5),
                _complete(2, 5),
            ],
            [
                _expected_chunk(1, three, 0),
                _expected_document("view.transfer_cancel"),
                *_expected_chunks(2, 5),
                _COMPLETE,
            ],
        ),
        accepted(
            "cancel_of_the_other_direction_passes_through",
            [],
            [_cancel("upload", 7)],
            [_expected_document("view.transfer_cancel")],
        ),
        accepted(
            "transfer_documents_pass_through",
            [],
            [
                {"document": {"kind": "view.download", "transfer_id": 1, "filename": "a.pdf"}},
                {"document": {"kind": "view.file_chooser", "chooser_id": 1, "accept": [], "multiple": False}},
                {"document": {"kind": "view.transfer_credit", "transfer_id": 1, "chunks": 32}},
            ],
            [
                _expected_document("view.download"),
                _expected_document("view.file_chooser"),
                _expected_document("view.transfer_credit"),
            ],
        ),
        refused("chunk_for_unknown_transfer", [], _transfer_chunks(1, 5), 0),
        refused("chunk_without_credit", [_expect(1)], _transfer_chunks(1, 5), 0),
        refused("chunk_beyond_credit", [_expect(1), _grant(1, 1)], _transfer_chunks(1, two), 1),
        refused(
            "out_of_order_chunk",
            [_expect(1), _grant(1, 2)],
            [_transfer_chunk(1, two, 1), _transfer_chunk(1, two, 0)],
            0,
        ),
        refused(
            "repeated_chunk", [_expect(1), _grant(1, 2)], [_transfer_chunk(1, two, 0), _transfer_chunk(1, two, 0)], 1
        ),
        refused(
            "skipped_chunk", [_expect(1), _grant(1, 2)], [_transfer_chunk(1, three, 0), _transfer_chunk(1, three, 2)], 1
        ),
        refused(
            "chunk_after_last", [_expect(1), _grant(1, 2)], [_transfer_chunk(1, 5, 0), _transfer_chunk(1, 5, 0)], 1
        ),
        refused(
            "interleaved_transfers",
            [_expect(1), _expect(2), _grant(1, 2), _grant(2, 2)],
            [_transfer_chunk(1, two, 0), _transfer_chunk(2, 5, 0)],
            1,
        ),
        refused(
            "transfer_chunk_inside_an_image",
            [_expect(1), _grant(1, 1)],
            [*image_after_chunk, _transfer_chunk(1, 5, 0)],
            2,
        ),
        refused(
            "misaligned_offset",
            [_expect(1), _grant(1, 1)],
            [_transfer_chunk(1, 5, 0, header=_transfer_header(1, 1, last=True))],
            0,
        ),
        refused(
            "short_chunk_that_is_not_last",
            [_expect(1), _grant(1, 1)],
            [_transfer_chunk(1, 10, 0, header=_transfer_header(1, 0, last=False))],
            0,
        ),
        refused(
            "complete_before_the_last_chunk",
            [_expect(1), _grant(1, 1)],
            [_transfer_chunk(1, two, 0), _complete(1, two)],
            1,
        ),
        refused("complete_for_unknown_transfer", [], [_complete(9, 5)], 0),
        refused(
            "complete_twice",
            [_expect(1), _grant(1, 1)],
            [*_transfer_chunks(1, 5), _complete(1, 5), _complete(1, 5)],
            2,
        ),
        refused(
            "complete_size_differs",
            [_expect(1), _grant(1, 1)],
            [*_transfer_chunks(1, 5), _complete(1, 5, reported_size=6)],
            1,
        ),
        refused(
            "complete_digest_differs",
            [_expect(1), _grant(1, 1)],
            [*_transfer_chunks(1, 5), _complete(1, 5, sha256=flipped)],
            1,
        ),
        refused("declared_size_exceeded", [_expect(1, 4), _grant(1, 1)], _transfer_chunks(1, 5), 0),
        refused(
            "declared_size_not_reached",
            [_expect(1, 10), _grant(1, 1)],
            [*_transfer_chunks(1, 5), _complete(1, 5)],
            1,
        ),
        refused(
            "image_chunk_upstream",
            [],
            [_chunk(1, 0, 1)],
            0,
            direction="upstream",
        ),
        refused(
            "upload_digest_differs",
            [_expect(1, 5), _grant(1, 1)],
            [*_transfer_chunks(1, 5), _complete(1, 5, sha256=flipped)],
            1,
            direction="upstream",
        ),
        {
            "name": "upload_chunks_and_documents",
            "direction": "upstream",
            "setup": [_expect(1, three), _grant(1, 3)],
            "steps": [
                {
                    "document": {
                        "kind": "view.file_chooser_answer",
                        "chooser_id": 1,
                        "outcome": "supplied",
                        "file_count": 1,
                    }
                },
                {
                    "document": {
                        "kind": "view.upload",
                        "chooser_id": 1,
                        "transfer_id": 1,
                        "name": "a.pdf",
                        "size": three,
                    }
                },
                *_transfer_chunks(1, three),
                _complete(1, three),
            ],
            "expect": [
                _expected_document("view.file_chooser_answer"),
                _expected_document("view.upload"),
                *_expected_chunks(1, three),
                _COMPLETE,
            ],
        },
    ]


_SHA256 = hashlib.sha256(b"transfer").hexdigest()


def _transfer_documents_accepted() -> list[tuple[str, str, dict[str, Any]]]:
    download = {"kind": "view.download", "transfer_id": 1, "filename": "justificante.pdf"}
    chooser = {"kind": "view.file_chooser", "chooser_id": 1, "accept": [], "multiple": False}
    answer = {"kind": "view.file_chooser_answer", "chooser_id": 1, "outcome": "supplied", "file_count": 3}
    upload = {"kind": "view.upload", "chooser_id": 1, "transfer_id": 2, "name": "factura.pdf", "size": 1234}
    complete = {"kind": "view.transfer_complete", "transfer_id": 1, "size": 1234, "sha256": _SHA256}
    credit = {"kind": "view.transfer_credit", "transfer_id": 1, "chunks": 1}
    cancel = {"kind": "view.transfer_cancel", "direction": "download", "transfer_id": 1}
    answer_to_download = {"kind": "view.download_answer", "transfer_id": 1, "outcome": "accepted"}
    return [
        ("download_bare", "downstream", download),
        ("download_with_hints", "downstream", {**download, "size": 123456, "mime": "application/pdf"}),
        ("download_empty_file", "downstream", {**download, "size": 0}),
        (
            "download_beyond_32_bits",
            "downstream",
            {**download, "transfer_id": _TRANSFER_ID_MAX, "size": _TRANSFER_SIZE_MAX, "mime": "text/csv"},
        ),
        ("download_unicode_name", "downstream", {**download, "filename": "Declaración ñ 2025.txt"}),
        ("download_longest_name", "downstream", {**download, "filename": "n" * 255}),
        ("file_chooser_single", "downstream", chooser),
        (
            "file_chooser_multiple",
            "downstream",
            {
                **chooser,
                "accept": [
                    ".pdf",
                    "image/*",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ],
                "multiple": True,
            },
        ),
        ("file_chooser_most_accept_entries", "downstream", {**chooser, "accept": [".pdf"] * 128}),
        ("complete_downstream", "downstream", complete),
        (
            "complete_largest_size",
            "downstream",
            {**complete, "transfer_id": _TRANSFER_ID_MAX, "size": _TRANSFER_SIZE_MAX},
        ),
        ("complete_empty_file", "downstream", {**complete, "size": 0}),
        ("credit_downstream", "downstream", credit),
        ("credit_full_window", "downstream", {**credit, "chunks": _TRANSFER_CREDIT_WINDOW}),
        ("cancel_download_downstream", "downstream", cancel),
        ("cancel_upload_downstream", "downstream", {**cancel, "direction": "upload"}),
        ("download_answer_accepted", "upstream", answer_to_download),
        ("download_answer_refused", "upstream", {**answer_to_download, "outcome": "refused"}),
        ("download_answer_cancelled", "upstream", {**answer_to_download, "outcome": "cancelled"}),
        ("file_chooser_answer_supplied", "upstream", answer),
        ("file_chooser_answer_cancelled", "upstream", {**answer, "outcome": "cancelled", "file_count": 0}),
        ("upload", "upstream", upload),
        ("upload_empty_file_with_media_type", "upstream", {**upload, "size": 0, "mime": "application/vnd.ms-excel"}),
        ("complete_upstream", "upstream", complete),
        ("credit_upstream", "upstream", credit),
        ("cancel_download_upstream", "upstream", cancel),
        ("cancel_upload_upstream", "upstream", {**cancel, "direction": "upload"}),
    ]


def _transfer_documents_refused() -> list[tuple[str, str, dict[str, Any]]]:
    download = {"kind": "view.download", "transfer_id": 1, "filename": "justificante.pdf"}
    chooser = {"kind": "view.file_chooser", "chooser_id": 1, "accept": [], "multiple": False}
    answer = {"kind": "view.file_chooser_answer", "chooser_id": 1, "outcome": "supplied", "file_count": 3}
    upload = {"kind": "view.upload", "chooser_id": 1, "transfer_id": 2, "name": "factura.pdf", "size": 1234}
    complete = {"kind": "view.transfer_complete", "transfer_id": 1, "size": 1234, "sha256": _SHA256}
    credit = {"kind": "view.transfer_credit", "transfer_id": 1, "chunks": 1}
    answer_to_download = {"kind": "view.download_answer", "transfer_id": 1, "outcome": "accepted"}
    return [
        ("download_on_upstream", "upstream", download),
        ("file_chooser_on_upstream", "upstream", chooser),
        ("download_answer_on_downstream", "downstream", answer_to_download),
        ("file_chooser_answer_on_downstream", "downstream", answer),
        ("upload_on_downstream", "downstream", upload),
        ("download_transfer_id_zero", "downstream", {**download, "transfer_id": 0}),
        ("download_transfer_id_beyond_u32", "downstream", {**download, "transfer_id": 2**32}),
        ("download_filename_empty", "downstream", {**download, "filename": ""}),
        ("download_filename_too_long", "downstream", {**download, "filename": "n" * 256}),
        ("download_filename_with_slash", "downstream", {**download, "filename": "../secret.pdf"}),
        ("download_filename_with_backslash", "downstream", {**download, "filename": "dir\\secret.pdf"}),
        ("download_filename_dot_dot", "downstream", {**download, "filename": ".."}),
        ("download_filename_control_character", "downstream", {**download, "filename": "a\nb.pdf"}),
        ("download_size_beyond_u64", "downstream", {**download, "size": 2**64}),
        ("download_size_negative", "downstream", {**download, "size": -1}),
        ("download_mime_with_parameters", "downstream", {**download, "mime": "text/html; charset=utf-8"}),
        ("download_mime_without_subtype", "downstream", {**download, "mime": "pdf"}),
        ("download_unknown_member", "downstream", {**download, "url": "https://x"}),
        (
            "file_chooser_accept_missing",
            "downstream",
            {"kind": "view.file_chooser", "chooser_id": 1, "multiple": False},
        ),
        ("file_chooser_too_many_accept_entries", "downstream", {**chooser, "accept": [".pdf"] * 129}),
        ("file_chooser_accept_with_space", "downstream", {**chooser, "accept": ["image/png, image/jpeg"]}),
        ("file_chooser_id_zero", "downstream", {**chooser, "chooser_id": 0}),
        ("download_answer_unknown_outcome", "upstream", {**answer_to_download, "outcome": "maybe"}),
        ("download_answer_without_outcome", "upstream", {"kind": "view.download_answer", "transfer_id": 1}),
        ("file_chooser_answer_supplied_without_files", "upstream", {**answer, "file_count": 0}),
        ("file_chooser_answer_cancelled_with_files", "upstream", {**answer, "outcome": "cancelled"}),
        ("file_chooser_answer_negative_count", "upstream", {**answer, "file_count": -1}),
        ("upload_without_size", "upstream", {key: value for key, value in upload.items() if key != "size"}),
        ("upload_name_with_slash", "upstream", {**upload, "name": "a/b.pdf"}),
        ("upload_size_beyond_u64", "upstream", {**upload, "size": 2**64}),
        ("complete_sha256_upper_case", "downstream", {**complete, "sha256": _SHA256.upper()}),
        ("complete_sha256_short", "downstream", {**complete, "sha256": _SHA256[:63]}),
        ("complete_size_negative", "downstream", {**complete, "size": -1}),
        ("complete_size_beyond_u64", "upstream", {**complete, "size": 2**64}),
        ("credit_zero_chunks", "downstream", {**credit, "chunks": 0}),
        ("credit_beyond_the_window", "upstream", {**credit, "chunks": _TRANSFER_CREDIT_WINDOW + 1}),
        (
            "cancel_unknown_direction",
            "downstream",
            {"kind": "view.transfer_cancel", "direction": "sideways", "transfer_id": 1},
        ),
        ("cancel_without_direction", "upstream", {"kind": "view.transfer_cancel", "transfer_id": 1}),
    ]


def _documents() -> dict[str, list[dict[str, Any]]]:
    offer = {"offer_id": "0123456789abcdef0123456789abcdef", "url": "https://www.example.org/form?id=1"}
    pointer = {
        "type": "pointer",
        "action": "down",
        "x": 10,
        "y": 20,
        "button": "left",
        "click_count": 1,
        "modifiers": 0,
    }
    accepted = [
        ("image", "downstream", _image_document(0, 1)),
        ("state", "downstream", _STATE),
        ("state_acquiring", "downstream", {**_STATE, "phase": "acquiring", "loading": True, "title": ""}),
        ("notice_refused", "downstream", {"kind": "view.notice", "code": "request_refused"}),
        ("notice_offer", "downstream", {"kind": "view.notice", "code": "navigation_offered", "offer": offer}),
        (
            "notice_login_unavailable",
            "downstream",
            {"kind": "view.notice", "code": "login_unavailable", "offer": offer},
        ),
        (
            "notice_dialog",
            "downstream",
            {
                "kind": "view.notice",
                "code": "dialog_opened",
                "dialog": {"dialog_id": 1, "dialog_kind": "prompt", "message": "¿Seguro?", "default_prompt": "sí"},
            },
        ),
        ("closed", "downstream", {"kind": "view.closed", "reason": "session_retired"}),
        ("credit_two", "upstream", {"kind": "view.credit", "images": 2}),
        ("input_pointer_down", "upstream", {"kind": "view.input", "event": pointer}),
        (
            "input_pointer_move",
            "upstream",
            {"kind": "view.input", "event": {**pointer, "action": "move", "button": "none", "click_count": 0}},
        ),
        ("input_pointer_edge", "upstream", {"kind": "view.input", "event": {**pointer, "x": 4095, "y": 4095}}),
        (
            "input_wheel",
            "upstream",
            {
                "kind": "view.input",
                "event": {"type": "wheel", "x": 0, "y": 0, "delta_x": 0, "delta_y": -10000, "modifiers": 8},
            },
        ),
        (
            "input_key",
            "upstream",
            {
                "kind": "view.input",
                "event": {"type": "key", "action": "down", "key": "Enter", "code": "Enter", "modifiers": 2},
            },
        ),
        ("input_text", "upstream", {"kind": "view.input", "event": {"type": "text", "text": "ñ" * 256}}),
        ("navigate_home", "upstream", {"kind": "view.navigate", "verb": "home"}),
        ("resize", "upstream", {"kind": "view.resize", "css_width": 4096, "css_height": 1, "scale": 0.5}),
        ("dialog_accept", "upstream", {"kind": "view.dialog", "dialog_id": 1, "accept": True, "prompt_text": "sí"}),
        ("dialog_dismiss", "upstream", {"kind": "view.dialog", "dialog_id": 4294967295, "accept": False}),
        ("close", "upstream", {"kind": "view.close"}),
        *_transfer_documents_accepted(),
    ]
    refused = [
        ("unknown_kind", "downstream", {"kind": "view.frame"}),
        ("image_extra_member", "downstream", {**_image_document(0, 1), "url": "https://x"}),
        ("image_empty", "downstream", _image_document(0, 0)),
        ("image_oversize", "downstream", _image_document(0, _IMAGE_MAX + 1)),
        ("image_sequence_beyond_u32", "downstream", _image_document(2**32, 1)),
        ("image_scale_beyond_bound", "downstream", {**_image_document(0, 1), "scale": 4.5}),
        ("image_pixels_beyond_bound", "downstream", {**_image_document(0, 1), "pixel_width": 8193}),
        ("state_origin_with_path", "downstream", {**_STATE, "origin": "https://sede.agenciatributaria.gob.es/Sede"}),
        ("state_origin_http", "downstream", {**_STATE, "origin": "http://sede.agenciatributaria.gob.es"}),
        ("state_path_with_query", "downstream", {**_STATE, "path": "/Sede/x.html?nif=1"}),
        ("state_unknown_phase", "downstream", {**_STATE, "phase": "submitting"}),
        ("notice_offer_code_without_offer", "downstream", {"kind": "view.notice", "code": "popup_offered"}),
        ("notice_refusal_with_offer", "downstream", {"kind": "view.notice", "code": "request_refused", "offer": offer}),
        (
            "notice_offer_javascript",
            "downstream",
            {"kind": "view.notice", "code": "download_offered", "offer": {**offer, "url": "javascript:alert(1)"}},
        ),
        (
            "notice_offer_userinfo",
            "downstream",
            {"kind": "view.notice", "code": "download_offered", "offer": {**offer, "url": "https://a:b@example.org/"}},
        ),
        (
            "notice_offer_id_shape",
            "downstream",
            {"kind": "view.notice", "code": "popup_offered", "offer": {**offer, "offer_id": "ABC"}},
        ),
        ("notice_unknown_code", "downstream", {"kind": "view.notice", "code": "form_submitted"}),
        ("closed_unknown_reason", "downstream", {"kind": "view.closed", "reason": "crashed"}),
        ("credit_on_downstream", "downstream", {"kind": "view.credit", "images": 1}),
        ("image_on_upstream", "upstream", _image_document(0, 1)),
        ("credit_zero", "upstream", {"kind": "view.credit", "images": 0}),
        ("credit_three", "upstream", {"kind": "view.credit", "images": 3}),
        ("pointer_beyond_panel", "upstream", {"kind": "view.input", "event": {**pointer, "x": 4096}}),
        ("pointer_negative", "upstream", {"kind": "view.input", "event": {**pointer, "y": -1}}),
        ("pointer_press_without_button", "upstream", {"kind": "view.input", "event": {**pointer, "button": "none"}}),
        ("pointer_move_with_clicks", "upstream", {"kind": "view.input", "event": {**pointer, "action": "move"}}),
        ("pointer_float_coordinate", "upstream", {"kind": "view.input", "event": {**pointer, "x": 1.5}}),
        ("modifiers_beyond_mask", "upstream", {"kind": "view.input", "event": {**pointer, "modifiers": 16}}),
        ("text_too_long", "upstream", {"kind": "view.input", "event": {"type": "text", "text": "a" * 257}}),
        ("text_control_character", "upstream", {"kind": "view.input", "event": {"type": "text", "text": "a\nb"}}),
        ("text_empty", "upstream", {"kind": "view.input", "event": {"type": "text", "text": ""}}),
        ("unknown_input_type", "upstream", {"kind": "view.input", "event": {"type": "script", "source": "1"}}),
        (
            "key_unknown_action",
            "upstream",
            {
                "kind": "view.input",
                "event": {"type": "key", "action": "press", "key": "a", "code": "KeyA", "modifiers": 0},
            },
        ),
        (
            "wheel_beyond_bound",
            "upstream",
            {
                "kind": "view.input",
                "event": {"type": "wheel", "x": 0, "y": 0, "delta_x": 10001, "delta_y": 0, "modifiers": 0},
            },
        ),
        ("navigate_url", "upstream", {"kind": "view.navigate", "verb": "url"}),
        ("navigate_with_url_member", "upstream", {"kind": "view.navigate", "verb": "home", "url": "https://x"}),
        ("resize_zero", "upstream", {"kind": "view.resize", "css_width": 0, "css_height": 1, "scale": 1.0}),
        (
            "dialog_dismiss_with_text",
            "upstream",
            {"kind": "view.dialog", "dialog_id": 1, "accept": False, "prompt_text": "x"},
        ),
        ("dialog_id_zero", "upstream", {"kind": "view.dialog", "dialog_id": 0, "accept": True}),
        ("close_on_downstream", "downstream", {"kind": "view.close"}),
        ("close_with_reason", "upstream", {"kind": "view.close", "reason": "cancelled"}),
        *_transfer_documents_refused(),
    ]
    return {
        "accepted": [
            {"name": name, "direction": direction, "document": document} for name, direction, document in accepted
        ],
        "refused": [
            {"name": name, "direction": direction, "document": document} for name, direction, document in refused
        ],
    }


def vectors() -> dict[str, Any]:
    """Return the complete vectors document."""
    return {
        "schema": 1,
        "about": _ABOUT,
        "layout": {
            "frame_kind": "B",
            "control_frame_kind": "J",
            "refused_frame_kinds": ["E", "S"],
            "frame_max_bytes": _FRAME_MAX,
            "chunk_header_bytes": _HEADER,
            "chunk_body_bytes": _BODY,
            "image_max_bytes": _IMAGE_MAX,
            "version": 1,
            "last_flag": 1,
            "credit_max_images": 2,
            "image_pattern_modulus": _PATTERN_MODULUS,
            "transfer_flag": _TRANSFER_FLAG,
            "transfer_id_max": _TRANSFER_ID_MAX,
            "transfer_size_max": _TRANSFER_SIZE_MAX,
            "transfer_credit_max_chunks": _TRANSFER_CREDIT_WINDOW,
        },
        "headers": _headers(),
        "header_refusals": _header_refusals(),
        "streams": _streams(),
        "documents": _documents(),
        "transfer_headers": _transfer_headers(),
        "transfer_header_refusals": _transfer_header_refusals(),
        "transfer_streams": _transfer_streams(),
    }


def render() -> str:
    """Return the vectors file's exact text."""
    return json.dumps(vectors(), indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    """Write the vectors file, or with ``--check`` report whether it is current."""
    text = render()
    if argv == ["--check"]:
        current = VECTORS_PATH.read_text(encoding="utf-8") if VECTORS_PATH.exists() else None
        if current != text:
            sys.stderr.write(f"{VECTORS_PATH.name} is stale; regenerate it\n")
            return 1
        return 0
    if argv:
        sys.stderr.write("usage: view_stream_vector_source [--check]\n")
        return 2
    VECTORS_PATH.write_bytes(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
