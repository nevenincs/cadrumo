"""Inert namespace for classification-gated encrypted blob storage.

The defining ``blob_store`` module owns :class:`EncryptedBlobStore` and its
typed :class:`BlobReference` / :class:`BlobManifest` handles. Blob layout is
classification-driven: only ``SensitivityClass.CORPUS`` payloads are stored as
plaintext corpus blobs; every other class is ciphertext with a per-blob wrapped
data-encryption key.

The defining ``materialisation`` module owns :func:`get_secret_store`, the route-canonical
:class:`adapters.persistence.storage.secret_store.SecretStore` factory. Domain
repositories and calculation sources should depend on higher-level secure-object
or repository APIs, not on blob paths directly. The package initializer exports
no symbols.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
