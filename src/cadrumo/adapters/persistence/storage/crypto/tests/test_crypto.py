"""Tests for the AEAD primitives and HKDF derivation helper."""

from __future__ import annotations

import secrets
from typing import cast

import pytest

from ...errors import DecryptionError, EncryptionError, KeyDerivationError
from ..aead import (
    GCM_TAG_SIZE,
    KEY_SIZE,
    NONCE_SIZE,
    EncryptedBlob,
    decrypt_record,
    derive_key,
    encrypt_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _fresh_key() -> bytes:
    return secrets.token_bytes(KEY_SIZE)


class TestEncryptDecryptRoundTrip:
    """``encrypt_record`` and ``decrypt_record`` are inverse functions."""

    def test_round_trip(self) -> None:
        """Encrypt-then-decrypt returns the original bytes for varied payloads."""
        plaintexts = (
            b"",
            b"hello",
            "movimientos bancarios — autónomo, NIF 12345678Z, año 2025".encode(),
            b"\x00\x01\x02\xff\xfe\xfd",
            # Deterministic 4096-byte payload (bytes 0..255 repeated); a fixed
            # value keeps pytest-xdist's collection identical across workers
            # without sacrificing the "large-payload round-trip" coverage.
            bytes(i % 256 for i in range(4096)),
        )
        for plaintext in plaintexts:
            key = _fresh_key()
            blob = encrypt_record(plaintext, key=key)
            assert decrypt_record(blob, key=key) == plaintext

    def test_round_trip_with_associated_data(self) -> None:
        """Associated data must be supplied identically at decrypt."""
        key = _fresh_key()
        plaintext = b"sensitive payload"
        aad = b"context:test:v1"
        blob = encrypt_record(plaintext, key=key, associated_data=aad)
        assert decrypt_record(blob, key=key, associated_data=aad) == plaintext

    def test_random_nonces_per_call(self) -> None:
        """Two encrypts of the same payload yield distinct nonces and ciphertexts."""
        key = _fresh_key()
        plaintext = b"deterministic input"
        first = encrypt_record(plaintext, key=key)
        second = encrypt_record(plaintext, key=key)
        assert first.nonce != second.nonce
        assert first.ciphertext != second.ciphertext

    def test_nonce_size_is_twelve_bytes(self) -> None:
        """The 96-bit GCM nonce convention is enforced."""
        key = _fresh_key()
        blob = encrypt_record(b"x", key=key)
        assert len(blob.nonce) == NONCE_SIZE
        assert NONCE_SIZE == 12

    def test_ciphertext_includes_gcm_tag(self) -> None:
        """The ciphertext field carries plaintext bytes + the 16-byte GCM tag."""
        key = _fresh_key()
        blob = encrypt_record(b"abc", key=key)
        assert len(blob.ciphertext) == len(b"abc") + GCM_TAG_SIZE


class TestTamperDetection:
    """Any modification to nonce, ciphertext, key, or AAD raises DecryptionError."""

    def test_modified_nonce_ciphertext_tag_or_key_raises(self) -> None:
        key = _fresh_key()
        blob = encrypt_record(b"payload", key=key)
        flipped_first_byte = bytes([blob.ciphertext[0] ^ 0x01]) + blob.ciphertext[1:]
        flipped_last_byte = blob.ciphertext[:-1] + bytes([blob.ciphertext[-1] ^ 0x01])
        other_nonce = secrets.token_bytes(NONCE_SIZE)
        # Ensure we picked a different nonce; collision odds are 2**-96.
        assert other_nonce != blob.nonce
        cases = (
            (blob, _fresh_key()),
            (EncryptedBlob(nonce=blob.nonce, ciphertext=flipped_first_byte), key),
            (EncryptedBlob(nonce=blob.nonce, ciphertext=flipped_last_byte), key),
            (EncryptedBlob(nonce=other_nonce, ciphertext=blob.ciphertext), key),
        )
        for candidate_blob, candidate_key in cases:
            with pytest.raises(DecryptionError):
                decrypt_record(candidate_blob, key=candidate_key)

    def test_aad_mismatch_or_omission_raises(self) -> None:
        key = _fresh_key()
        blob = encrypt_record(b"payload", key=key, associated_data=b"context:a")
        with pytest.raises(DecryptionError):
            decrypt_record(blob, key=key, associated_data=b"context:b")

        missing_aad_blob = encrypt_record(b"payload", key=key, associated_data=b"context")
        with pytest.raises(DecryptionError):
            decrypt_record(missing_aad_blob, key=key)


class TestKeySizeValidation:
    """The substrate refuses anything other than a 32-byte AES-256 key."""

    def test_encrypt_and_decrypt_reject_wrong_key_sizes(self) -> None:
        blob = encrypt_record(b"payload", key=_fresh_key())
        for invalid_size in (0, 15, 16, 24, 33, 64):
            invalid_key = secrets.token_bytes(invalid_size)
            with pytest.raises(EncryptionError):
                encrypt_record(b"payload", key=invalid_key)
            with pytest.raises(EncryptionError):
                decrypt_record(blob, key=invalid_key)

    def test_encrypt_wraps_invalid_plaintext_type_as_encryption_error(self) -> None:
        with pytest.raises(EncryptionError):
            encrypt_record(cast(bytes, "payload"), key=_fresh_key())

    def test_decrypt_wraps_invalid_associated_data_type_as_decryption_error(self) -> None:
        key = _fresh_key()
        blob = encrypt_record(b"payload", key=key, associated_data=b"context")
        with pytest.raises(DecryptionError):
            decrypt_record(blob, key=key, associated_data=cast(bytes, "context"))


class TestEncryptedBlobShape:
    """The frozen pydantic record validates its own size invariants."""

    def test_to_wire_round_trip(self) -> None:
        """``to_wire`` and ``from_wire`` are inverse on valid blobs."""
        key = _fresh_key()
        blob = encrypt_record(b"hello world", key=key)
        wire = blob.to_wire()
        restored = EncryptedBlob.from_wire(wire)
        assert restored == blob
        assert decrypt_record(restored, key=key) == b"hello world"

    def test_from_wire_rejects_short_payload(self) -> None:
        """A wire payload shorter than nonce + tag minimum raises."""
        with pytest.raises(DecryptionError):
            EncryptedBlob.from_wire(b"x" * (NONCE_SIZE + GCM_TAG_SIZE - 1))

    def test_blob_rejects_wrong_nonce_length(self) -> None:
        from pydantic import ValidationError

        ciphertext = b"x" * (GCM_TAG_SIZE + 1)
        with pytest.raises(ValidationError):
            EncryptedBlob(nonce=b"\x00" * (NONCE_SIZE - 1), ciphertext=ciphertext)
        with pytest.raises(ValidationError):
            EncryptedBlob(nonce=b"\x00" * (NONCE_SIZE + 1), ciphertext=ciphertext)

    def test_blob_rejects_under_size_ciphertext(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EncryptedBlob(nonce=b"\x00" * NONCE_SIZE, ciphertext=b"\x00" * (GCM_TAG_SIZE - 1))


class TestHkdfDerivation:
    """``derive_key`` produces deterministic, context-bound key material."""

    def test_deterministic_and_bound_to_context_and_salt(self) -> None:
        ikm = b"master-key-material"
        salt = b"per-store-salt"
        first = derive_key(key_material=ikm, salt=salt, context=b"cadrumo.context.v1")
        second = derive_key(key_material=ikm, salt=salt, context=b"cadrumo.context.v1")
        assert first == second

        lookup_key = derive_key(key_material=ikm, salt=salt, context=b"cadrumo.lookup.v1")
        envelope_key = derive_key(key_material=ikm, salt=salt, context=b"cadrumo.envelope.v1")
        assert lookup_key != envelope_key

        salt_a_key = derive_key(key_material=ikm, salt=b"salt-a", context=b"cadrumo.context.v1")
        salt_b_key = derive_key(key_material=ikm, salt=b"salt-b", context=b"cadrumo.context.v1")
        assert salt_a_key != salt_b_key

    def test_default_length_is_aes256_key_size(self) -> None:
        derived = derive_key(
            key_material=b"ikm",
            salt=b"salt",
            context=b"cadrumo.context.v1",
        )
        assert len(derived) == KEY_SIZE

    def test_custom_length(self) -> None:
        for length in (16, 24, 48, 64):
            derived = derive_key(
                key_material=b"ikm",
                salt=b"salt",
                context=b"cadrumo.context.v1",
                length=length,
            )
            assert len(derived) == length

    def test_non_positive_length_rejected(self) -> None:
        for length in (0, -1):
            with pytest.raises(KeyDerivationError):
                derive_key(
                    key_material=b"ikm",
                    salt=b"salt",
                    context=b"cadrumo.context.v1",
                    length=length,
                )

    def test_invalid_context_type_is_wrapped_as_key_derivation_error(self) -> None:
        with pytest.raises(KeyDerivationError):
            derive_key(
                key_material=b"ikm",
                salt=b"salt",
                context=cast(bytes, "cadrumo.context.v1"),
            )

    def test_derived_key_can_drive_encrypt_round_trip(self) -> None:
        """End-to-end: HKDF-derived key works as an AES-256-GCM key."""
        master = secrets.token_bytes(KEY_SIZE)
        derived = derive_key(
            key_material=master,
            salt=b"per-store-salt",
            context=b"aeat-test.v1",
        )
        plaintext = b"end-to-end derived-key encryption"
        blob = encrypt_record(plaintext, key=derived)
        assert decrypt_record(blob, key=derived) == plaintext


class TestErrorCodeRegistration:
    """Every new exception class binds to a registered ErrorCode."""

    def test_classes_bind_to_registered_codes(self) -> None:
        cases = (
            ("EncryptionError", "INTEGRITY_STORAGE_ENCRYPTION"),
            ("DecryptionError", "INTEGRITY_STORAGE_DECRYPTION"),
            ("KeyDerivationError", "INTEGRITY_STORAGE_KEY_DERIVATION"),
            ("NonceCollisionError", "INTEGRITY_STORAGE_NONCE_COLLISION"),
            ("PersistenceError", "FAIL_STORAGE_PERSISTENCE"),
        )
        from ......core.errors.error_codes import bind_error_code
        from ... import errors as storage_errors

        for error_class, expected_code in cases:
            cls = getattr(storage_errors, error_class)
            bound = bind_error_code(cls)
            assert bound is not None
            assert bound.code == expected_code
