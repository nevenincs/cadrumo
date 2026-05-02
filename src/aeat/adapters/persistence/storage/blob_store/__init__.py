"""Blob-store substrate: classification-gated content-addressed encrypted blobs.

Public surface for the encrypted blob substrate. Exposes the
:class:`EncryptedBlobStore` repository, the typed :class:`BlobReference`
and :class:`BlobManifest` records, and the secret-materialisation
helpers (:func:`materialise_secret`, :func:`export_to_temp_path`,
:func:`get_secret_store`, :func:`override_secret_store`) consumed by
adapters that must hand a plaintext secret to a third-party SDK
through the filesystem.
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
    override_secret_store,
)

__all__ = [
    "BlobManifest",
    "BlobReference",
    "EncryptedBlobStore",
    "export_to_temp_path",
    "get_secret_store",
    "materialise_secret",
    "override_secret_store",
]
