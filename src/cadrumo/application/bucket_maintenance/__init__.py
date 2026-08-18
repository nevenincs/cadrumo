"""Application-layer bucket-maintenance read-only projection facade.

This package exposes :class:`BucketMaintenanceService` and its Pydantic
command/result contracts for profile-scoped storage maintenance. The
service is currently a **read-only** surface over the current-capsule
primitives: target locking (``deletion_target_locks``), a deletion
pre-assessment (``assess_deletion``), namespace-level inventory
(the browse and disk-usage surfaces were retired with their producerless contracts).

Bucket rename, bucket delete, bucket archive (reversible dormancy),
bucket restore, sealed-archive export/import/inspect, and the earlier
sandbox lifecycle (``create_sandbox`` / ``discard_sandbox`` /
``archive_sandbox`` / ``restore_sandbox`` / ``merge_sandbox``) were
removed from this package when profile identity moved onto the
encrypted custody capsule; see
:mod:`application.user_profile` (``ProfileCapsuleLifecycle``) for the
surviving create/restore/select/delete primitives. Bucket rename has no
successor primitive; bucket delete lives on as
``ProfileCapsuleLifecycle.prepare_delete`` /
``confirm_delete`` / ``delete``, consumed today only by the durable
all-profile ``application.config_reset`` flow. Bucket delete has no
single-target operator route; bucket archive, bucket restore, and
sealed-archive export/import/inspect have no successor primitive at
all. :meth:`BucketMaintenanceService.assess_deletion` is the retention
pre-assessment for a destructive delete; it does not implement reset
orchestration itself.

:meth:`BucketMaintenanceService.disk_usage` measures a bucket's on-disk
footprint by summing regular-file byte sizes under its fixed directory
layout; it reads only filesystem metadata, never decrypted content, so
it can measure a non-active bucket without opening a storage session.

See Also:
    :mod:`application.user_profile`
        ``ProfileCapsuleLifecycle``, the custody transaction owner for
        create, restore, select and delete.
    :mod:`application.config_reset`
        The durable all-profile reset flow, the sole current caller of
        ``ProfileCapsuleLifecycle.delete``.
"""

from __future__ import annotations

from ._contracts import (
    AssessBucketDeletionCommand,
    BucketDeletionAssessment,
    BucketDeletionFingerprint,
)
from ._service import BucketMaintenanceService

__all__ = [
    "AssessBucketDeletionCommand",
    "BucketDeletionAssessment",
    "BucketDeletionFingerprint",
    "BucketMaintenanceService",
]
