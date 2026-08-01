"""Application-layer bucket-maintenance lifecycle facade.

This package exposes :class:`BucketMaintenanceService`
and its Pydantic command/result contracts for profile-scoped storage
maintenance. The service composes the existing single-writer primitives
that own bucket lifecycle operations: label rename, soft tombstone plus
hard removal, sealed portable-bundle export/import, and namespace-level
browse. It contributes bucket-maintenance audit events through
:class:`domain.buckets.BucketEventHistoryRepository` while the
inner profile primitives keep emitting their lifecycle events.

The service does not re-implement a cross-store write; it
delegates to the existing top-level user-profile re-exports:
:func:`application.user_profile.rename_profile`,
:func:`application.user_profile.delete_profile_with_lifecycle_span`,
:func:`application.user_profile.remove_profile_bucket_directory`,
:func:`application.user_profile.serialize_profile_bundle`, and
:func:`application.user_profile.deserialize_profile_bundle`.

Export/import composition is deliberately typed at the facade boundary:
commands such as
:class:`ExportBucketCommand` and
:class:`ImportBucketCommand` produce
sealed archives with
:class:`adapters.persistence.storage.bucket.ExportArchiveHeader`,
payloads based on
:class:`domain.user_profile.UserProfilePortableExport`, and a
manifest digest from
:func:`compute_manifest_digest`.
Sealed exports use
:class:`adapters.persistence.storage.StorageCustodyProfile.FULL`:
the portable payload carries the typed profile/work/ledger/calculation/filing
categories plus the registry-derived carried secure-object namespaces. Carried
rows are addressed by their natural object keys, not the stored HMAC lookup
digests, so import re-saves them through the recipient bucket's
:class:`adapters.persistence.storage.SecureObjectRepository` and
re-encrypts under that bucket's DEK.
This package exposes the lifecycle composition verbs ``archive``,
``browse``, ``delete``, ``disk_usage``, ``export``, ``import``, ``inspect``,
``rename``, and ``restore``. The ``search`` verb is deferred; it must route
through domain repositories instead of decrypting secure-object storage
directly.

:class:`AssessBucketDeletionCommand`,
:class:`BucketDeletionAssessment`, and
:class:`BucketDeletionFingerprint` expose target-scoped, read-only foundation
contracts for composing deletion safely. They do not implement reset
orchestration.

:meth:`BucketMaintenanceService.disk_usage` measures a bucket's on-disk
footprint by summing regular-file byte sizes under its fixed directory
layout (:func:`adapters.persistence.storage.bucket.bucket_paths`); it reads
only filesystem metadata, never decrypted content, so it can measure a
non-active (even archived) bucket without opening a storage session.

:func:`create_sandbox` and :func:`discard_sandbox` expose a discardable
experiment-workspace lifecycle over the same primitives: a sandbox is an
ordinary bucket labelled with the reserved :data:`SANDBOX_LABEL_PREFIX`,
created (optionally forked from a live profile's facts) through the
canonical atomic-create span and discarded through this package's
:meth:`BucketMaintenanceService.delete`. :func:`preview_discard_sandbox`
reports what a discard would remove without removing it, and
:func:`list_sandboxes` enumerates every live sandbox for bulk operations
such as ``sandbox prune``. :func:`archive_sandbox` and
:func:`restore_sandbox` expose a reversible-dormancy alternative to
discard: :meth:`BucketMaintenanceService.archive` soft-tombstones the
sandbox without removing its directory, and
:meth:`BucketMaintenanceService.restore` reactivates it. :func:`merge_sandbox`
promotes a :class:`SandboxMergeScope` (``ledger``, ``modelo``, or ``all``)
from a sandbox into a target profile bucket by composing the same typed
catalogue repositories and domain upsert primitives (``upsert_work_unit``,
``upsert_calculation_revision``, ``upsert_filing_record``) the
portable-bundle import path already uses for those categories, so a
repeated merge of unchanged sandbox content is an idempotent no-op write.

See Also:
    :mod:`application.user_profile`
        Lifecycle and portable-bundle single-writer primitives composed by this
        facade.
    :mod:`domain.buckets`
        Bucket-event records and
        :class:`domain.buckets.BucketEventHistoryRepository` used for the
        maintenance audit trail.
    :mod:`adapters.persistence.storage.bucket`
        Bucket manifest, sealed-archive header, and archive reader/writer
        contracts used by export and import.
    :class:`BucketMaintenanceService`
        Stateless service that implements the ``browse``, ``delete``,
        ``export``, ``import``, ``inspect``, and ``rename`` verbs.
    :func:`compute_manifest_digest`
        Archive-header integrity anchor bound into the sealed payload's AEAD
        associated data.
    :func:`compute_bucket_deletion_fingerprint`
        Structured observation of deletion-relevant target contents; callers
        remain responsible for keeping the target stable while it is computed.
"""

