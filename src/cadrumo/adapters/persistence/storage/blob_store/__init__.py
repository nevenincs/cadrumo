"""Blob-store substrate for classification-gated encrypted blobs.

Public surface for the content-addressed :class:`EncryptedBlobStore` and its
typed :class:`BlobReference` / :class:`BlobManifest` handles. Blob layout is
classification-driven: only ``SensitivityClass.CORPUS`` payloads are stored as
plaintext corpus blobs; every other class is ciphertext with a per-blob wrapped
data-encryption key.

This package also exposes the path-shaped secret bridge used by SDKs that
cannot consume in-memory bytes. :func:`materialise_secret` and
:func:`export_to_temp_path` read encrypted records through
:class:`adapters.persistence.storage.secret_store.SecretStore`, write a
short-lived private tempfile, and leave cleanup ownership explicit. Domain
repositories and calculation sources should depend on higher-level secure-object
or repository APIs, not on blob paths directly.
"""

from __future__ import annotations

from ._blob_store import (
    BlobManifest,
    BlobReference,
    EncryptedBlobStore,
)
from ._materialisation import (
    export_to_temp_path,
    get_secret_store,
    materialise_secret,
)

__all__ = [
    "BlobManifest",
    "BlobReference",
    "EncryptedBlobStore",
    "export_to_temp_path",
    "get_secret_store",
    "materialise_secret",
]
