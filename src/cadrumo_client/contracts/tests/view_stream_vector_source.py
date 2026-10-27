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
    "or refuse, in their closed sets."
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
        },
        "headers": _headers(),
        "header_refusals": _header_refusals(),
        "streams": _streams(),
        "documents": _documents(),
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
