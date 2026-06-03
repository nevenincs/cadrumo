"""``BucketMaintenanceService`` composition implementation.

The service delegates every cross-store mutation to its existing
single-writer primitive (see the ADR
``2026-06-03-cli-workflow-redesign-adr``). It contributes the
bucket-maintenance audit-event emission that the inner primitives do
not own; the inner primitives keep emitting their lifecycle events
(``PROFILE_RENAMED`` etc.) so each operator action surfaces both
perspectives in the bucket-event history.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.time import now
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
)
from ..user_profile import rename_profile
from ..workflow._profile_bucket_scan import read_profile_bucket_by_id
from ._contracts import RenameBucketCommand, RenameBucketResult

if TYPE_CHECKING:  # pragma: no cover - import-cycle guard
    from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol


_RENAME_PAYLOAD_VERSION = 1


class BucketMaintenanceService:
    """Compose existing primitives behind the bucket-maintenance surface.

    The service holds no state of its own. An optional event-history
    repository override is accepted for tests that want to assert
    against an in-memory or alternate-backend repository; production
    instantiates the default which is bound to the active bucket via
    :class:`BucketEventHistoryRepository`.
    """

    def __init__(
        self,
        *,
        event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    ) -> None:
        self._event_repository = event_repository

    def rename(self, command: RenameBucketCommand) -> RenameBucketResult:
        """Relabel the bucket identified by ``command.bucket_id``.

        Reads the current operator-visible label, delegates the
        cross-store relabel to :func:`rename_profile`, then emits
        ``BUCKET_RENAMED`` carrying the previous label in the payload
        so the audit consumer can render the before / after pair
        without re-reading the manifest.

        The inner :func:`rename_profile` call emits ``PROFILE_RENAMED``
        from the lifecycle service; the two events are co-emitted by
        design — the lifecycle event records the data change, the
        maintenance event records the operator-surface invocation.
        """
        pointer = read_profile_bucket_by_id(command.bucket_id)
        if pointer is None:
            from ...domain.user_profile import ProfileNotFoundError

            raise ProfileNotFoundError(
                translated_message="application.user_profile.errors.no_active_profile_selected",
                context={"bucket_id": command.bucket_id},
            )
        previous_label = pointer.label
        record = rename_profile(profile_id=command.bucket_id, new_label=command.new_label)
        occurred_at = now()
        event = BucketEvent(
            event_id=derive_bucket_event_id(
                bucket_id=command.bucket_id,
                event_type=BucketEventType.BUCKET_RENAMED,
                occurred_at=occurred_at,
                actor="bucket-maintenance",
                object_type=BucketEventObjectType.BUCKET,
                object_id=command.bucket_id,
                payload={"previous_label": previous_label, "new_label": record.display_name},
            ),
            bucket_id=command.bucket_id,
            event_type=BucketEventType.BUCKET_RENAMED,
            occurred_at=occurred_at,
            actor="bucket-maintenance",
            object_type=BucketEventObjectType.BUCKET,
            object_id=command.bucket_id,
            payload_version=_RENAME_PAYLOAD_VERSION,
            payload={"previous_label": previous_label, "new_label": record.display_name},
        )
        repository = self._event_repository or BucketEventHistoryRepository()
        repository.save(append_bucket_event(repository.load(), event))
        return RenameBucketResult(
            bucket_id=command.bucket_id,
            previous_label=previous_label,
            new_label=record.display_name,
            occurred_at=occurred_at,
        )
