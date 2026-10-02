"""Bounded private request bytes reach canonical decoding intact or are refused."""

from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError

from cadrumo.application.runtime.submission_payload import (
    SUBMISSION_PAYLOAD_CHUNK_BYTES,
    SUBMISSION_PAYLOAD_MAX_BYTES,
    SUBMISSION_PAYLOAD_TIMEOUT_SECONDS,
    SubmissionPayloadBuffer,
    SubmissionPayloadChunk,
    SubmissionPayloadDescriptor,
)
from cadrumo.core.hashing import sha256_hex

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _descriptor(payload: bytes) -> SubmissionPayloadDescriptor:
    return SubmissionPayloadDescriptor(byte_count=len(payload), payload_digest=sha256_hex(payload))


def _chunk(offset: int, payload: bytes) -> SubmissionPayloadChunk:
    return SubmissionPayloadChunk(offset=offset, encoded=base64.b64encode(payload).decode("ascii"))


def test_multichunk_unicode_roundtrip_uses_exact_utf8_bytes_and_wipes_buffer() -> None:
    prefix = b'{"nombre":"'
    payload = (
        prefix
        + b"x" * (SUBMISSION_PAYLOAD_CHUNK_BYTES - len(prefix) - 1)
        + "👋".encode()
        + '","detalle":"Peña"}'.encode()
    )
    # The first frame ends after just one byte of the emoji's UTF-8 sequence.
    assert payload[SUBMISSION_PAYLOAD_CHUNK_BYTES - 1 : SUBMISSION_PAYLOAD_CHUNK_BYTES + 3] == "👋".encode()
    buffer = SubmissionPayloadBuffer(_descriptor(payload))
    storage = buffer._content
    assert SUBMISSION_PAYLOAD_TIMEOUT_SECONDS == 30

    for offset in range(0, len(payload), SUBMISSION_PAYLOAD_CHUNK_BYTES):
        chunk = _chunk(offset, payload[offset : offset + SUBMISSION_PAYLOAD_CHUNK_BYTES])
        assert "Peña" not in repr(chunk)
        buffer.append(chunk)

    assert buffer.finish() == payload.decode("utf-8")
    assert storage == bytearray()
    with pytest.raises(ValueError, match="closed"):
        buffer.finish()
    with pytest.raises(ValueError, match="closed"):
        buffer.append(_chunk(0, b"{}"))


@pytest.mark.parametrize("byte_count", [0, 1, SUBMISSION_PAYLOAD_MAX_BYTES + 1, True])
def test_descriptor_refuses_unbounded_or_noninteger_byte_counts(byte_count: object) -> None:
    with pytest.raises(ValidationError):
        SubmissionPayloadDescriptor.model_validate({"byte_count": byte_count, "payload_digest": sha256_hex(b"{}")})


def test_descriptor_accepts_maximum_without_allocating_it() -> None:
    descriptor = SubmissionPayloadDescriptor(byte_count=SUBMISSION_PAYLOAD_MAX_BYTES, payload_digest=sha256_hex(b"{}"))
    assert descriptor.byte_count == SUBMISSION_PAYLOAD_MAX_BYTES
    with pytest.raises(ValidationError):
        SubmissionPayloadDescriptor(byte_count=2, payload_digest="not-a-digest")


@pytest.mark.parametrize("encoded", ["!!!!", "Zh==", "", "A" * (4 * ((SUBMISSION_PAYLOAD_CHUNK_BYTES + 2) // 3) + 4)])
def test_chunk_refuses_malformed_noncanonical_or_oversized_base64(encoded: str) -> None:
    try:
        chunk = SubmissionPayloadChunk(offset=0, encoded=encoded)
    except ValidationError:
        return
    with pytest.raises(ValueError, match="invalid submission payload chunk"):
        chunk.decode()


@pytest.mark.parametrize(
    ("offset", "first"),
    [
        (1, b"{}"),
        (0, b"{"),
        (0, b"{}x"),
    ],
)
def test_append_refuses_wrong_offset_or_length_and_closes(offset: int, first: bytes) -> None:
    buffer = SubmissionPayloadBuffer(_descriptor(b"{}"))
    with pytest.raises(ValueError, match="range"):
        buffer.append(_chunk(offset, first))
    with pytest.raises(ValueError, match="closed"):
        buffer.finish()


def test_append_requires_full_intermediate_chunk() -> None:
    payload = b"x" * (SUBMISSION_PAYLOAD_CHUNK_BYTES + 1)
    buffer = SubmissionPayloadBuffer(_descriptor(payload))
    with pytest.raises(ValueError, match="range"):
        buffer.append(_chunk(0, b"x" * (SUBMISSION_PAYLOAD_CHUNK_BYTES - 1)))


@pytest.mark.parametrize(
    ("payload", "submitted", "reason"),
    [
        (b"{}", None, "incomplete"),
        (b"{}", b"[]", "digest"),
        (b"\xff\xfe", b"\xff\xfe", "UTF-8"),
    ],
)
def test_finish_refuses_incomplete_digest_or_invalid_utf8_and_wipes(
    payload: bytes, submitted: bytes | None, reason: str
) -> None:
    buffer = SubmissionPayloadBuffer(_descriptor(payload))
    storage = buffer._content
    if submitted is not None:
        buffer.append(_chunk(0, submitted))
    with pytest.raises(ValueError, match=reason):
        buffer.finish()
    assert storage == bytearray()
    with pytest.raises(ValueError, match="closed"):
        buffer.append(_chunk(0, b"{}"))


def test_explicit_close_is_idempotent_and_prevents_reuse() -> None:
    buffer = SubmissionPayloadBuffer(_descriptor(b"{}"))
    storage = buffer._content
    buffer.append(_chunk(0, b"{}"))
    buffer.close()
    buffer.close()
    assert storage == bytearray()
    with pytest.raises(ValueError, match="closed"):
        buffer.finish()
