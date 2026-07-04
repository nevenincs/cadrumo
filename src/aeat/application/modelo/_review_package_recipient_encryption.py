"""Encrypt-for-recipient transport for review packages (X25519 ECIES).

This module adds a CONFIDENTIALITY layer on top of the review-package
checksum-integrity (:mod:`aeat.application.modelo._review_package`) and
authenticity (:mod:`aeat.application.modelo._review_package_signing`,
:mod:`aeat.application.modelo._review_package_counter_sign`) layers: a
review package sealed with :func:`encrypt_review_package_for_recipient`
can be opened only by the holder of the matching X25519 private key --
unlike ``sign``/``counter-sign``, which leave the archive itself in
plaintext ZIP form.

Construction (ECIES over the primitives already vetted and already
shipped by this project -- no new dependency, see
``2026-07-04-recipient-encryption-adr``):

1. A fresh EPHEMERAL X25519 keypair is generated for this one message
   (``cryptography.hazmat.primitives.asymmetric.x25519.X25519PrivateKey.generate()``).
2. ECDH is performed between the ephemeral private key and the
   recipient's long-term public key
   (:class:`~aeat.application.modelo.RecipientFingerprintRecord`),
   producing a 32-byte shared secret.
3. The shared secret is NEVER used directly as an AEAD key. It is run
   through :func:`~aeat.adapters.persistence.storage.crypto.derive_key`
   (HKDF-SHA256), with the HKDF ``salt`` set to the ephemeral public key
   and the ``context`` (HKDF ``info``) bound to a fixed domain-separation
   string PLUS the recipient's public key -- so a derived key can never
   be reused across a different ephemeral sender key or a different
   recipient.
4. The package bytes are AEAD-encrypted via
   :func:`~aeat.adapters.persistence.storage.crypto.encrypt_record`
   (AES-256-GCM), with the recipient's public key bound into the
   associated data -- so a ciphertext cannot be silently re-targeted at
   a different recipient's key without the AEAD tag failing to verify.
5. The returned :class:`RecipientEncryptedPackage` envelope carries the
   ephemeral public key, the recipient's public key, and the AEAD wire
   bytes -- everything the recipient needs to reverse the ECDH and
   decrypt, and nothing that identifies the sender (no long-term sender
   keypair is required or persisted for this direction).

Key custody (``sensitive-financial-data-secure-storage-only``): the
review-package bytes are read into memory, encrypted in memory, and the
CIPHERTEXT envelope is the only artefact this module returns to the
caller; the caller is responsible for writing the envelope bytes to its
requested output path. Nothing is staged to a temp file. The recipient's
public key carries no secrecy requirement (it is looked up from
:class:`~aeat.application.modelo.RecipientFingerprintRegistryRepository`);
the ephemeral sender private key exists only for the duration of one
call and is never persisted.

See Also:
    :mod:`aeat.application.modelo._review_package_recipient_registry`
        Where a recipient's trusted public key is registered and looked
        up before calling this module.
    :mod:`aeat.application.modelo._review_package`
        Builds and integrity-verifies the review package this module
        encrypts.
"""

from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors import AeatError

#: Wire-format version of the recipient-encryption envelope. Bumped when
#: the envelope schema changes shape.
_RECIPIENT_ENCRYPTION_ENVELOPE_VERSION = 1

#: HKDF domain-separation context. Distinct from any other HKDF context
#: string used elsewhere in the codebase (e.g. secure-object row keys,
#: DEK wrapping) so a key derived here can never collide with a key
#: derived for an unrelated purpose even if the same shared secret were
#: (incorrectly) reused.
_HKDF_CONTEXT_PREFIX = b"aeat.review_package.recipient_encryption.v1"

_HEX_PATTERN_64 = r"^[0-9a-f]{64}$"


class RecipientEncryptionError(AeatError):
    """Base error for review-package recipient-encryption failures."""


class RecipientDecryptionError(RecipientEncryptionError):
    """Raised when a recipient-encrypted package fails to decrypt.

    Covers both cryptographic AEAD-tag failure (tampered ciphertext or
    wrong private key) and a mismatched recipient public key (the
    caller's private key does not correspond to the envelope's declared
    recipient public key) -- never distinguished further, so an attacker
    cannot use error content to learn which check failed.
    """


class RecipientEncryptedPackage(BaseModel):
    """Wire envelope for a review package encrypted for one recipient.

    ``ephemeral_public_key_hex`` and ``recipient_public_key_hex`` are
    both raw 32-byte X25519 public keys, hex-encoded. ``ciphertext``
    is the AEAD wire form (``nonce || ciphertext_with_tag``) produced by
    :func:`~aeat.adapters.persistence.storage.crypto.encrypt_record`.
    """

    model_config = _STRICT_FROZEN

    envelope_version: int = Field(default=_RECIPIENT_ENCRYPTION_ENVELOPE_VERSION, ge=1)
    ephemeral_public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    recipient_public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    ciphertext: bytes = Field(min_length=1)


def _hkdf_context(recipient_public_key_hex: str) -> bytes:
    """Return the HKDF ``info`` bytes binding a derived key to one recipient.

    Domain-separates the derived AEAD key from any other HKDF use in the
    codebase, and from a derivation for a *different* recipient's public
    key, so the same ephemeral keypair could never (even by caller
    error) yield the same derived key for two different recipients.
    """
    return _HKDF_CONTEXT_PREFIX + b":" + recipient_public_key_hex.encode("ascii")


