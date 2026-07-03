"""Secret-store substrate: keyed secret records over encrypted blobs.

Public surface for the keyed-secret persistence layer. Exposes the
typed :class:`SecretRecord` payload and the :class:`SecretStore`
repository that wraps records in
:class:`adapters.persistence.storage.envelope.Envelope`, persists
them via
:class:`adapters.persistence.storage.blob_store.EncryptedBlobStore`,
and indexes natural keys by HMAC-SHA256 lookup digest.

The index is deliberately not a plaintext inventory: secret keys,
payload bytes, and blob digests are kept out of user-facing miss,
collision, corruption, and cleanup messages. SECRET and SESSION
records must also carry explicit expiry before write. Consumers that
need a filesystem path for an SDK should use
:func:`adapters.persistence.storage.blob_store.materialise_secret`
or :func:`adapters.persistence.storage.blob_store.export_to_temp_path`;
this package owns opaque secret persistence, not tempfile lifecycle.
"""

from __future__ import annotations

from ._secret_store import SecretRecord, SecretStore

__all__ = [
    "SecretRecord",
    "SecretStore",
]
