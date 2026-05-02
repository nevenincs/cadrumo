"""Crypto substrate: AEAD primitives plus encrypted SQLAlchemy column types.

Public surface for the at-rest crypto stack. Re-exports the AEAD
primitives (:func:`encrypt_record`, :func:`decrypt_record`,
:func:`derive_key`, :class:`EncryptedBlob`, and the
:data:`KEY_SIZE` / :data:`NONCE_SIZE` / :data:`GCM_TAG_SIZE`
constants) alongside the SQLAlchemy ``TypeDecorator`` set
(:class:`EncryptedString`, :class:`EncryptedBytes`,
:class:`EncryptedJSON`, :class:`HashedLookup`) and the
:func:`override_master_key_provider` test helper.
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
    EncryptedString,
    HashedLookup,
    override_master_key_provider,
)

__all__ = [
    "GCM_TAG_SIZE",
    "KEY_SIZE",
    "NONCE_SIZE",
    "EncryptedBlob",
    "EncryptedBytes",
    "EncryptedJSON",
    "EncryptedString",
    "HashedLookup",
    "decrypt_record",
    "derive_key",
    "encrypt_record",
    "override_master_key_provider",
]
