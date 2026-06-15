"""Crypto substrate: AEAD primitives plus encrypted SQLAlchemy column types.

Public surface for the at-rest crypto stack. Re-exports the AEAD
primitives (:func:`encrypt_record`, :func:`decrypt_record`,
:func:`derive_key`, :class:`EncryptedBlob`, and the
:data:`KEY_SIZE` / :data:`NONCE_SIZE` / :data:`GCM_TAG_SIZE`
constants) alongside the SQLAlchemy ``TypeDecorator`` set
(:class:`EncryptedString`, :class:`EncryptedBytes`,
:class:`EncryptedJSON`, :class:`HashedLookup`). Column-level
decrypt and encrypt operations resolve their key bytes through
:func:`get_active_master_key` on the active :class:`BucketSession`.
"""

from __future__ import annotations

from ._crypto import (
    GCM_TAG_SIZE,
    KEY_SIZE,
    NONCE_SIZE,
    EncryptedBlob,
    decrypt_record,
    derive_key,
    encrypt_record,
)
from ._encrypted_columns import (
    EncryptedBytes,
    EncryptedJSON,
    EncryptedPayload,
    EncryptedString,
    HashedLookup,
    secure_object_key_digest,
)

__all__ = [
    "GCM_TAG_SIZE",
    "KEY_SIZE",
    "NONCE_SIZE",
    "EncryptedBlob",
    "EncryptedBytes",
    "EncryptedJSON",
    "EncryptedPayload",
    "EncryptedString",
    "HashedLookup",
    "decrypt_record",
    "derive_key",
    "encrypt_record",
    "secure_object_key_digest",
]
