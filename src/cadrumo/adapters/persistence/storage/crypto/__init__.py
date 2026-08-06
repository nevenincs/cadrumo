"""Crypto substrate: AEAD primitives plus encrypted SQLAlchemy helpers.

Public surface for the at-rest crypto stack. Re-exports the AEAD
primitives (:func:`encrypt_record`, :func:`decrypt_record`,
:func:`derive_key`, :class:`EncryptedBlob`, and the
:data:`KEY_SIZE` / :data:`NONCE_SIZE` / :data:`GCM_TAG_SIZE`
constants) alongside the SQLAlchemy ``TypeDecorator`` set
(:class:`EncryptedString`, :class:`EncryptedBytes`,
:class:`EncryptedJSON`, :class:`HashedLookup`), the
:class:`EncryptedPayload` JSON guard, and
:func:`secure_object_key_digest` for secure-object row AAD binding.

Column-level decrypt and encrypt operations resolve key bytes through
:func:`adapters.persistence.storage.master_key._active_session.get_active_master_key`
on the active
:class:`adapters.persistence.storage.master_key._bucket_session.BucketSession`.
This facade only re-exports crypto objects; it does not acquire key
material or activate a session at import time.
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
    decrypt_encrypted_bytes_column,
    decrypt_secure_object_payload,
    encrypt_secure_object_payload,
    hkdf_hmac_digest,
    secure_object_key_digest,
    secure_object_payload_aad,
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
    "decrypt_encrypted_bytes_column",
    "decrypt_record",
    "decrypt_secure_object_payload",
    "derive_key",
    "encrypt_record",
    "encrypt_secure_object_payload",
    "hkdf_hmac_digest",
    "secure_object_key_digest",
    "secure_object_payload_aad",
]
