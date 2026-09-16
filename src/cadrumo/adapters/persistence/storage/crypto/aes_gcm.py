"""AES-256-GCM sealing with a fresh random nonce, on plain bytes.

The one AES-GCM implementation. :mod:`.aead` wraps it in the typed
:class:`~.aead.EncryptedBlob` record and the storage error hierarchy; the
supervised key-derivation child calls it directly. That child is started for
every wrap and unwrap, so this module imports only :mod:`cryptography` and the
standard library -- no pydantic, no error hierarchy -- and reports failures as
the builtin and :mod:`cryptography` exceptions its callers translate.
"""

from __future__ import annotations

import secrets
from typing import Final

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_SIZE: Final = 12
"""AES-256-GCM nonce size in bytes (per NIST SP 800-38D)."""

GCM_TAG_SIZE: Final = 16
"""AES-256-GCM authentication-tag size in bytes."""

KEY_SIZE: Final = 32
"""AES-256 key size in bytes."""


class AesGcmKeyLengthError(ValueError):
    """Raised when a key is not exactly :data:`KEY_SIZE` bytes.

    ``AESGCM`` itself also accepts 128- and 192-bit keys, so the AES-256
    requirement is enforced here rather than left to the library.
    """


def _cipher(key: bytes) -> AESGCM:
    if len(key) != KEY_SIZE:
        raise AesGcmKeyLengthError(f"AES-256-GCM key must be exactly {KEY_SIZE} bytes; got {len(key)}")
    return AESGCM(key)


def seal(plaintext: bytes, *, key: bytes, associated_data: bytes | None = None) -> tuple[bytes, bytes]:
    """Encrypt ``plaintext`` under a fresh random nonce.

    Returns:
        ``(nonce, ciphertext_with_tag)``; the tag is the trailing
        :data:`GCM_TAG_SIZE` bytes.

    Raises:
        AesGcmKeyLengthError: If ``key`` is not exactly :data:`KEY_SIZE` bytes.
        TypeError, ValueError: If the underlying AEAD operation refuses its input.
    """
    cipher = _cipher(key)
    nonce = secrets.token_bytes(NONCE_SIZE)
    return nonce, cipher.encrypt(nonce, plaintext, associated_data)


def open_sealed(nonce: bytes, ciphertext: bytes, *, key: bytes, associated_data: bytes | None = None) -> bytes:
    """Decrypt ``ciphertext`` (with its trailing tag) and verify it.

    Raises:
        AesGcmKeyLengthError: If ``key`` is not exactly :data:`KEY_SIZE` bytes.
        cryptography.exceptions.InvalidTag: If authentication fails.
        TypeError, ValueError: If the underlying AEAD operation refuses its input.
    """
    return _cipher(key).decrypt(nonce, ciphertext, associated_data)


__all__ = [
    "GCM_TAG_SIZE",
    "KEY_SIZE",
    "NONCE_SIZE",
    "AesGcmKeyLengthError",
    "open_sealed",
    "seal",
]
