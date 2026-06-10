"""Tests for the AEAD primitives and HKDF derivation helper."""

from __future__ import annotations

import secrets

import pytest

from ...errors import DecryptionError, EncryptionError, KeyDerivationError
from .._crypto import (
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

    @pytest.mark.parametrize(
        "plaintext",
        [
            b"",
            b"hello",
            "movimientos bancarios — autónomo, NIF 12345678Z, año 2025".encode(),
            b"\x00\x01\x02\xff\xfe\xfd",
            # Deterministic 4096-byte payload (bytes 0..255 repeated); a fixed
            # value keeps pytest-xdist's collection identical across workers
            # without sacrificing the "large-payload round-trip" coverage.
            bytes(i % 256 for i in range(4096)),
        ],
        ids=["empty", "ascii", "unicode", "raw-bytes", "large-4096"],
    )
    def test_round_trip(self, plaintext: bytes) -> None:
        """Encrypt-then-decrypt returns the original bytes for varied payloads."""
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

    def test_wrong_key_raises(self) -> None:
        plaintext = b"payload"
        blob = encrypt_record(plaintext, key=_fresh_key())
        with pytest.raises(DecryptionError):
            decrypt_record(blob, key=_fresh_key())

    def test_tampered_ciphertext_raises(self) -> None:
        key = _fresh_key()
        blob = encrypt_record(b"payload", key=key)
        flipped_first_byte = bytes([blob.ciphertext[0] ^ 0x01]) + blob.ciphertext[1:]
        tampered = EncryptedBlob(nonce=blob.nonce, ciphertext=flipped_first_byte)
        with pytest.raises(DecryptionError):
            decrypt_record(tampered, key=key)

    def test_tampered_tag_raises(self) -> None:
        key = _fresh_key()
        blob = encrypt_record(b"payload", key=key)
        flipped_last_byte = blob.ciphertext[:-1] + bytes([blob.ciphertext[-1] ^ 0x01])
        tampered = EncryptedBlob(nonce=blob.nonce, ciphertext=flipped_last_byte)
        with pytest.raises(DecryptionError):
            decrypt_record(tampered, key=key)

    def test_swapped_nonce_raises(self) -> None:
        key = _fresh_key()
        blob = encrypt_record(b"payload", key=key)
        other_nonce = secrets.token_bytes(NONCE_SIZE)
        # Ensure we picked a different nonce; collision odds are 2**-96.
        assert other_nonce != blob.nonce
        with pytest.raises(DecryptionError):
            decrypt_record(EncryptedBlob(nonce=other_nonce, ciphertext=blob.ciphertext), key=key)

    def test_aad_mismatch_raises(self) -> None:
        key = _fresh_key()
        blob = encrypt_record(b"payload", key=key, associated_data=b"context:a")
        with pytest.raises(DecryptionError):
            decrypt_record(blob, key=key, associated_data=b"context:b")

    def test_missing_aad_at_decrypt_raises(self) -> None:
        """Encrypting with AAD then decrypting without it MUST fail."""
        key = _fresh_key()
        blob = encrypt_record(b"payload", key=key, associated_data=b"context")
        with pytest.raises(DecryptionError):
            decrypt_record(blob, key=key)


class TestKeySizeValidation:
    """The substrate refuses anything other than a 32-byte AES-256 key."""

    @pytest.mark.parametrize("invalid_size", [0, 15, 16, 24, 33, 64])
    def test_encrypt_rejects_wrong_key_size(self, invalid_size: int) -> None:
        with pytest.raises(EncryptionError):
            encrypt_record(b"payload", key=secrets.token_bytes(invalid_size))

    @pytest.mark.parametrize("invalid_size", [0, 15, 16, 24, 33, 64])
    def test_decrypt_rejects_wrong_key_size(self, invalid_size: int) -> None:
        blob = encrypt_record(b"payload", key=_fresh_key())
        with pytest.raises(EncryptionError):
            decrypt_record(blob, key=secrets.token_bytes(invalid_size))

    def test_encrypt_wraps_invalid_plaintext_type_as_encryption_error(self) -> None:
        with pytest.raises(EncryptionError):
            encrypt_record("payload", key=_fresh_key())  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # negative test: intentionally invalid input

    def test_decrypt_wraps_invalid_associated_data_type_as_decryption_error(self) -> None:
        key = _fresh_key()
        blob = encrypt_record(b"payload", key=key, associated_data=b"context")
        with pytest.raises(DecryptionError):
            decrypt_record(blob, key=key, associated_data="context")  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # negative test: intentionally invalid input


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

    def test_deterministic_for_fixed_inputs(self) -> None:
        ikm = b"master-key-material"
        salt = b"per-store-salt"
        first = derive_key(key_material=ikm, salt=salt, context=b"aeat.context.v1")
        second = derive_key(key_material=ikm, salt=salt, context=b"aeat.context.v1")
        assert first == second

    def test_different_contexts_yield_different_keys(self) -> None:
        ikm = b"master-key-material"
        salt = b"per-store-salt"
        a = derive_key(key_material=ikm, salt=salt, context=b"aeat.lookup.v1")
        b = derive_key(key_material=ikm, salt=salt, context=b"aeat.envelope.v1")
        assert a != b

    def test_different_salts_yield_different_keys(self) -> None:
        ikm = b"master-key-material"
        a = derive_key(key_material=ikm, salt=b"salt-a", context=b"aeat.context.v1")
        b = derive_key(key_material=ikm, salt=b"salt-b", context=b"aeat.context.v1")
        assert a != b

    def test_default_length_is_aes256_key_size(self) -> None:
        derived = derive_key(
            key_material=b"ikm",
            salt=b"salt",
            context=b"aeat.context.v1",
        )
        assert len(derived) == KEY_SIZE

    @pytest.mark.parametrize("length", [16, 24, 48, 64])
    def test_custom_length(self, length: int) -> None:
        derived = derive_key(
            key_material=b"ikm",
            salt=b"salt",
            context=b"aeat.context.v1",
            length=length,
        )
        assert len(derived) == length

    def test_zero_length_rejected(self) -> None:
        with pytest.raises(KeyDerivationError):
            derive_key(
                key_material=b"ikm",
                salt=b"salt",
                context=b"aeat.context.v1",
                length=0,
            )

    def test_negative_length_rejected(self) -> None:
        with pytest.raises(KeyDerivationError):
            derive_key(
                key_material=b"ikm",
                salt=b"salt",
                context=b"aeat.context.v1",
                length=-1,
            )

    def test_invalid_context_type_is_wrapped_as_key_derivation_error(self) -> None:
        with pytest.raises(KeyDerivationError):
            derive_key(
                key_material=b"ikm",
                salt=b"salt",
                context="aeat.context.v1",  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # negative test: intentionally invalid input
            )

    def test_derived_key_can_drive_encrypt_round_trip(self) -> None:
        """End-to-end: HKDF-derived key works as an AES-256-GCM key."""
        master = secrets.token_bytes(KEY_SIZE)
        derived = derive_key(
            key_material=master,
            salt=b"per-store-salt",
            context=b"aeat.test.v1",
        )
        plaintext = b"end-to-end derived-key encryption"
        blob = encrypt_record(plaintext, key=derived)
        assert decrypt_record(blob, key=derived) == plaintext


class TestErrorCodeRegistration:
    """Every new exception class binds to a registered ErrorCode."""

    @pytest.mark.parametrize(
        ("error_class", "expected_code"),
        [
            ("EncryptionError", "INTEGRITY_STORAGE_ENCRYPTION"),
            ("DecryptionError", "INTEGRITY_STORAGE_DECRYPTION"),
            ("KeyDerivationError", "INTEGRITY_STORAGE_KEY_DERIVATION"),
            ("NonceCollisionError", "INTEGRITY_STORAGE_NONCE_COLLISION"),
            ("PersistenceError", "FAIL_STORAGE_PERSISTENCE"),
        ],
    )
    def test_class_binds_to_registered_code(
        self,
        error_class: str,
        expected_code: str,
    ) -> None:
        from ......core.errors._registry import bind_error_code
        from ... import errors as storage_errors

        cls = getattr(storage_errors, error_class)
        bound = bind_error_code(cls)
        assert bound is not None
        assert bound.code == expected_code
