"""Manifest-digest helper for the sealed bucket-export archive header.

The ``ExportArchiveHeader.manifest_digest`` field carries a
SHA-256 hex digest over the serialised :class:`BucketManifest` TOML
bytes. The importer cross-checks this digest against the
freshly-provisioned manifest as a pre-flight integrity gate: a
mismatched digest means the source archive was generated from a
different bucket-manifest state than the one the importer is about
to write, and the import refuses.

Authority: ``2026-06-03-bucket-sealed-archive-adr``.
"""

from __future__ import annotations

import hashlib

from ...adapters.persistence.storage.bucket._manifest import BucketManifest


def compute_manifest_digest(manifest: BucketManifest) -> str:
    """Return the SHA-256 hex digest of ``manifest`` serialised to JSON.

    Uses JSON rather than TOML because pydantic's ``model_dump_json``
    provides a deterministic byte-stable serialisation that does not
    depend on the hand-rolled TOML emitter. The digest is the
    archive-header integrity anchor; the import side recomputes it
    from the freshly-imported manifest and refuses on mismatch.

    The output is a 64-character lowercase hex string matching the
    :class:`ExportArchiveHeader.manifest_digest` field constraint.
    """
    serialised = manifest.model_dump_json().encode("utf-8")
    return hashlib.sha256(serialised).hexdigest()


__all__ = ["compute_manifest_digest"]
