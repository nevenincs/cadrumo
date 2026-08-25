"""Tests for the `zeroise` in-memory wipe primitive."""

from __future__ import annotations

import pytest

from ..errors import WipeTypeError
from .._zeroise import zeroise

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


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
    with pytest.raises(WipeTypeError, match="bytearray") as excinfo:
        zeroise(b"\x01" * 32)
    assert excinfo.value.translated_message == "errors.internal.internal_wipe_type"
    assert excinfo.value.context == {"received_type": "bytes"}


def test_zeroise_rejects_non_bytes_like() -> None:
    with pytest.raises(WipeTypeError, match="bytearray") as excinfo:
        zeroise("password")
    assert excinfo.value.translated_message == "errors.internal.internal_wipe_type"
    assert excinfo.value.context == {"received_type": "str"}
    assert "password" not in str(excinfo.value)


def test_wipe_type_error_is_storage_error_and_type_error() -> None:
    """The refusal stays catchable as both, which is what callers rely on.

    Re-sited with the error rather than dropped: a caller that guards a wipe
    with a bare ``except TypeError`` keeps working, and the typed storage
    surface still propagates across domain boundaries.
    """
    from ...errors import StorageError

    assert issubclass(WipeTypeError, StorageError)
    assert issubclass(WipeTypeError, TypeError)
