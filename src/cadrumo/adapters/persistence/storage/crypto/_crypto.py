"""AEAD primitives and HKDF derivation for at-rest persistence.

Wraps :mod:`cryptography.hazmat.primitives.ciphers.aead.AESGCM` and
:mod:`cryptography.hazmat.primitives.kdf.hkdf.HKDF` behind a small,
typed surface. The at-rest crypto stack pivots on this module:
column-level :class:`TypeDecorator` instances, the encrypted blob
store, the secret store, and the schema-version envelope all consume
:func:`encrypt_record`, :func:`decrypt_record`, and :func:`derive_key`.

The on-wire shape of :class:`EncryptedBlob` is deliberately minimal —
``nonce || ciphertext_with_tag``. The AEAD identifier and any version
metadata live in the envelope record (see :mod:`adapters.persistence.storage`'s
:class:`EncryptionMetadata`), so a future swap to e.g. ChaCha20-Poly1305
or an Argon2id-derived KEK can define a new current envelope contract
without changing this primitive blob shape.
"""

from __future__ import annotations

import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pydantic import BaseModel, Field

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..errors import DecryptionError, EncryptionError, KeyDerivationError

NONCE_SIZE: int = 12
"""AES-256-GCM nonce size in bytes (per NIST SP 800-38D)."""

GCM_TAG_SIZE: int = 16
"""AES-256-GCM authentication-tag size in bytes."""

KEY_SIZE: int = 32
"""AES-256 key size in bytes."""


class EncryptedBlob(BaseModel):
    """One frozen unit of AEAD ciphertext.

    The on-wire form is ``nonce || ciphertext_with_tag``. Callers that
    persist the blob choose the wire encoding (raw BLOB column,
    base64-in-JSON, etc.). The pydantic record is the in-memory
    canonical form.

    Attributes:
        nonce: 12 random bytes used exactly once with the wrapping key.
            Sourced from :func:`secrets.token_bytes`; the GCM birthday
            bound permits roughly 2**32 random nonces per key.
        ciphertext: AES-256-GCM ciphertext concatenated with its 16-byte
            authentication tag. The ``min_length=GCM_TAG_SIZE`` permits
            a bare 16-byte authentication tag, which is the legitimate
            shape for an empty-plaintext encryption (``encrypt_record(b"")``);
            shorter values are rejected because the GCM tag would be
            truncated.
    """

    model_config = _STRICT_FROZEN

    nonce: bytes = Field(min_length=NONCE_SIZE, max_length=NONCE_SIZE)
    ciphertext: bytes = Field(min_length=GCM_TAG_SIZE)

    def to_wire(self) -> bytes:
        """Serialise the blob to the canonical ``nonce || ciphertext_with_tag``."""
        return self.nonce + self.ciphertext

    @classmethod
    def from_wire(cls, payload: bytes) -> EncryptedBlob:
        """Parse the canonical wire form back into an :class:`EncryptedBlob`.

        Args:
            payload: ``nonce || ciphertext_with_tag``. Must be at least
                ``NONCE_SIZE + GCM_TAG_SIZE`` bytes.

        Returns:
            The reconstructed :class:`EncryptedBlob`.

        Raises:
            DecryptionError: If ``payload`` is shorter than the minimum
                envelope.
        """
        minimum = NONCE_SIZE + GCM_TAG_SIZE
        if len(payload) < minimum:
            raise DecryptionError(
                f"AEAD payload too short: got {len(payload)} bytes, need at least {minimum}",
            )
        return cls(nonce=payload[:NONCE_SIZE], ciphertext=payload[NONCE_SIZE:])


