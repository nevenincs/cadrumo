"""Blob-store substrate: classification-gated content-addressed encrypted blobs.

Bucket boundary established by audit-4 in the aeat-restructure ADR.
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
