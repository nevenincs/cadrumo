"""Tests for AES-256-GCM wrap/unwrap of the per-bucket DEK.

The known-answer ciphertext below was captured from a one-time direct
invocation of `cryptography.hazmat.primitives.ciphers.aead.AESGCM`
under the documented inputs; the upstream library is the reference
authority. The substrate's `wrap_dek` mints a fresh random nonce per
call, so the wrap KAT is exercised by feeding a fixed nonce through
`AESGCM` directly and asserting `unwrap_dek` recovers the DEK from the
captured `WrappedDek` shape.
"""

from __future__ import annotations

import pytest
from cryptography.exceptions import InvalidTag

from ......core.errors import build_error_envelope
from ...errors import DecryptionError, EncryptionError
from .._dek_wrap import (
    WrappedDek,
    unwrap_dek,
    wrap_dek,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


_REFERENCE_KEK = bytes.fromhex(
    "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff",
)
_REFERENCE_DEK = bytes.fromhex(
    "a0a1a2a3a4a5a6a7a8a9aaabacadaeafb0b1b2b3b4b5b6b7b8b9babbbcbdbebf",
)
_REFERENCE_NONCE = bytes.fromhex("0123456789abcdef01234567")
_REFERENCE_BUCKET = "bucket-a"
# Captured via:
#   from cryptography.hazmat.primitives.ciphers.aead import AESGCM
#   AESGCM(_REFERENCE_KEK).encrypt(_REFERENCE_NONCE, _REFERENCE_DEK,
#       b"aeat.dek-wrap.v1:bucket-a")
_REFERENCE_CIPHERTEXT_WITH_TAG = bytes.fromhex(
    "544545e66d237ace67966d425b8df6ee9c83200606732831f8a2fc5fa41c5a0cae235f7967e573c9a93eee2e98ab458d",
)
_REFERENCE_CIPHERTEXT = _REFERENCE_CIPHERTEXT_WITH_TAG[:32]
_REFERENCE_TAG = _REFERENCE_CIPHERTEXT_WITH_TAG[32:]


def test_unwrap_dek_matches_upstream_reference_vector() -> None:
    """Known-answer: a fixed-nonce wrapped DEK round-trips to the DEK."""

    wrapped = WrappedDek(
        nonce=_REFERENCE_NONCE,
        ciphertext=_REFERENCE_CIPHERTEXT,
        tag=_REFERENCE_TAG,
    )

    recovered = unwrap_dek(
        kek=_REFERENCE_KEK,
        wrapped=wrapped,
        bucket_id=_REFERENCE_BUCKET,
    )

    assert recovered == _REFERENCE_DEK


def test_wrap_then_unwrap_round_trip_returns_dek() -> None:
    """Property: `unwrap_dek(wrap_dek(dek)) == dek` for random nonces."""

    wrapped = wrap_dek(kek=_REFERENCE_KEK, dek=_REFERENCE_DEK, bucket_id="bucket-x")

    assert len(wrapped.nonce) == 12
    assert len(wrapped.ciphertext) == 32
    assert len(wrapped.tag) == 16

    recovered = unwrap_dek(kek=_REFERENCE_KEK, wrapped=wrapped, bucket_id="bucket-x")
    assert recovered == _REFERENCE_DEK


def test_wrap_uses_fresh_nonce_per_call() -> None:
    """The substrate must never re-use a nonce under the same KEK."""

    a = wrap_dek(kek=_REFERENCE_KEK, dek=_REFERENCE_DEK, bucket_id="bucket-x")
    b = wrap_dek(kek=_REFERENCE_KEK, dek=_REFERENCE_DEK, bucket_id="bucket-x")

    assert a.nonce != b.nonce
    assert a.ciphertext != b.ciphertext


def test_unwrap_fails_when_kek_differs() -> None:
    wrapped = wrap_dek(kek=_REFERENCE_KEK, dek=_REFERENCE_DEK, bucket_id="bucket-x")
    wrong_kek = bytes(32)

    with pytest.raises(DecryptionError) as exc_info:
        unwrap_dek(kek=wrong_kek, wrapped=wrapped, bucket_id="bucket-x")
    assert isinstance(exc_info.value.__cause__, InvalidTag)
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_decryption"
    assert "bucket-x" not in str(exc_info.value)
    envelope = build_error_envelope(exc_info.value)
    assert envelope.message
    assert "bucket-x" not in envelope.model_dump_json()


def test_unwrap_fails_when_bucket_id_differs() -> None:
    """AEAD AAD binds the wrap to one bucket; a mismatched id fails closed."""

    wrapped = wrap_dek(kek=_REFERENCE_KEK, dek=_REFERENCE_DEK, bucket_id="bucket-x")

    with pytest.raises(DecryptionError) as exc_info:
        unwrap_dek(kek=_REFERENCE_KEK, wrapped=wrapped, bucket_id="bucket-y")
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_decryption"


def test_unwrap_fails_when_tag_is_tampered() -> None:
    wrapped = wrap_dek(kek=_REFERENCE_KEK, dek=_REFERENCE_DEK, bucket_id="bucket-x")
    tampered = WrappedDek(
        nonce=wrapped.nonce,
        ciphertext=wrapped.ciphertext,
        tag=bytes([wrapped.tag[0] ^ 0x01]) + wrapped.tag[1:],
    )

    with pytest.raises(DecryptionError) as exc_info:
        unwrap_dek(kek=_REFERENCE_KEK, wrapped=tampered, bucket_id="bucket-x")
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_decryption"


def test_unwrap_fails_when_ciphertext_is_tampered() -> None:
    wrapped = wrap_dek(kek=_REFERENCE_KEK, dek=_REFERENCE_DEK, bucket_id="bucket-x")
    tampered = WrappedDek(
        nonce=wrapped.nonce,
        ciphertext=bytes([wrapped.ciphertext[0] ^ 0x01]) + wrapped.ciphertext[1:],
        tag=wrapped.tag,
    )

    with pytest.raises(DecryptionError) as exc_info:
        unwrap_dek(kek=_REFERENCE_KEK, wrapped=tampered, bucket_id="bucket-x")
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_decryption"


def test_wrap_rejects_wrong_size_kek() -> None:
    with pytest.raises(EncryptionError, match="kek must be exactly 32 bytes") as exc_info:
        wrap_dek(kek=b"x" * 16, dek=_REFERENCE_DEK, bucket_id="bucket-x")
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_encryption"


def test_wrap_rejects_wrong_size_dek() -> None:
    with pytest.raises(EncryptionError, match="dek must be exactly 32 bytes") as exc_info:
        wrap_dek(kek=_REFERENCE_KEK, dek=b"x" * 16, bucket_id="bucket-x")
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_encryption"


def test_wrap_rejects_empty_bucket_id() -> None:
    with pytest.raises(EncryptionError, match="bucket_id must be non-empty") as exc_info:
        wrap_dek(kek=_REFERENCE_KEK, dek=_REFERENCE_DEK, bucket_id="")
    assert exc_info.value.translated_message == "errors.integrity.integrity_storage_encryption"


def test_wrapped_dek_strict_validation_rejects_wrong_field_lengths() -> None:
    """pydantic strict validation enforces the on-wire byte budgets."""

    with pytest.raises(ValueError):
        WrappedDek(nonce=b"\x00" * 11, ciphertext=b"\x00" * 32, tag=b"\x00" * 16)
    with pytest.raises(ValueError):
        WrappedDek(nonce=b"\x00" * 12, ciphertext=b"\x00" * 31, tag=b"\x00" * 16)
    with pytest.raises(ValueError):
        WrappedDek(nonce=b"\x00" * 12, ciphertext=b"\x00" * 32, tag=b"\x00" * 15)
