"""Manifest-digest helper for the sealed bucket-export archive header.

Used by: :class:`~aeat.application.bucket_maintenance.BucketMaintenanceService`
to generate export archive digests.

The ``ExportArchiveHeader.manifest_digest`` field carries a
SHA-256 hex digest over the serialised :class:`BucketManifest` JSON
bytes. The digest is the export's integrity anchor: it is bound into the
sealed payload's AEAD associated data (``_archive_associated_data`` in
:mod:`~._service`), so tampering with the header digest makes the
payload's AEAD tag verification fail and the import is refused at
decryption.

The digest is NOT recomputed-and-compared against the freshly-provisioned
manifest on the import host. The manifest carries host-specific lifecycle
timestamps (``created_at``, ``last_unlocked_at``) that legitimately differ
between the exporting and importing hosts, so a literal recompute could never
match; the AEAD binding is the authoritative integrity mechanism.

Authority: ``2026-06-03-bucket-sealed-archive-adr``.
"""

from __future__ import annotations

from ...adapters.persistence.storage.bucket import BucketManifest
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import sha256_hex


def compute_manifest_digest(manifest: BucketManifest) -> str:
    """Return the SHA-256 hex digest of ``manifest`` serialised to JSON.

    Uses JSON rather than TOML because pydantic's ``model_dump_json``
    provides a deterministic byte-stable serialisation that does not
    depend on the hand-rolled TOML emitter. The digest is the
    archive-header integrity anchor: it is bound into the sealed
    payload's AEAD associated data, so a tampered digest fails the
    payload's authentication tag and the import is refused at
    decryption (it is not recomputed-and-compared against the import-
    host manifest, whose lifecycle timestamps legitimately differ).

    The output is a 64-character lowercase hex string matching the
    ``manifest_digest`` field constraint on
    :class:`~aeat.adapters.persistence.storage.bucket.ExportArchiveHeader`.
    """
    serialised = manifest.model_dump_json().encode(UTF_8_ENCODING)
    return sha256_hex(serialised)


__all__ = ["compute_manifest_digest"]
