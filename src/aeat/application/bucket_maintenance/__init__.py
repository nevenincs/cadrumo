"""Application-layer bucket-maintenance lifecycle facade.

This package exposes :class:`~aeat.application.bucket_maintenance.BucketMaintenanceService`
and its Pydantic command/result contracts for profile-scoped storage
maintenance. The service composes the existing single-writer primitives
that own bucket lifecycle operations: label rename, soft tombstone plus
hard removal, sealed portable-bundle export/import, and namespace-level
browse. It contributes bucket-maintenance audit events through
:class:`~aeat.domain.buckets.BucketEventHistoryRepository` while the
inner profile primitives keep emitting their lifecycle events.

Authority: ``2026-06-03-cli-workflow-redesign-adr`` (composition
pattern). The service does not re-implement a cross-store write; it
delegates to the existing top-level user-profile re-exports:
:func:`~aeat.application.user_profile.rename_profile`,
:func:`~aeat.application.user_profile.delete_profile_with_lifecycle_span`,
:func:`~aeat.application.user_profile.remove_profile_bucket_directory`,
:func:`~aeat.application.user_profile.serialize_profile_bundle`, and
:func:`~aeat.application.user_profile.deserialize_profile_bundle`.

Export/import composition is deliberately typed at the facade boundary:
commands such as
:class:`~aeat.application.bucket_maintenance.ExportBucketCommand` and
:class:`~aeat.application.bucket_maintenance.ImportBucketCommand` produce
sealed archives with
:class:`~aeat.adapters.persistence.storage.bucket.ExportArchiveHeader`,
payloads based on
:class:`~aeat.domain.user_profile.UserProfilePortableExport`, and a
manifest digest from
:func:`~aeat.application.bucket_maintenance.compute_manifest_digest`.
This package exposes the lifecycle composition verbs ``browse``,
``delete``, ``export``, ``import``, and ``rename``. The ``search`` verb is
deferred behind its own ADR because it must route through domain
repositories instead of decrypting secure-object storage directly.

See Also:
    :mod:`aeat.application.user_profile`
        Lifecycle and portable-bundle single-writer primitives composed by this
        facade.
    :mod:`aeat.domain.buckets`
        Bucket-event records and
        :class:`~aeat.domain.buckets.BucketEventHistoryRepository` used for the
        maintenance audit trail.
    :mod:`aeat.adapters.persistence.storage.bucket`
        Bucket manifest, sealed-archive header, and archive reader/writer
        contracts used by export and import.
    :class:`BucketMaintenanceService`
        Stateless service that implements the ``browse``, ``delete``,
        ``export``, ``import``, and ``rename`` verbs.
    :func:`compute_manifest_digest`
        Archive-header integrity anchor bound into the sealed payload's AEAD
        associated data.
"""

from __future__ import annotations

from ._contracts import (
    BrowseBucketCommand,
    BrowseBucketResult,
    BucketNamespaceInventoryRow,
    DeleteBucketCommand,
    DeleteBucketResult,
    ExportBucketCommand,
    ExportBucketResult,
    ImportBucketCommand,
    ImportBucketResult,
    RenameBucketCommand,
    RenameBucketResult,
)
from ._manifest_digest import compute_manifest_digest
from ._service import BucketMaintenanceService

__all__ = [
    "BrowseBucketCommand",
    "BrowseBucketResult",
    "BucketMaintenanceService",
    "BucketNamespaceInventoryRow",
    "DeleteBucketCommand",
    "DeleteBucketResult",
    "ExportBucketCommand",
    "ExportBucketResult",
    "ImportBucketCommand",
    "ImportBucketResult",
    "RenameBucketCommand",
    "RenameBucketResult",
    "compute_manifest_digest",
]
