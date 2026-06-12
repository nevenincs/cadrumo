"""``BucketMaintenanceService`` composition implementation.

The service delegates every cross-store mutation to its existing
single-writer primitive (see the ADR
``2026-06-03-cli-workflow-redesign-adr``). It contributes the
bucket-maintenance audit-event emission that the inner primitives do
not own; the inner primitives keep emitting their lifecycle events
(``PROFILE_RENAMED`` etc.) so each operator action surfaces both
perspectives in the bucket-event history.

This module uses :class:`BucketEventHistoryRepository` for event emission.
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
from ..user_profile import (
    delete_profile_with_lifecycle_span,
    remove_profile_bucket_directory,
    rename_profile,
)
from ..workflow import read_profile_bucket_by_id
from ._contracts import (
    BrowseBucketCommand,
    BrowseBucketResult,
    BucketNamespaceInventoryRow,
    DeleteBucketCommand,
    DeleteBucketResult,
    RenameBucketCommand,
    RenameBucketResult,
)

if TYPE_CHECKING:  # pragma: no cover - import-cycle guard
    from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol


_RENAME_PAYLOAD_VERSION = 1
_DELETE_PAYLOAD_VERSION = 1


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

    @staticmethod
    def _event_repository_for_bucket(bucket_id: str) -> BucketEventHistoryRepository:
        """Return a :class:`BucketEventHistoryRepository` bound to ``bucket_id``'s database.

        The maintenance event for a surviving bucket belongs in that
        bucket's own event history — the same binding principle the
        lifecycle service applies — so a rename of a non-active bucket
        never writes its audit event into a different bucket's
        catalogue. ``delete`` deliberately does NOT use this binding:
        its event must outlive the erased bucket, so it lands in the
        operator's active bucket history instead.
        """
        from ...adapters.persistence.storage.runtime_repository import (
            secure_object_repository_for_bucket,
        )

        return BucketEventHistoryRepository(objects=secure_object_repository_for_bucket(bucket_id))

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

        Both events land in the renamed bucket's OWN event history:
        the lifecycle service already binds its event repository to the
        target bucket's database, and the maintenance emission mirrors
        that binding so the audit trail can never split from the
        records it describes when the renamed bucket is not the active
        one.

        Returns:
            :class:`RenameBucketResult`: The result of the rename operation.
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
        repository = self._event_repository or self._event_repository_for_bucket(command.bucket_id)
        repository.save(append_bucket_event(repository.load(), event))
        return RenameBucketResult(
            bucket_id=command.bucket_id,
            previous_label=previous_label,
            new_label=record.display_name,
            occurred_at=occurred_at,
        )

    def delete(self, command: DeleteBucketCommand) -> DeleteBucketResult:
        """Destructively erase the bucket identified by ``command.bucket_id``.

        Composes the existing two-step erase pattern: soft tombstone
        via :func:`delete_profile_with_lifecycle_span` (clears the
        active-profile pointer, writes the manifest lifecycle status,
        tombstones the encrypted record, emits ``PROFILE_TOMBSTONED``)
        followed by hard directory removal via
        :func:`remove_profile_bucket_directory`. The ``BUCKET_DELETED``
        event is emitted into the bucket's own history between the
        soft and hard steps so the operator's verb invocation is
        recorded before the storage is gone.

        Refuses unless ``command.confirmed`` is ``True``; refuses if
        the target bucket is the active profile (the operator must
        switch profiles first, per the 2026-05-15 amendment to the
        bucket ADR). Both refusals are service-boundary contracts,
        not CLI ergonomics — a programmatic caller observes the same
        guarantees.

        Returns:
            :class:`DeleteBucketResult`: The result of the delete operation.
        """
        from ...core import resolve_active_bucket_id
        from ...domain.buckets import BucketDeleteRefusedError

        if not command.confirmed:
            raise BucketDeleteRefusedError(
                translated_message="application.bucket_maintenance.errors.delete_not_confirmed",
                context={"bucket_id": command.bucket_id},
            )
        if resolve_active_bucket_id() == command.bucket_id:
            raise BucketDeleteRefusedError(
                translated_message="application.bucket_maintenance.errors.delete_active_bucket",
                context={"bucket_id": command.bucket_id},
            )
        pointer = read_profile_bucket_by_id(command.bucket_id)
        if pointer is None:
            from ...domain.user_profile import ProfileNotFoundError

            raise ProfileNotFoundError(
                translated_message="application.user_profile.errors.no_active_profile_selected",
                context={"bucket_id": command.bucket_id},
            )
        previous_label = pointer.label
        delete_profile_with_lifecycle_span(command.bucket_id)
        occurred_at = now()
        event = BucketEvent(
            event_id=derive_bucket_event_id(
                bucket_id=command.bucket_id,
                event_type=BucketEventType.BUCKET_DELETED,
                occurred_at=occurred_at,
                actor="bucket-maintenance",
                object_type=BucketEventObjectType.BUCKET,
                object_id=command.bucket_id,
                payload={"previous_label": previous_label},
            ),
            bucket_id=command.bucket_id,
            event_type=BucketEventType.BUCKET_DELETED,
            occurred_at=occurred_at,
            actor="bucket-maintenance",
            object_type=BucketEventObjectType.BUCKET,
            object_id=command.bucket_id,
            payload_version=_DELETE_PAYLOAD_VERSION,
            payload={"previous_label": previous_label},
        )
        repository = self._event_repository or BucketEventHistoryRepository()
        repository.save(append_bucket_event(repository.load(), event))
        remove_profile_bucket_directory(command.bucket_id)
        return DeleteBucketResult(
            bucket_id=command.bucket_id,
            previous_label=previous_label,
            occurred_at=occurred_at,
        )

    def browse(self, command: BrowseBucketCommand) -> BrowseBucketResult:
        """Enumerate the bucket namespace inventory and return a :class:`BrowseBucketResult`.

        Composes :meth:`SecureObjectRepository.list_namespaces` with a
        per-namespace row count via :meth:`list_keys` (whose return is
        the HMAC-digest list — the count is meaningful even though the
        digests themselves are opaque). The result excludes any
        namespace whose name does not contain ``namespace_filter`` as a
        substring when one is supplied. Read-only; emits no bucket
        event.

        Key-level browse (returning operator-readable keys + classification
        per row) requires decryption and a ``SensitivityClass`` redaction
        policy; deferred to a follow-up Step per the composition-pattern
        ADR.
        """
        from ...adapters.persistence.storage.runtime_repository import (
            secure_object_repository_for_active_bucket,
        )

        repository = secure_object_repository_for_active_bucket()
        all_namespaces = repository.list_namespaces()
        if command.namespace_filter is not None:
            needle = command.namespace_filter
            namespaces = tuple(ns for ns in all_namespaces if needle in ns)
        else:
            namespaces = all_namespaces
        rows = tuple(
            BucketNamespaceInventoryRow(namespace=ns, row_count=len(repository.list_keys(ns))) for ns in namespaces
        )
        return BrowseBucketResult(bucket_id=command.bucket_id, rows=rows)
