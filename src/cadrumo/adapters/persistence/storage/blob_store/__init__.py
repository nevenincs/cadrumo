"""Blob-store substrate for classification-gated encrypted blobs.

Public surface for the content-addressed :class:`EncryptedBlobStore` and its
typed :class:`BlobReference` / :class:`BlobManifest` handles. Blob layout is
classification-driven: only ``SensitivityClass.CORPUS`` payloads are stored as
plaintext corpus blobs; every other class is ciphertext with a per-blob wrapped
data-encryption key.

This package also exposes :func:`get_secret_store`, the route-canonical
:class:`adapters.persistence.storage.secret_store.SecretStore` factory. Domain
repositories and calculation sources should depend on higher-level secure-object
or repository APIs, not on blob paths directly.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