def _associated_data(recipient_public_key_hex: str) -> bytes:
    """Return the AEAD associated data binding ciphertext to one recipient.

    Any attempt to present this ciphertext as encrypted for a different
    recipient's public key fails AEAD authentication, because the
    associated data would no longer match.
    """
    return b"aeat.review_package.recipient:" + recipient_public_key_hex.encode("ascii")


def encrypt_review_package_for_recipient(
    package_bytes: bytes,
    *,
    recipient_public_key_hex: str,
) -> RecipientEncryptedPackage:
    """Seal ``package_bytes`` so only ``recipient_public_key_hex``'s holder can open it.

    Generates a fresh ephemeral X25519 keypair, performs ECDH against the
    recipient's public key, derives a per-message AES-256-GCM key via
    HKDF-SHA256, and encrypts. See the module docstring for the full
    construction. Never writes ``package_bytes`` or the derived key to
    disk; the caller is responsible for persisting the returned
    envelope's bytes.

    Args:
        package_bytes: The plaintext review-package archive bytes to
            seal (read into memory by the caller; this function performs
            no filesystem I/O).
        recipient_public_key_hex: The recipient's raw 32-byte X25519
            public key, hex-encoded (see
            :class:`~aeat.application.modelo.RecipientFingerprintRecord`).

    Raises:
        RecipientEncryptionError: If ``recipient_public_key_hex`` is not
            a well-formed X25519 public key.
    """
    from ...adapters.persistence.storage.crypto import derive_key, encrypt_record

    try:
        recipient_public_key = X25519PublicKey.from_public_bytes(bytes.fromhex(recipient_public_key_hex))
    except (ValueError, TypeError) as exc:
        raise RecipientEncryptionError(
            "recipient_public_key_hex is not a well-formed X25519 public key",
            translated_message="application.modelo.errors.recipient_encryption_invalid_key",
        ) from exc

    ephemeral_private_key = X25519PrivateKey.generate()
    ephemeral_public_key = ephemeral_private_key.public_key()
    ephemeral_public_key_hex = ephemeral_public_key.public_bytes_raw().hex()

    shared_secret = ephemeral_private_key.exchange(recipient_public_key)
    derived_key = derive_key(
        key_material=shared_secret,
        salt=ephemeral_public_key.public_bytes_raw(),
        context=_hkdf_context(recipient_public_key_hex),
    )
    encrypted = encrypt_record(
        package_bytes,
        key=derived_key,
        associated_data=_associated_data(recipient_public_key_hex),
    )

    return RecipientEncryptedPackage(
        ephemeral_public_key_hex=ephemeral_public_key_hex,
        recipient_public_key_hex=recipient_public_key_hex,
        ciphertext=encrypted.to_wire(),
    )


def decrypt_review_package_for_recipient(
    envelope: RecipientEncryptedPackage,
    *,
    recipient_private_key: X25519PrivateKey,
) -> bytes:
    """Reverse :func:`encrypt_review_package_for_recipient` and return the package bytes.

    Reconstructs the same derived AEAD key by performing ECDH between
    ``recipient_private_key`` and the envelope's ephemeral public key,
    then decrypts and authenticates. A wrong ``recipient_private_key`` (or
    any tampering of ``envelope.ciphertext`` or the declared public keys)
    fails AEAD authentication.

    Args:
        envelope: The :class:`RecipientEncryptedPackage` produced by
            :func:`encrypt_review_package_for_recipient`.
        recipient_private_key: The recipient's own X25519 private key.

    Returns:
        The original plaintext review-package archive bytes.

    Raises:
        RecipientDecryptionError: If ``recipient_private_key`` does not
            match the envelope's declared recipient public key, or the
            ciphertext fails AEAD authentication for any reason
            (tampering, corruption, wrong key).
    """
    from ...adapters.persistence.storage import DecryptionError
    from ...adapters.persistence.storage.crypto import EncryptedBlob, decrypt_record, derive_key

    recipient_public_key_hex = recipient_private_key.public_key().public_bytes_raw().hex()
    if recipient_public_key_hex != envelope.recipient_public_key_hex:
        raise RecipientDecryptionError(
            "recipient_private_key does not match the envelope's declared recipient public key",
            translated_message="application.modelo.errors.recipient_decryption_failed",
        )

    ephemeral_public_key = X25519PublicKey.from_public_bytes(bytes.fromhex(envelope.ephemeral_public_key_hex))
    shared_secret = recipient_private_key.exchange(ephemeral_public_key)
    derived_key = derive_key(
        key_material=shared_secret,
        salt=bytes.fromhex(envelope.ephemeral_public_key_hex),
        context=_hkdf_context(envelope.recipient_public_key_hex),
    )
    try:
        return decrypt_record(
            EncryptedBlob.from_wire(envelope.ciphertext),
            key=derived_key,
            associated_data=_associated_data(envelope.recipient_public_key_hex),
        )
    except DecryptionError as exc:
        raise RecipientDecryptionError(
            "recipient-encrypted package failed AEAD authentication",
            translated_message="application.modelo.errors.recipient_decryption_failed",
        ) from exc


__all__ = [
    "RecipientDecryptionError",
    "RecipientEncryptedPackage",
    "RecipientEncryptionError",
    "decrypt_review_package_for_recipient",
    "encrypt_review_package_for_recipient",
]
