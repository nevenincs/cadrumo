"""Operator-facing bucket maintenance surface.

Composes the existing single-writer primitives that own bucket-scoped
lifecycle operations (label rename, soft tombstone + hard removal,
portable bundle export / import, namespace-grouped browse) behind a
thin service that emits the bucket-maintenance audit events alongside
the lifecycle events the inner primitives already emit.

Authority: ``2026-06-03-cli-workflow-redesign-adr`` (composition
pattern). The service NEVER re-implements a cross-store write — it
delegates to the existing top-level re-exports (``rename_profile``,
``delete_profile_with_lifecycle_span``, ``remove_profile_bucket_directory``,
``serialize_profile_bundle``, ``deserialize_profile_bundle``).

This package exposes the lifecycle composition verbs ``browse``, ``delete``,
``export``, ``import``, and ``rename``. The ``search`` verb is deferred behind
its own ADR because it must route through domain repositories instead of
decrypting secure-object storage directly.
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
