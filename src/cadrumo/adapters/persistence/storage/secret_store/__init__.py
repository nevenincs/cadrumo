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
records must also carry explicit expiry before write. This package
owns opaque secret persistence, not tempfile lifecycle; every current
consumer reads bytes directly rather than through a filesystem path.
"""

from __future__ import annotations

__all__ = [
]
