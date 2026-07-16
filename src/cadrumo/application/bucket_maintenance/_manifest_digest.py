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
    BucketManifest,
    BucketPaths,
    bucket_paths,
    read_manifest,
)
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import content_hash_hex, hash_file, sha256_hex
from ._contracts import BucketDeletionFingerprint


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
    :class:`~adapters.persistence.storage.bucket.ExportArchiveHeader`.
    """
    serialised = manifest.model_dump_json().encode(UTF_8_ENCODING)
    return sha256_hex(serialised)


def compute_bucket_deletion_fingerprint(
    *,
    root: Path,
    bucket_id: str,
) -> BucketDeletionFingerprint:
    """Compute a structured fingerprint of deletion-relevant bucket contents.

    Regular files are visited recursively in relative-path order. The fold
    includes the bucket identifier, structured manifest digest, each relative
    path, file-content hash, and byte count. Files whose names end in
    ``.lock``, ``.tmp``, or ``-shm`` are excluded.

    The function refuses a missing bucket, a link-like bucket root, links or
    junctions below that root, and buckets containing no included files. It
    acquires no lock or transactional snapshot, so the caller must keep the
    target stable throughout the read.
    """
    paths = validated_bucket_deletion_paths(root=root, bucket_id=bucket_id)
    manifest = read_manifest(paths)
    entries: list[dict[str, str | int]] = []
    total_bytes = 0
    for path in sorted(paths.bucket_dir.rglob("*"), key=lambda candidate: candidate.as_posix()):
        if path.is_symlink() or path.is_junction():
            raise ValueError(f"bucket deletion fingerprint refuses linked path: {path}")
        if not path.is_file() or _is_transient_bucket_file(path):
            continue
        digest, byte_count = hash_file(path)
        entries.append(
            {
                "path": path.relative_to(paths.bucket_dir).as_posix(),
                "sha256": digest,
                "bytes": byte_count,
            },
        )
        total_bytes += byte_count

    if not entries:
        raise ValueError(f"bucket deletion fingerprint found no durable files for {bucket_id}")
    manifest_digest = compute_manifest_digest(manifest)
    digest = content_hash_hex(
        {
            "schema_version": 1,
            "bucket_id": bucket_id,
            "manifest_digest": manifest_digest,
            "files": entries,
        },
    )
    return BucketDeletionFingerprint(
        digest=digest,
        manifest_digest=manifest_digest,
        file_count=len(entries),
        total_bytes=total_bytes,
    )


def validated_bucket_deletion_paths(*, root: Path, bucket_id: str) -> BucketPaths:
    """Return deletion paths only for a real, non-link bucket root.

    The check occurs before manifest reads so a symlink or Windows junction
    cannot redirect assessment into storage outside the configured bucket
    directory.
    """
    paths = bucket_paths(root, bucket_id)
    if paths.bucket_dir.is_symlink() or paths.bucket_dir.is_junction():
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
    return (
        name.endswith(".lock")
        or name.endswith(".tmp")
        or name.endswith("-shm")
    )


__all__ = [
    "compute_bucket_deletion_fingerprint",
    "compute_manifest_digest",
    "validated_bucket_deletion_paths",
]
