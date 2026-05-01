"""Crypto substrate: AEAD primitives + EncryptedString/Bytes/JSON columns.

Bucket boundary established by audit-4 in the aeat-restructure ADR.
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