from __future__ import annotations

from ._contracts import (
    ArchiveBucketCommand,
    ArchiveBucketResult,
    AssessBucketDeletionCommand,
    BrowseBucketCommand,
    BrowseBucketResult,
    BucketDeletionAssessment,
    BucketDeletionFingerprint,
    BucketDiskUsageSubdirRow,
    BucketNamespaceInventoryRow,
    DeleteBucketCommand,
    DeleteBucketResult,
    DiskUsageBucketCommand,
    DiskUsageBucketResult,
    ExportBucketCommand,
    ExportBucketResult,
    ImportBucketCommand,
    ImportBucketResult,
    InspectBucketArchiveCommand,
    InspectBucketArchiveResult,
    RenameBucketCommand,
    RenameBucketResult,
    RestoreBucketCommand,
    RestoreBucketResult,
)
from ._manifest_digest import compute_bucket_deletion_fingerprint, compute_manifest_digest
from ._sandbox import (
    SANDBOX_LABEL_PREFIX,
    ArchiveSandboxCommand,
    ArchiveSandboxResult,
    CreateSandboxCommand,
    CreateSandboxResult,
    DiscardSandboxCommand,
    DiscardSandboxResult,
    MergeSandboxCommand,
    MergeSandboxResult,
    PreviewDiscardSandboxCommand,
    PreviewDiscardSandboxResult,
    RestoreSandboxCommand,
    RestoreSandboxResult,
    SandboxAlreadyExistsError,
    SandboxDiscardRefusedError,
    SandboxMergeRefusedError,
    SandboxMergeScope,
    SandboxNotArchivedError,
    SandboxNotFoundError,
    SandboxSourceNotFoundError,
    archive_sandbox,
    create_sandbox,
    discard_sandbox,
    is_sandbox_label,
    list_sandboxes,
    merge_sandbox,
    preview_discard_sandbox,
    restore_sandbox,
    sandbox_label,
)
from ._service import BucketMaintenanceService

__all__ = [
    "SANDBOX_LABEL_PREFIX",
    "ArchiveBucketCommand",
    "ArchiveBucketResult",
    "ArchiveSandboxCommand",
    "ArchiveSandboxResult",
    "AssessBucketDeletionCommand",
    "BrowseBucketCommand",
    "BrowseBucketResult",
    "BucketDeletionAssessment",
    "BucketDeletionFingerprint",
    "BucketDiskUsageSubdirRow",
    "BucketMaintenanceService",
    "BucketNamespaceInventoryRow",
    "CreateSandboxCommand",
    "CreateSandboxResult",
    "DeleteBucketCommand",
    "DeleteBucketResult",
    "DiscardSandboxCommand",
    "DiscardSandboxResult",
    "DiskUsageBucketCommand",
    "DiskUsageBucketResult",
    "ExportBucketCommand",
    "ExportBucketResult",
    "ImportBucketCommand",
    "ImportBucketResult",
    "InspectBucketArchiveCommand",
    "InspectBucketArchiveResult",
    "MergeSandboxCommand",
    "MergeSandboxResult",
    "PreviewDiscardSandboxCommand",
    "PreviewDiscardSandboxResult",
    "RenameBucketCommand",
    "RenameBucketResult",
    "RestoreBucketCommand",
    "RestoreBucketResult",
    "RestoreSandboxCommand",
    "RestoreSandboxResult",
    "SandboxAlreadyExistsError",
    "SandboxDiscardRefusedError",
    "SandboxMergeRefusedError",
    "SandboxMergeScope",
    "SandboxNotArchivedError",
    "SandboxNotFoundError",
    "SandboxSourceNotFoundError",
    "archive_sandbox",
    "compute_bucket_deletion_fingerprint",
    "compute_manifest_digest",
    "create_sandbox",
    "discard_sandbox",
    "is_sandbox_label",
    "list_sandboxes",
    "merge_sandbox",
    "preview_discard_sandbox",
    "restore_sandbox",
    "sandbox_label",
]