def encrypt_record(
    plaintext: bytes,
    *,
    key: bytes,
    associated_data: bytes | None = None,
) -> EncryptedBlob:
    """Encrypt ``plaintext`` with AES-256-GCM and return an :class:`EncryptedBlob`.

    A 12-byte random nonce is generated for every call. The substrate's
    expected throughput is far below the GCM birthday bound, so random
    nonces are safe.

    Args:
        plaintext: Bytes to encrypt. Empty plaintext is permitted; the
            tag still authenticates the empty payload.
        key: 32-byte AES-256 key. Smaller keys are rejected.
        associated_data: Optional additional authenticated data. The
            same value MUST be supplied at decrypt time; mismatch raises
            :class:`DecryptionError`.

    Returns:
        A frozen :class:`EncryptedBlob` carrying the nonce and
        ciphertext-with-tag.

    Raises:
        EncryptionError: If ``key`` is not exactly ``KEY_SIZE`` bytes,
            or if the underlying AEAD operation fails for any other
            reason.
    """
    if len(key) != KEY_SIZE:
        raise EncryptionError(
            f"AES-256-GCM key must be exactly {KEY_SIZE} bytes; got {len(key)}",
        )
    cipher = AESGCM(key)
    nonce = secrets.token_bytes(NONCE_SIZE)
    try:
        ciphertext = cipher.encrypt(nonce, plaintext, associated_data)
    except (TypeError, ValueError) as exc:
        raise EncryptionError(f"AES-256-GCM encryption failed: {exc}") from exc
    return EncryptedBlob(nonce=nonce, ciphertext=ciphertext)


def decrypt_record(
    blob: EncryptedBlob,
    *,
    key: bytes,
    associated_data: bytes | None = None,
) -> bytes:
    """Decrypt an :class:`EncryptedBlob` and verify its authentication tag.

    Args:
        blob: The encrypted record produced by :func:`encrypt_record`.
        key: The same 32-byte key used to encrypt the blob.
        associated_data: The same associated data passed at encrypt
            time. Must match exactly (including ``None`` vs ``b""``).

    Returns:
        The original plaintext bytes.

    Raises:
        DecryptionError: If the authentication tag does not verify, the
            ciphertext has been tampered with, the key does not match,
            or the associated-data binding is wrong.
        EncryptionError: If ``key`` is not exactly ``KEY_SIZE`` bytes.
    """
    if len(key) != KEY_SIZE:
        raise EncryptionError(
            f"AES-256-GCM key must be exactly {KEY_SIZE} bytes; got {len(key)}",
        )
    cipher = AESGCM(key)
    try:
        return cipher.decrypt(blob.nonce, blob.ciphertext, associated_data)
    except InvalidTag as exc:
        raise DecryptionError("AES-256-GCM tag verification failed") from exc
    except (TypeError, ValueError) as exc:
        raise DecryptionError(f"AES-256-GCM decryption failed: {exc}") from exc


def derive_key(
    *,
    key_material: bytes,
    salt: bytes,
    context: bytes,
    length: int = KEY_SIZE,
) -> bytes:
    """Derive a per-purpose key via HKDF-SHA256.

    The substrate uses HKDF to produce per-row, per-blob, and per-store
    keys from a single master key. ``context`` is the HKDF ``info``
    parameter and binds the derived key to a specific purpose; reusing
    the same master key with different ``context`` values yields
    cryptographically independent keys.

    Args:
        key_material: The IKM (input keying material). For the
            substrate this is the master key.
        salt: HKDF salt. SHOULD be a random per-store value persisted
            alongside the secret-store master key file. May be empty
            for callers that only ever derive one key from the IKM,
            but a per-purpose salt is preferred.
        context: HKDF ``info`` parameter. SHOULD be a stable
            descriptive bytestring such as ``b"cadrumo.lookup.v1"`` or
            ``b"cadrumo.envelope.payload.v1"``.
        length: Number of bytes to derive. Defaults to ``KEY_SIZE``.

    Returns:
        ``length`` derived key bytes.

    Raises:
        KeyDerivationError: If the HKDF operation fails.
    """
    if length <= 0:
        raise KeyDerivationError(f"derived-key length must be positive; got {length}")
    try:
        hkdf = HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=context)
        return hkdf.derive(key_material)
    except (TypeError, ValueError) as exc:
        raise KeyDerivationError(f"HKDF-SHA256 derivation failed: {exc}") from exc
