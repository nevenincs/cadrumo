"""Real-behavior tests for EncryptionError at every migrated raise in _dek_wrap.py (contract).

Asserts that:
- `wrap_dek` and `_associated_data` raise `EncryptionError` for each invalid
  input path (wrong-size kek, wrong-size dek, empty bucket_id).
- `EncryptionError` round-trips through `build_error_envelope`.
"""

from __future__ import annotations

import pytest

from ......core.errors import ERROR_REGISTRY, build_error_envelope
from ...errors import EncryptionError
from .._dek_wrap import wrap_dek

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_VALID_KEK = bytes(range(32))
_VALID_DEK = bytes(range(32, 64))


def test_wrap_dek_raises_encryption_error_for_short_kek() -> None:
    """_dek_wrap.py:74 — short kek raises EncryptionError."""

    with pytest.raises(EncryptionError, match="kek must be exactly 32 bytes"):
        wrap_dek(kek=b"x" * 16, dek=_VALID_DEK, bucket_id="bucket-a")


def test_wrap_dek_raises_encryption_error_for_short_dek() -> None:
    """_dek_wrap.py:76 — short dek raises EncryptionError."""

    with pytest.raises(EncryptionError, match="dek must be exactly 32 bytes"):
        wrap_dek(kek=_VALID_KEK, dek=b"x" * 16, bucket_id="bucket-a")


def test_wrap_dek_raises_encryption_error_for_empty_bucket_id() -> None:
    """_dek_wrap.py:49 (_associated_data) — empty bucket_id raises EncryptionError."""

    with pytest.raises(EncryptionError, match="bucket_id must be non-empty"):
        wrap_dek(kek=_VALID_KEK, dek=_VALID_DEK, bucket_id="")


def test_encryption_error_is_registered() -> None:
    """EncryptionError must have a bound ErrorCode in ERROR_REGISTRY."""

    err = EncryptionError("test")
    code = err.code

    assert code.code in ERROR_REGISTRY


def test_encryption_error_envelope_round_trip() -> None:
    """build_error_envelope produces a well-formed envelope from EncryptionError."""

    err = EncryptionError("kek must be exactly 32 bytes")
    envelope = build_error_envelope(err)

    assert envelope.code in ERROR_REGISTRY
    assert envelope.retryable is False
    assert envelope.message
