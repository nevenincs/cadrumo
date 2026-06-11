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

`unwrap_dek` raises a typed storage `DecryptionError` on AEAD failure.
"""

from __future__ import annotations

import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, Field

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ..errors import DecryptionError, EncryptionError

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
    """Compose the AEAD additional-authenticated-data for one bucket."""
    if not bucket_id:
        raise _encryption_error("bucket_id must be non-empty")
    return f"aeat.dek-wrap.v1:{bucket_id}".encode(_UTF_8_ENCODING)


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
        bucket_id: Non-empty bucket identifier; bound into the AEAD AAD
            so the wrapped DEK cannot be re-mounted under a different
            bucket.

    Returns:
        A frozen :class:`WrappedDek` record carrying nonce, ciphertext, and
        tag.

    Raises:
        EncryptionError: If `kek` or `dek` is not 32 bytes, or `bucket_id`
            is empty.
    """
    if len(kek) != _KEK_BYTES:
        raise _encryption_error(f"kek must be exactly {_KEK_BYTES} bytes")
    if len(dek) != _DEK_BYTES:
        raise _encryption_error(f"dek must be exactly {_DEK_BYTES} bytes")

    nonce = secrets.token_bytes(_NONCE_BYTES)
    aad = _associated_data(bucket_id)
    try:
        cipher_with_tag = AESGCM(kek).encrypt(nonce, dek, aad)
    except (TypeError, ValueError) as exc:
        raise _encryption_error("DEK wrap failed") from exc
    ciphertext, tag = cipher_with_tag[:_DEK_BYTES], cipher_with_tag[_DEK_BYTES:]
    return WrappedDek(nonce=nonce, ciphertext=ciphertext, tag=tag)


def unwrap_dek(*, kek: bytes, wrapped: WrappedDek, bucket_id: str) -> bytes:
    """Recover the 32-byte DEK from `wrapped` under `kek` and `bucket_id`.

    Args:
        kek: 32-byte key-encryption key.
        wrapped: Typed envelope produced by `wrap_dek`.
        bucket_id: Non-empty bucket identifier; must match the value
            bound at wrap time.

    Returns:
        The 32-byte data-encryption key.

    Raises:
        EncryptionError: When ``kek`` is not 32 bytes or ``bucket_id`` is empty.
        DecryptionError: When AEAD tag verification fails.
    """
    if len(kek) != _KEK_BYTES:
        raise _encryption_error(f"kek must be exactly {_KEK_BYTES} bytes")

    aad = _associated_data(bucket_id)
    cipher_with_tag = wrapped.ciphertext + wrapped.tag
    try:
        return AESGCM(kek).decrypt(wrapped.nonce, cipher_with_tag, aad)
    except InvalidTag as exc:
        raise _decryption_error("DEK unwrap tag verification failed") from exc
    except (TypeError, ValueError) as exc:
        raise _decryption_error("DEK unwrap failed") from exc


__all__ = ["WrappedDek", "unwrap_dek", "wrap_dek"]
