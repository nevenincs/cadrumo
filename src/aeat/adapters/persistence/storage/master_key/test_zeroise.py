"""Tests for the `zeroise` in-memory wipe primitive."""

from __future__ import annotations

import pytest

from aeat.adapters.persistence.storage.master_key._zeroise import zeroise

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def test_zeroise_overwrites_non_zero_buffer_in_place() -> None:
    buffer = bytearray(b"\x01\x02\x03\x04\x05")

    zeroise(buffer)

    assert bytes(buffer) == bytes(5)


def test_zeroise_handles_empty_buffer() -> None:
    buffer = bytearray()

    zeroise(buffer)

    assert bytes(buffer) == b""


def test_zeroise_handles_long_buffer() -> None:
    buffer = bytearray(b"\xff" * 4096)

    zeroise(buffer)

    assert bytes(buffer) == bytes(4096)


def test_zeroise_does_not_replace_buffer_object() -> None:
    """The caller's reference still points at the same object after wipe."""

    buffer = bytearray(b"\x01" * 32)
    original_id = id(buffer)

    zeroise(buffer)

    assert id(buffer) == original_id


def test_zeroise_rejects_immutable_bytes() -> None:
    """Python cannot overwrite immutable `bytes`; the contract is enforced."""
    with pytest.raises(TypeError, match="bytearray"):
        zeroise(b"\x01" * 32)


def test_zeroise_rejects_non_bytes_like() -> None:
    with pytest.raises(TypeError, match="bytearray"):
        zeroise("password")
