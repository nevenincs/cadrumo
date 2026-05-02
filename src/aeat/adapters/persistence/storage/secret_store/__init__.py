"""Secret-store substrate: keyed secret repository on top of the blob store.

Public surface for the keyed-secret persistence layer. Exposes the
typed :class:`SecretRecord` payload and the :class:`SecretStore`
repository that wraps records in a :class:`Envelope`, persists them
via :class:`aeat.adapters.persistence.storage.blob_store.EncryptedBlobStore`,
and indexes them by HMAC-SHA256 digest of the natural key.
"""

from __future__ import annotations

from ._secret_store import SecretRecord, SecretStore

__all__ = [
    "SecretRecord",
    "SecretStore",
]
