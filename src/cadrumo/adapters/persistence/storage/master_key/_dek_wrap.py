"""AES-256-GCM wrap and unwrap of the per-bucket data-encryption key.

The substrate wraps a freshly-generated 32-byte data-encryption key
(DEK) under a passphrase-derived 32-byte key-encryption key (KEK) using
AES-256-GCM. The wrap binds to the bucket id
through AEAD additional-authenticated-data (AAD), so the wrapped DEK
from one bucket cannot be silently swapped under another bucket's
manifest at unlock.

The on-wire shape is the typed `WrappedDek` record carrying:

- `nonce`     12 random bytes produced afresh at every wrap.
- `ciphertext` 32 bytes of AES-256-GCM ciphertext.
- `tag`       16 bytes of AES-256-GCM authentication tag.

The actual AEAD operation routes through the canonical
:func:`~adapters.persistence.storage.crypto.encrypt_record` /
:func:`~adapters.persistence.storage.crypto.decrypt_record` primitives
(the same AES-256-GCM construction the blob store and the schema-version
envelope use), rather than calling ``cryptography``'s ``AESGCM`` directly.
Only the three-field ``WrappedDek`` wire shape is specific to this module:
``encrypt_record``'s ``EncryptedBlob.ciphertext`` (``ciphertext_with_tag``)
is split into ``WrappedDek.ciphertext``/``WrappedDek.tag`` at the 32-byte
boundary on wrap, and rejoined the same way on unwrap, so the on-disk
``WrappedDek`` shape is unchanged and every previously-wrapped DEK remains
readable.

`unwrap_dek` raises a typed storage `DecryptionError` on AEAD failure.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..crypto import EncryptedBlob, decrypt_record, encrypt_record
from ..errors import DecryptionError, EncryptionError
from ._bucket_identity import canonical_bucket_id

_NONCE_BYTES = 12
_TAG_BYTES = 16
_DEK_BYTES = 32
_KEK_BYTES = 32
_STORAGE_DECRYPTION_MESSAGE_KEY = "errors.integrity.integrity_storage_decryption"
_STORAGE_ENCRYPTION_MESSAGE_KEY = "errors.integrity.integrity_storage_encryption"


class WrappedDek(BaseModel):
    """Frozen AES-256-GCM envelope around one bucket's data-encryption key."""

    model_config = _STRICT_FROZEN

    nonce: bytes = Field(min_length=_NONCE_BYTES, max_length=_NONCE_BYTES)
    ciphertext: bytes = Field(min_length=_DEK_BYTES, max_length=_DEK_BYTES)
    tag: bytes = Field(min_length=_TAG_BYTES, max_length=_TAG_BYTES)


def _associated_data(bucket_id: str) -> bytes:
    """Compose the AEAD additional-authenticated-data for one bucket.

    The identity is canonicalized first, so the AAD this composes is the
    storage layer's spelling of the bucket rather than the caller's. Two
    spellings of one bucket therefore wrap and unwrap interchangeably, and an
    identity the storage layer would refuse never reaches AES-GCM at all.
    """
    try:
        canonical = canonical_bucket_id(bucket_id)
    except ValueError as exc:
        raise _encryption_error("bucket_id must be a canonical bucket identity") from exc
    return f"cadrumo.dek-wrap.v1:{canonical}".encode()


def _encryption_error(message: str) -> EncryptionError:
    return EncryptionError(message, translated_message=_STORAGE_ENCRYPTION_MESSAGE_KEY)


def _decryption_error(message: str) -> DecryptionError:
    return DecryptionError(message, translated_message=_STORAGE_DECRYPTION_MESSAGE_KEY)


def wrap_dek(*, kek: bytes, dek: bytes, bucket_id: str) -> WrappedDek:
    """Wrap `dek` under `kek` using AES-256-GCM keyed to `bucket_id`.

    Args:
        kek: 32-byte key-encryption key derived from the operator's
            passphrase via Argon2id.
        dek: 32-byte data-encryption key minted afresh at enrollment.
        bucket_id: Bucket identifier, canonicalized through
            :data:`~core.identity.BucketId` and bound into the AEAD AAD so
            the wrapped DEK cannot be re-mounted under a different bucket.

    Returns:
        A frozen :class:`WrappedDek` record carrying nonce, ciphertext, and
        tag.

    Raises:
        EncryptionError: If `kek` or `dek` is not 32 bytes, or `bucket_id`
            is not a canonical bucket identity.
    """
    if len(kek) != _KEK_BYTES:
        raise _encryption_error(f"kek must be exactly {_KEK_BYTES} bytes")
    if len(dek) != _DEK_BYTES:
        raise _encryption_error(f"dek must be exactly {_DEK_BYTES} bytes")

    aad = _associated_data(bucket_id)
    try:
        blob = encrypt_record(dek, key=kek, associated_data=aad)
    except EncryptionError as exc:
        # Re-raise the SAME exception object (preserving its __cause__ chain)
        # with this module's translated_message, rather than wrapping it in a
        # new EncryptionError -- a caller inspecting __cause__ sees the real
        # underlying failure either way.
        exc.translated_message = _STORAGE_ENCRYPTION_MESSAGE_KEY
        raise
    ciphertext, tag = blob.ciphertext[:_DEK_BYTES], blob.ciphertext[_DEK_BYTES:]
    return WrappedDek(nonce=blob.nonce, ciphertext=ciphertext, tag=tag)


def unwrap_dek(*, kek: bytes, wrapped: WrappedDek, bucket_id: str) -> bytes:
    """Recover the 32-byte DEK from `wrapped` under `kek` and `bucket_id`.

    Args:
        kek: 32-byte key-encryption key.
        wrapped: Typed envelope produced by `wrap_dek`.
        bucket_id: Bucket identifier; must name the same bucket bound at
            wrap time, in any spelling the canonical
            :data:`~core.identity.BucketId` normalizes to that value.

    Returns:
        The 32-byte data-encryption key.

    Raises:
        EncryptionError: When ``kek`` is not 32 bytes or ``bucket_id`` is not
            a canonical bucket identity.
        DecryptionError: When AEAD tag verification fails.
    """
    if len(kek) != _KEK_BYTES:
        raise _encryption_error(f"kek must be exactly {_KEK_BYTES} bytes")

    aad = _associated_data(bucket_id)
    blob = EncryptedBlob(nonce=wrapped.nonce, ciphertext=wrapped.ciphertext + wrapped.tag)
    try:
        return decrypt_record(blob, key=kek, associated_data=aad)
    except DecryptionError as exc:
        # Same re-raise-in-place rationale as wrap_dek: preserves __cause__
        # (e.g. the underlying cryptography.exceptions.InvalidTag) exactly.
        exc.translated_message = _STORAGE_DECRYPTION_MESSAGE_KEY
        raise


__all__ = ["WrappedDek", "unwrap_dek", "wrap_dek"]
