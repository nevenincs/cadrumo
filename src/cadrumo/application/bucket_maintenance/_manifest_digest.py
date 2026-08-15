"""Manifest-digest helper for the sealed bucket-export archive header.

Used by: :class:`~application.bucket_maintenance.BucketMaintenanceService`
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
"""

from __future__ import annotations

from pathlib import Path

from ...adapters.persistence.storage.bucket import (
    BucketPaths,
    bucket_paths,
)
from ...core import is_link_like


def validated_bucket_deletion_paths(*, root: Path, bucket_id: str) -> BucketPaths:
    """Return deletion paths only for a real, non-link bucket root.

    The check occurs before manifest reads so a symlink or Windows junction
    cannot redirect assessment into storage outside the configured bucket
    directory.
    """
    paths = bucket_paths(root, bucket_id)
    if is_link_like(paths.bucket_dir):
        raise ValueError(f"bucket deletion refuses linked bucket root: {paths.bucket_dir}")
    if not paths.bucket_dir.is_dir():
        raise FileNotFoundError(paths.bucket_dir)
    return paths


def _is_transient_bucket_file(path: Path) -> bool:
    """Return whether a name matches the fingerprint exclusion policy.

    Names ending in ``.lock``, ``.tmp``, or ``-shm`` are excluded. The
    classification does not assert that every excluded file is inherently
    non-durable.
    """
    name = path.name
    return name.endswith(".lock") or name.endswith(".tmp") or name.endswith("-shm")


__all__ = [
    "validated_bucket_deletion_paths",
]
