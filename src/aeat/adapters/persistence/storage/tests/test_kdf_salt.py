"""Tests for shared storage KDF salt codec helpers."""

from __future__ import annotations

import pytest

from .._kdf_salt import KDF_SALT_BYTES, decode_kdf_salt, encode_kdf_salt, require_kdf_salt_length
from ..errors import StorageValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_encode_decode_kdf_salt_round_trips_exact_bytes() -> None:
    salt = b"0123456789abcdef"

    encoded = encode_kdf_salt(salt)
    decoded = decode_kdf_salt(encoded)

    assert decoded == salt


def test_decode_kdf_salt_accepts_bytes_without_copying_contract_change() -> None:
    salt = b"0123456789abcdef"

    assert decode_kdf_salt(salt) is salt


def test_require_kdf_salt_length_accepts_canonical_length() -> None:
    salt = b"0" * KDF_SALT_BYTES

    assert require_kdf_salt_length(salt) == salt


@pytest.mark.parametrize("invalid_salt", [b"short", b"0" * (KDF_SALT_BYTES + 1)])
def test_require_kdf_salt_length_raises_configured_error_type(invalid_salt: bytes) -> None:
    with pytest.raises(StorageValidationError, match="salt must be exactly 16 bytes"):
        require_kdf_salt_length(invalid_salt, error_type=StorageValidationError)


def test_decode_kdf_salt_rejects_non_bytes_non_string_with_configured_error_type() -> None:
    with pytest.raises(StorageValidationError, match="salt must be bytes or base64 string"):
        decode_kdf_salt(123, error_type=StorageValidationError)
