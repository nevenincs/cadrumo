"""``BucketMaintenanceService`` composition implementation.

The service delegates every cross-store mutation to its existing
single-writer primitive. It contributes the
bucket-maintenance audit-event emission that the inner primitives do
not own; the inner primitives keep emitting their lifecycle events
(``PROFILE_RENAMED`` etc.) so each operator action surfaces both
perspectives in the bucket-event history.

This module uses :class:`BucketEventHistoryRepository` for event
emission, :class:`~domain.user_profile.UserProfilePortableExport`
for sealed export/import payloads, and
:class:`~adapters.persistence.storage.bucket.ExportArchiveHeader`
for archive frontmatter. The archive file is an explicit operator
handoff artifact; bucket state remains owned by the profile and secure
repository primitives the service composes.
"""

from __future__ import annotations

import base64
import json
import secrets
from collections.abc import Generator, Iterable
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.storage import (
    BUCKET_AUDIT_DIRNAME,
    BUCKET_BLOBS_DIRNAME,
    BUCKET_DB_DIRNAME,
    StorageCustodyProfile,
)
from ...adapters.persistence.storage.bucket import acquire_lock, release_lock
from ...core.external_constants import UTF_8_ENCODING
from ...core.product_identity import PRODUCT_IDENTITY
from ...core.time import now
from ...domain.buckets import (
    BucketArchiveRefusedError,
    BucketDeleteRefusedError,
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
    BucketImportError,
    BucketRestoreRefusedError,
    append_bucket_event,
    derive_bucket_event_id,
)
from ...domain.user_profile import ProfileNotFoundError, UserProfileStatus
from .._config_reset_repository import (
    ConfigResetJournalError,
    ConfigResetJournalRepository,
)
from ..user_profile import (
    UnsupportedBundleSchemaVersionError,
    active_profile_pointer_transaction,
    delete_profile_with_lifecycle_span,
    deserialize_profile_bundle,
    missing_filing_baseline_flags,
    profile_create_storage_span,
    profile_storage_session,
    reactivate_profile_with_lifecycle_span,
    record_to_path_values,
    register_active_profile,
    remove_profile_bucket_directory,
    rename_profile,
    serialize_profile_bundle,
    validate_bundle_payload,
)
from ..workflow import read_profile_bucket_by_id
from ._contracts import (
    ArchiveBucketCommand,
    ArchiveBucketResult,
    AssessBucketDeletionCommand,
    BrowseBucketCommand,
    BrowseBucketResult,
    BucketDeletionAssessment,
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
from ._manifest_digest import (
    compute_bucket_deletion_fingerprint,
    compute_manifest_digest,
    validated_bucket_deletion_paths,
)

if TYPE_CHECKING:  # pragma: no cover - import-cycle guard
    from datetime import datetime

    from ...domain.buckets import BucketEventHistoryRepositoryProtocol
    from ...domain.retention import RetentionFloorAssessment
    from ...domain.user_profile import UserProfilePortableExport
    from .._bucket_deletion_contracts import BucketDeletionFingerprint


_RENAME_PAYLOAD_VERSION = 1
_DELETE_PAYLOAD_VERSION = 1
_ARCHIVE_PAYLOAD_VERSION = 1
_RESTORE_PAYLOAD_VERSION = 1
_EXPORT_PAYLOAD_VERSION = 1
_IMPORT_PAYLOAD_VERSION = 1
_ARCHIVE_SCHEMA_VERSION = 3
_RECOVERY_WRAP_SALT_BYTES = 16


def ensure_archive_schema_supported(archive_schema_version: int) -> None:
    """Refuse a sealed-archive version this application cannot restore.

    Only the current archive layout is restorable. A higher version is
    identified as written by a newer application; a lower version is
    unsupported and is never interpreted as the current layout.

    Raises:
        BucketImportError: When the version is not current.
    """
    if archive_schema_version > _ARCHIVE_SCHEMA_VERSION:
        raise BucketImportError(
            translated_message="application.bucket_maintenance.errors.archive_schema_version_from_future",
            context={
                "archive_schema_version": str(archive_schema_version),
                "max_supported": str(_ARCHIVE_SCHEMA_VERSION),
            },
        )
    if archive_schema_version < _ARCHIVE_SCHEMA_VERSION:
        raise BucketImportError(
            translated_message="application.bucket_maintenance.errors.unsupported_archive_schema_version",
            context={"archive_schema_version": str(archive_schema_version)},
        )


def _directory_byte_total(directory: Path) -> tuple[int, int]:
    """Return ``(total_bytes, file_count)`` for every regular file under ``directory``.

    Missing directories (a bucket whose ``blobs``/``audit`` subdirectory was
    never populated still exists per :func:`provision_bucket_directory`, but
    the helper tolerates absence defensively) report ``(0, 0)`` rather than
    raising. Only regular-file sizes are summed via ``os.stat``; no file is
    opened or decrypted.
    """
    if not directory.is_dir():
        return 0, 0
    total_bytes = 0
    file_count = 0
    for entry in directory.rglob("*"):
        if entry.is_file():
            total_bytes += entry.stat().st_size
            file_count += 1
    return total_bytes, file_count


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
        """Return an event repository bound to a surviving target bucket.

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

    @contextmanager
    def _mutation_target_lock(
        self,
        *,
        root: Path,
        bucket_id: str,
        wait_seconds: float,
        missing_ok: bool = False,
    ) -> Generator[None]:
        try:
            paths = validated_bucket_deletion_paths(
                root=root,
                bucket_id=bucket_id,
            )
        except FileNotFoundError as exc:
            if missing_ok:
                yield
                return
            raise ProfileNotFoundError(
                translated_message="application.user_profile.errors.no_active_profile_selected",
                context={"bucket_id": bucket_id},
            ) from exc
        except ValueError as exc:
            raise BucketDeleteRefusedError(
                "bucket mutation lock refuses a linked target",
                context={"bucket_id": bucket_id},
            ) from exc
        acquire_lock(paths, wait_seconds=wait_seconds)
        try:
            yield
        finally:
            release_lock(paths)

    @contextmanager
    def deletion_target_locks(
        self,
        *,
        root: Path,
        bucket_ids: Iterable[str],
        wait_seconds: float,
    ) -> Generator[None]:
        """Hold existing deletion targets in stable UUID order.

        Missing targets, including a dangling active-pointer identifier, are
        not materialized merely to create a lockfile. Existing targets are
        validated against link redirection before their canonical bucket
        lockfiles are acquired.
        """
        with ExitStack() as stack:
            for bucket_id in sorted(set(bucket_ids)):
                try:
                    paths = validated_bucket_deletion_paths(
                        root=root,
                        bucket_id=bucket_id,
                    )
                except FileNotFoundError:
                    continue
                except ValueError as exc:
                    raise BucketDeleteRefusedError(
                        "bucket deletion lock refuses a linked target",
                        context={"bucket_id": bucket_id},
                    ) from exc
                acquire_lock(paths, wait_seconds=wait_seconds)
                stack.callback(release_lock, paths)
            yield

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
        from ...core.config import load_settings

        settings = load_settings()
        with self._mutation_target_lock(
            root=settings.cadrumo_local_storage_root,
            bucket_id=command.bucket_id,
            wait_seconds=settings.cadrumo_file_lock_timeout_s,
        ):
            pointer = read_profile_bucket_by_id(command.bucket_id)
            if pointer is None:
                raise ProfileNotFoundError(
                    translated_message="application.user_profile.errors.no_active_profile_selected",
                    context={"bucket_id": command.bucket_id},
                )
            previous_label = pointer.label
            with profile_storage_session(command.bucket_id):
                record = rename_profile(
                    profile_id=command.bucket_id,
                    new_label=command.new_label,
                )
                occurred_at = now()
                event = BucketEvent(
                    event_id=derive_bucket_event_id(
                        bucket_id=command.bucket_id,
                        event_type=BucketEventType.BUCKET_RENAMED,
                        occurred_at=occurred_at,
                        actor="bucket-maintenance",
                        object_type=BucketEventObjectType.BUCKET,
                        object_id=command.bucket_id,
                        payload={
                            "previous_label": previous_label,
                            "new_label": record.display_name,
                        },
                    ),
                    bucket_id=command.bucket_id,
                    event_type=BucketEventType.BUCKET_RENAMED,
                    occurred_at=occurred_at,
                    actor="bucket-maintenance",
                    object_type=BucketEventObjectType.BUCKET,
                    object_id=command.bucket_id,
                    payload_version=_RENAME_PAYLOAD_VERSION,
                    payload={
                        "previous_label": previous_label,
                        "new_label": record.display_name,
                    },
                )
                repository = self._event_repository or self._event_repository_for_bucket(
                    command.bucket_id,
                )
                repository.save(append_bucket_event(repository.load(), event))
        return RenameBucketResult(
            bucket_id=command.bucket_id,
            previous_label=previous_label,
            new_label=record.display_name,
            occurred_at=occurred_at,
        )

    def delete(self, command: DeleteBucketCommand) -> DeleteBucketResult:
        """Delete one bucket under pointer-first canonical mutation locks."""
        from ...core.config import load_settings

        settings = load_settings()
        with (
            active_profile_pointer_transaction(settings.cadrumo_local_storage_root),
            self._mutation_target_lock(
                root=settings.cadrumo_local_storage_root,
                bucket_id=command.bucket_id,
                wait_seconds=settings.cadrumo_file_lock_timeout_s,
                missing_ok=command.reset_operation_id is not None,
            ),
        ):
            return self._delete_locked(command)

    def _delete_locked(self, command: DeleteBucketCommand) -> DeleteBucketResult:
        """Destructively erase the bucket identified by ``command.bucket_id``.

        Composes the existing two-step erase pattern: soft tombstone
        via :func:`delete_profile_with_lifecycle_span` (clears the
        active-profile pointer, writes the manifest lifecycle status,
        tombstones the encrypted record, emits ``PROFILE_TOMBSTONED``)
        followed by hard directory removal via
        :func:`remove_profile_bucket_directory`. Ordinary deletion writes
        ``BUCKET_DELETED`` through the injected repository or the default
        repository bound to the active bucket. Reset-owned deletion uses only
        an explicitly injected event repository; otherwise its external reset
        journal remains the surviving ownership evidence and no ambient
        post-delete event route is opened.

        Refuses unless ``command.confirmed`` is ``True``; refuses if
        the target bucket is the active profile (the operator must
        switch profiles first). Both refusals are service-boundary contracts,
        not CLI ergonomics — a programmatic caller observes the same
        guarantees.

        Retention and the deletion fingerprint are reassessed before deletion.
        An expected-fingerprint mismatch is refused before lifecycle mutation.
        Supplied operation context must match the journal's target snapshot,
        approved retention decision, deletion marker, and deleting/deleted
        phase. It is propagated to the result and to any explicitly routed
        deletion event.

        An already-absent target is accepted only when the caller supplies an
        operation identifier and expected fingerprint that match a durable
        deleting marker in the external reset journal.

        Returns:
            :class:`DeleteBucketResult`: The result of the delete operation.
        """
        self._refuse_unconfirmed_or_active(command)
        assessment = self.assess_deletion(AssessBucketDeletionCommand(bucket_id=command.bucket_id))
        self._verify_reset_ownership(command)
        absent = self._absent_target_result(command, assessment)
        if absent is not None:
            return absent
        fingerprint, retention, previous_label = self._enforced_deletion_context(command, assessment)
        override_used = self._enforce_retention_floor(command, retention)
        latest_safe_erase_date = retention.latest_safe_erase_date
        delete_profile_with_lifecycle_span(command.bucket_id)
        event, occurred_at = self._deletion_event(command, previous_label, fingerprint, override_used, retention)
        self._route_deletion_event(command, event)
        remove_profile_bucket_directory(command.bucket_id)
        return DeleteBucketResult(
            bucket_id=command.bucket_id,
            previous_label=previous_label,
            occurred_at=occurred_at,
            retention_override_used=override_used,
            latest_safe_erase_date=latest_safe_erase_date,
            deletion_fingerprint=fingerprint.digest,
            reset_operation_id=command.reset_operation_id,
        )

    @staticmethod
    def _refuse_unconfirmed_or_active(command: DeleteBucketCommand) -> None:
        """Refuse an unconfirmed erase or one that targets the active bucket.

        Both refusals are service-boundary contracts, not CLI ergonomics — a
        programmatic caller observes the same guarantees.
        """
        from ...core import resolve_active_bucket_id

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

    @staticmethod
    def _verify_reset_ownership(command: DeleteBucketCommand) -> None:
        """Verify the external reset journal owns a reset-driven deletion.

        Only runs when the caller supplies both an operation identifier and an
        expected fingerprint; otherwise this is not a reset-owned deletion and
        no ownership evidence is demanded.
        """
        if command.reset_operation_id is None or command.expected_deletion_fingerprint is None:
            return
        try:
            ConfigResetJournalRepository().verify_deletion_ownership(
                operation_id=command.reset_operation_id,
                bucket_id=command.bucket_id,
                expected_fingerprint=command.expected_deletion_fingerprint,
            )
        except ConfigResetJournalError as exc:
            raise BucketDeleteRefusedError(
                "reset journal does not own the requested bucket deletion",
                context={
                    "bucket_id": command.bucket_id,
                    "reset_operation_id": command.reset_operation_id,
                    "expected_fingerprint": command.expected_deletion_fingerprint,
                },
            ) from exc

    @staticmethod
    def _absent_target_result(
        command: DeleteBucketCommand,
        assessment: BucketDeletionAssessment,
    ) -> DeleteBucketResult | None:
        """Return the already-absent result, or ``None`` when the target exists.

        An already-absent target is accepted only when the caller supplies an
        operation identifier and expected fingerprint that match a durable
        deleting marker in the external reset journal; otherwise the missing
        bucket is refused.
        """
        if assessment.exists:
            return None
        if command.reset_operation_id is not None and command.expected_deletion_fingerprint is not None:
            return DeleteBucketResult(
                bucket_id=command.bucket_id,
                occurred_at=now(),
                deletion_fingerprint=command.expected_deletion_fingerprint,
                reset_operation_id=command.reset_operation_id,
                already_absent=True,
            )
        from ...domain.user_profile import ProfileNotFoundError

        raise ProfileNotFoundError(
            translated_message="application.user_profile.errors.no_active_profile_selected",
            context={"bucket_id": command.bucket_id},
        )

    @staticmethod
    def _enforced_deletion_context(
        command: DeleteBucketCommand,
        assessment: BucketDeletionAssessment,
    ) -> tuple[BucketDeletionFingerprint, RetentionFloorAssessment, str]:
        """Extract the erase context, refusing on a post-assessment fingerprint drift.

        An expected-fingerprint mismatch is refused before any lifecycle
        mutation. Returns the deletion fingerprint, retention assessment, and
        previous label for the subsequent tombstone and event.
        """
        fingerprint = assessment.fingerprint
        retention = assessment.retention
        assert fingerprint is not None
        assert retention is not None
        if (
            command.expected_deletion_fingerprint is not None
            and command.expected_deletion_fingerprint != fingerprint.digest
        ):
            raise BucketDeleteRefusedError(
                "bucket content changed after reset deletion assessment",
                context={
                    "bucket_id": command.bucket_id,
                    "reset_operation_id": command.reset_operation_id or "",
                    "expected_fingerprint": command.expected_deletion_fingerprint,
                    "observed_fingerprint": fingerprint.digest,
                },
            )
        previous_label = assessment.label
        assert previous_label is not None
        return fingerprint, retention, previous_label

    @staticmethod
    def _deletion_event(
        command: DeleteBucketCommand,
        previous_label: str,
        fingerprint: BucketDeletionFingerprint,
        override_used: bool,
        retention: RetentionFloorAssessment,
    ) -> tuple[BucketEvent, datetime]:
        """Build the ``BUCKET_DELETED`` event and its ``occurred_at`` stamp."""
        occurred_at = now()
        payload: dict[str, str] = {"previous_label": previous_label}
        if command.reset_operation_id is not None:
            payload["reset_operation_id"] = command.reset_operation_id
            payload["deletion_fingerprint"] = fingerprint.digest
        if override_used:
            # The override is a legally-material operator decision (erasing a
            # record the law still requires kept); record the acknowledgement,
            # the operator's reason, and the bypassed safe-erase date so the
            # append-only audit trail explains why the record was destroyed early.
            payload["retention_override"] = "true"
            payload["retention_override_reason"] = command.retention_override_reason or ""
            latest_safe_erase_date = retention.latest_safe_erase_date
            if latest_safe_erase_date is not None:
                payload["retention_safe_erase_date"] = latest_safe_erase_date.isoformat()
        event = BucketEvent(
            event_id=derive_bucket_event_id(
                bucket_id=command.bucket_id,
                event_type=BucketEventType.BUCKET_DELETED,
                occurred_at=occurred_at,
                actor="bucket-maintenance",
                object_type=BucketEventObjectType.BUCKET,
                object_id=command.bucket_id,
                payload=payload,
            ),
            bucket_id=command.bucket_id,
            event_type=BucketEventType.BUCKET_DELETED,
            occurred_at=occurred_at,
            actor="bucket-maintenance",
            object_type=BucketEventObjectType.BUCKET,
            object_id=command.bucket_id,
            payload_version=_DELETE_PAYLOAD_VERSION,
            payload=payload,
        )
        return event, occurred_at

    def _route_deletion_event(self, command: DeleteBucketCommand, event: BucketEvent) -> None:
        """Route the deletion event, honouring the reset-owned no-ambient-route rule.

        Ordinary deletion writes through the injected repository or the default
        repository bound to the active bucket. Reset-owned deletion uses only an
        explicitly injected event repository; otherwise its external reset
        journal remains the surviving ownership evidence and no ambient
        post-delete event route is opened.
        """
        if command.reset_operation_id is None:
            repository = self._event_repository or BucketEventHistoryRepository()
            repository.save(append_bucket_event(repository.load(), event))
        elif self._event_repository is not None:
            self._event_repository.save(
                append_bucket_event(self._event_repository.load(), event),
            )

    def assess_deletion(
        self,
        command: AssessBucketDeletionCommand,
    ) -> BucketDeletionAssessment:
        """Assess one explicit bucket target without lifecycle mutation.

        A missing bucket directory produces an absent assessment. An existing
        bucket with an unregistered or unreadable manifest is refused. A valid
        existing bucket produces its label, lifecycle status, retention
        information, and deletion fingerprint.
        """
        from ...core.config import load_settings

        root = load_settings().cadrumo_local_storage_root
        try:
            validated_bucket_deletion_paths(root=root, bucket_id=command.bucket_id)
        except FileNotFoundError:
            return BucketDeletionAssessment(bucket_id=command.bucket_id, exists=False)
        except ValueError as exc:
            raise BucketDeleteRefusedError(
                "bucket deletion assessment refuses a linked bucket root",
                context={"bucket_id": command.bucket_id},
            ) from exc
        pointer = read_profile_bucket_by_id(command.bucket_id)
        if pointer is None:
            raise BucketDeleteRefusedError(
                "bucket directory exists without a readable registered manifest",
                context={"bucket_id": command.bucket_id},
            )
        retention = self._assess_retention_floor(command.bucket_id)
        fingerprint = compute_bucket_deletion_fingerprint(
            root=root,
            bucket_id=command.bucket_id,
        )
        return BucketDeletionAssessment(
            bucket_id=command.bucket_id,
            exists=True,
            label=pointer.label,
            status=pointer.status,
            fingerprint=fingerprint,
            retention=retention,
        )

    def archive(self, command: ArchiveBucketCommand) -> ArchiveBucketResult:
        """Archive one bucket under pointer-first canonical mutation locks."""
        from ...core.config import load_settings

        settings = load_settings()
        with (
            active_profile_pointer_transaction(settings.cadrumo_local_storage_root),
            self._mutation_target_lock(
                root=settings.cadrumo_local_storage_root,
                bucket_id=command.bucket_id,
                wait_seconds=settings.cadrumo_file_lock_timeout_s,
            ),
        ):
            return self._archive_locked(command)

    def _archive_locked(self, command: ArchiveBucketCommand) -> ArchiveBucketResult:
        """Move the bucket identified by ``command.bucket_id`` into reversible dormancy.

        Composes :func:`~application.user_profile.reactivate_profile_with_lifecycle_span`'s
        counterpart, :func:`~application.user_profile.delete_profile_with_lifecycle_span`
        — the SAME soft-tombstone primitive :meth:`delete` composes — but
        deliberately stops there: the hard directory removal
        (:func:`~application.user_profile.remove_profile_bucket_directory`)
        that :meth:`delete` performs afterward never runs, so the bucket
        directory, manifest, and encrypted record all survive intact and
        :meth:`restore` can bring the same bucket back.

        Refuses unless ``command.confirmed`` is ``True``; refuses if the
        target bucket is the active profile (the operator must switch
        profiles first, mirroring :meth:`delete`'s own contract). The
        ``BUCKET_ARCHIVED`` event lands in the archived bucket's OWN event
        history (mirroring :meth:`rename`'s binding) since the bucket
        still exists after this call — unlike :meth:`delete`'s event,
        which must outlive the erased bucket.

        Returns:
            :class:`ArchiveBucketResult`: The result of the archive operation.
        """
        from ...core import resolve_active_bucket_id

        if not command.confirmed:
            raise BucketArchiveRefusedError(
                translated_message="application.bucket_maintenance.errors.archive_not_confirmed",
                context={"bucket_id": command.bucket_id},
            )
        if resolve_active_bucket_id() == command.bucket_id:
            raise BucketArchiveRefusedError(
                translated_message="application.bucket_maintenance.errors.archive_active_bucket",
                context={"bucket_id": command.bucket_id},
            )
        pointer = read_profile_bucket_by_id(command.bucket_id)
        if pointer is None:
            from ...domain.user_profile import ProfileNotFoundError

            raise ProfileNotFoundError(
                translated_message="application.user_profile.errors.no_active_profile_selected",
                context={"bucket_id": command.bucket_id},
            )
        label = pointer.label
        delete_profile_with_lifecycle_span(command.bucket_id)
        occurred_at = now()
        payload = {"label": label}
        event = BucketEvent(
            event_id=derive_bucket_event_id(
                bucket_id=command.bucket_id,
                event_type=BucketEventType.BUCKET_ARCHIVED,
                occurred_at=occurred_at,
                actor="bucket-maintenance",
                object_type=BucketEventObjectType.BUCKET,
                object_id=command.bucket_id,
                payload=payload,
            ),
            bucket_id=command.bucket_id,
            event_type=BucketEventType.BUCKET_ARCHIVED,
            occurred_at=occurred_at,
            actor="bucket-maintenance",
            object_type=BucketEventObjectType.BUCKET,
            object_id=command.bucket_id,
            payload_version=_ARCHIVE_PAYLOAD_VERSION,
            payload=payload,
        )
        # The soft tombstone's own storage span already closed, so the
        # active-bucket session reverted to whatever it was beforehand
        # (typically a different, still-live profile). Binding the event
        # write to its OWN target-bucket session — the same span
        # ``delete_profile_with_lifecycle_span`` just used — keeps the
        # storage-runtime route consistent with the bucket the event
        # repository is about to open.
        with profile_storage_session(command.bucket_id):
            repository = self._event_repository or self._event_repository_for_bucket(command.bucket_id)
            repository.save(append_bucket_event(repository.load(), event))
        return ArchiveBucketResult(bucket_id=command.bucket_id, label=label, occurred_at=occurred_at)

    def restore(self, command: RestoreBucketCommand) -> RestoreBucketResult:
        """Restore one bucket under its canonical mutation lock."""
        from ...core.config import load_settings

        settings = load_settings()
        with self._mutation_target_lock(
            root=settings.cadrumo_local_storage_root,
            bucket_id=command.bucket_id,
            wait_seconds=settings.cadrumo_file_lock_timeout_s,
        ):
            return self._restore_locked(command)

    def _restore_locked(self, command: RestoreBucketCommand) -> RestoreBucketResult:
        """Bring the archived bucket identified by ``command.bucket_id`` back to active.

        Composes :func:`~application.user_profile.reactivate_profile_with_lifecycle_span`
        — the symmetric inverse of the soft tombstone :meth:`archive` composes.
        Refuses when the target is not currently tombstoned (i.e. was never
        archived, or is already active), surfaced by
        :class:`~domain.user_profile.ProfileNotFoundError` from the
        underlying lifecycle service.

        The ``BUCKET_RESTORED`` event lands in the restored bucket's OWN
        event history, mirroring :meth:`archive`'s binding.

        Returns:
            :class:`RestoreBucketResult`: The result of the restore operation.
        """
        from ...domain.user_profile import ProfileNotFoundError

        pointer = read_profile_bucket_by_id(command.bucket_id)
        if pointer is None:
            raise ProfileNotFoundError(
                translated_message="application.user_profile.errors.no_active_profile_selected",
                context={"bucket_id": command.bucket_id},
            )
        if pointer.status is not UserProfileStatus.TOMBSTONED:
            raise BucketRestoreRefusedError(
                translated_message="application.bucket_maintenance.errors.restore_not_archived",
                context={"bucket_id": command.bucket_id},
            )
        label = pointer.label
        reactivate_profile_with_lifecycle_span(command.bucket_id)
        occurred_at = now()
        payload = {"label": label}
        event = BucketEvent(
            event_id=derive_bucket_event_id(
                bucket_id=command.bucket_id,
                event_type=BucketEventType.BUCKET_RESTORED,
                occurred_at=occurred_at,
                actor="bucket-maintenance",
                object_type=BucketEventObjectType.BUCKET,
                object_id=command.bucket_id,
                payload=payload,
            ),
            bucket_id=command.bucket_id,
            event_type=BucketEventType.BUCKET_RESTORED,
            occurred_at=occurred_at,
            actor="bucket-maintenance",
            object_type=BucketEventObjectType.BUCKET,
            object_id=command.bucket_id,
            payload_version=_RESTORE_PAYLOAD_VERSION,
            payload=payload,
        )
        # Mirrors ``archive``'s own-session binding: the reactivation span
        # already closed, so re-open one scoped to the target bucket
        # before the event-history repository resolves its storage route.
        with profile_storage_session(command.bucket_id):
            repository = self._event_repository or self._event_repository_for_bucket(command.bucket_id)
            repository.save(append_bucket_event(repository.load(), event))
        return RestoreBucketResult(bucket_id=command.bucket_id, label=label, occurred_at=occurred_at)

    @staticmethod
    def _assess_retention_floor(bucket_id: str) -> RetentionFloorAssessment:
        """Assess the target bucket's filed records against the legal retention floor.

        Opens a storage session scoped to ``bucket_id`` (the target is never the
        active bucket, so its master-key session is activated the same way the
        export path activates it) and reads the encrypted filing catalogue, then
        delegates the pure floor evaluation to
        :func:`~domain.retention.assess_retention_floor`.
        """
        from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
        from ...domain.retention import assess_retention_floor

        with profile_storage_session(bucket_id):
            filing_records = tuple(ModeloRecordCatalogueRepository(bucket_id=bucket_id).load())
        return assess_retention_floor(filing_records, as_of=now())

    @staticmethod
    def _enforce_retention_floor(
        command: DeleteBucketCommand,
        assessment: RetentionFloorAssessment,
    ) -> bool:
        """Refuse the erase when records are still retained, unless overridden.

        Returns whether a still-retained record was erased under the explicit
        legal-retention override. A record inside its window is erasable only
        when the operator both acknowledges the override AND supplies a
        non-empty reason; an acknowledgement without a reason is not a valid
        override and the erase is refused.
        """
        if not assessment.blocks_erase:
            return False
        reason = (command.retention_override_reason or "").strip()
        override_valid = command.acknowledge_retention_override and bool(reason)
        if override_valid:
            return True
        from ...domain.retention import RetentionFloorError

        safe_date = assessment.latest_safe_erase_date
        raise RetentionFloorError(
            context={
                "bucket_id": command.bucket_id,
                "retained_record_count": len(assessment.retained),
                "earliest_safe_erase_date": safe_date.date().isoformat() if safe_date is not None else "",
            },
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
        policy; not yet implemented.
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

    def disk_usage(self, command: DiskUsageBucketCommand) -> DiskUsageBucketResult:
        """Measure ``command.bucket_id``'s on-disk footprint and return a :class:`DiskUsageBucketResult`.

        Walks the bucket's fixed directory layout
        (:func:`~adapters.persistence.storage.bucket.bucket_paths`) and
        sums regular-file byte sizes via ``os.stat`` — plain filesystem
        metadata, never decrypted content. This is the same non-active-safe
        posture :meth:`browse` and
        :func:`~application.bucket_maintenance.preview_discard_sandbox`
        already rely on: no master key or active-bucket session is opened, so
        a non-active (even archived) bucket can be measured. Read-only; emits
        no bucket event.

        Returns:
            :class:`DiskUsageBucketResult` reporting the total byte count and
            a per-subdirectory (``db``, ``blobs``, ``audit``) breakdown, plus
            the bucket's own manifest file folded into the ``db`` row (the
            manifest sits directly under the bucket directory, not in a
            fixed subdirectory of its own).
        """
        from ...adapters.persistence.storage.bucket import bucket_paths, manifest_path
        from ...core.config import load_settings

        paths = bucket_paths(load_settings().cadrumo_local_storage_root, command.bucket_id)
        manifest = manifest_path(paths)
        subdir_specs = (
            (BUCKET_DB_DIRNAME, paths.db_dir, (manifest,)),
            (BUCKET_BLOBS_DIRNAME, paths.blobs_dir, ()),
            (BUCKET_AUDIT_DIRNAME, paths.audit_dir, ()),
        )
        rows: list[BucketDiskUsageSubdirRow] = []
        total_bytes = 0
        for name, directory, extra_files in subdir_specs:
            subdir_bytes, subdir_count = _directory_byte_total(directory)
            for extra in extra_files:
                if extra.is_file():
                    subdir_bytes += extra.stat().st_size
                    subdir_count += 1
            rows.append(BucketDiskUsageSubdirRow(subdir=name, total_bytes=subdir_bytes, file_count=subdir_count))
            total_bytes += subdir_bytes
        return DiskUsageBucketResult(bucket_id=command.bucket_id, total_bytes=total_bytes, subdirs=tuple(rows))

    def export(self, command: ExportBucketCommand) -> ExportBucketResult:
        """Write a sealed bucket archive for ``command.bucket_id``.

        The method composes the existing profile portable-bundle serializer,
        :func:`compute_manifest_digest`, sealed-archive writer, active bucket
        DEK, and bucket-event history. It does not reimplement profile export
        logic. When a recovery passphrase is supplied, the payload is sealed
        under a passphrase-derived key and the archive carries a small
        recovery-wrap salt member; otherwise the currently active bucket DEK
        seals the payload for same-host backup.

        Returns:
            An :class:`ExportBucketResult` describing the written sealed archive.
        """
        from ...adapters.persistence.storage.bucket import (
            ExportArchiveHeader,
            bucket_paths,
            read_manifest,
            write_sealed_archive,
        )
        from ...adapters.persistence.storage.crypto import encrypt_record
        from ...adapters.persistence.storage.master_key import (
            ARGON2_MEMORY_COST_KIB,
            ARGON2_PARALLELISM,
            ARGON2_TIME_COST,
            derive_kek_with_params,
            get_active_master_key,
        )
        from ...core.config import load_settings

        pointer = read_profile_bucket_by_id(command.bucket_id)
        if pointer is None:
            from ...domain.user_profile import ProfileNotFoundError

            raise ProfileNotFoundError(
                translated_message="application.user_profile.errors.no_active_profile_selected",
                context={"bucket_id": command.bucket_id},
            )

        with profile_storage_session(command.bucket_id):
            # The sealed archive is the full-custody recovery transport: it is
            # AEAD-encrypted at rest, so it carries every durable secure-object
            # store (evidence bytes, cross-period calc inputs, the audit trail,
            # the live captures), and the export fails closed if any populated
            # carried namespace is uncovered.
            bundle = serialize_profile_bundle(
                bucket_id=command.bucket_id,
                custody_profile=StorageCustodyProfile.FULL,
            )
            manifest = read_manifest(bucket_paths(load_settings().cadrumo_local_storage_root, command.bucket_id))
            manifest_digest = compute_manifest_digest(manifest)
            occurred_at = now()
            recovery_wrap_bytes: bytes | None = None
            if command.recovery_wrap_passphrase is None:
                sealing_key = get_active_master_key()
            else:
                # Seal the exported bucket under a password KDF (Argon2id), not a
                # bare HKDF pass: a recovery-passphrase archive may leave the host,
                # and Argon2id's work factor is what makes an offline brute force of
                # the operator-chosen passphrase infeasible. The Argon2 parameters
                # ride in the recovery-wrap member so the importer can reproduce the
                # derivation.
                salt = secrets.token_bytes(_RECOVERY_WRAP_SALT_BYTES)
                recovery_wrap_bytes = _recovery_wrap_bytes(
                    salt,
                    memory_cost=ARGON2_MEMORY_COST_KIB,
                    time_cost=ARGON2_TIME_COST,
                    parallelism=ARGON2_PARALLELISM,
                )
                sealing_key = derive_kek_with_params(
                    command.recovery_wrap_passphrase.encode(UTF_8_ENCODING),
                    salt,
                    memory_cost=ARGON2_MEMORY_COST_KIB,
                    time_cost=ARGON2_TIME_COST,
                    parallelism=ARGON2_PARALLELISM,
                )
            payload = bundle.model_dump_json().encode(UTF_8_ENCODING)
            encrypted = encrypt_record(
                payload,
                key=sealing_key,
                associated_data=_archive_associated_data(command.bucket_id, manifest_digest),
            )
            header = ExportArchiveHeader(
                product=PRODUCT_IDENTITY.python_package,
                bucket_id=command.bucket_id,
                manifest_digest=manifest_digest,
                recovery_wrap_present=recovery_wrap_passphrase_present(command),
                archive_schema_version=_ARCHIVE_SCHEMA_VERSION,
                created_at=occurred_at,
            )
            command.output_path.parent.mkdir(parents=True, exist_ok=True)
            write_sealed_archive(
                command.output_path,
                header=header,
                payload_envelope_bytes=encrypted.to_wire(),
                recovery_wrap_bytes=recovery_wrap_bytes,
            )
            self._append_event(
                bucket_id=command.bucket_id,
                event_type=BucketEventType.BUCKET_EXPORTED,
                object_id=command.bucket_id,
                occurred_at=occurred_at,
                payload_version=_EXPORT_PAYLOAD_VERSION,
                payload={
                    "output_path": command.output_path.name,
                    "manifest_digest": manifest_digest,
                    "archive_schema_version": str(_ARCHIVE_SCHEMA_VERSION),
                    "recovery_wrap_present": str(header.recovery_wrap_present).lower(),
                },
            )
        return ExportBucketResult(
            bucket_id=command.bucket_id,
            output_path=command.output_path,
            manifest_digest=manifest_digest,
            recovery_wrap_present=command.recovery_wrap_passphrase is not None,
            occurred_at=occurred_at,
        )

    def import_(self, command: ImportBucketCommand) -> ImportBucketResult:
        """Import a sealed bucket archive through the profile bundle service.

        Archives with a recovery-wrap member require the matching passphrase.
        Archives without one are same-host backups and require the active bucket
        DEK to match the archive payload. New buckets are provisioned through
        the canonical profile create span before the
        :class:`~domain.user_profile.UserProfilePortableExport` payload is
        restored. The archive header's manifest digest is authenticated through
        AEAD associated data during decryption; it is not recomputed against the
        imported host manifest.

        Returns:
            An :class:`ImportBucketResult` describing the restored bucket.
        """
        from ...adapters.persistence.storage.bucket import read_sealed_archive
        from ...adapters.persistence.storage.crypto import (
            EncryptedBlob,
            decrypt_record,
        )
        from ...adapters.persistence.storage.master_key import derive_kek_with_params, get_active_master_key

        contents = read_sealed_archive(command.source_path)
        header = contents.header
        ensure_archive_schema_supported(header.archive_schema_version)
        existing = read_profile_bucket_by_id(header.bucket_id)
        if existing is not None and not command.force_replace:
            raise BucketImportError(
                translated_message="application.bucket_maintenance.errors.import_bucket_collision",
                context={"bucket_id": header.bucket_id},
            )
        if header.recovery_wrap_present:
            if command.recovery_wrap_passphrase is None:
                raise BucketImportError(
                    translated_message="application.bucket_maintenance.errors.import_recovery_passphrase_required",
                    context={"bucket_id": header.bucket_id},
                )
            if contents.recovery_wrap_bytes is None:
                raise BucketImportError(
                    translated_message="application.bucket_maintenance.errors.import_recovery_wrap_missing",
                    context={"bucket_id": header.bucket_id},
                )
            recovery_kdf = _recovery_wrap_kdf(contents.recovery_wrap_bytes)
            sealing_key = derive_kek_with_params(
                command.recovery_wrap_passphrase.encode(UTF_8_ENCODING),
                recovery_kdf.salt,
                memory_cost=recovery_kdf.memory_cost,
                time_cost=recovery_kdf.time_cost,
                parallelism=recovery_kdf.parallelism,
            )
        else:
            sealing_key = get_active_master_key()

        try:
            decrypted = decrypt_record(
                EncryptedBlob.from_wire(contents.payload_envelope_bytes),
                key=sealing_key,
                associated_data=_archive_associated_data(header.bucket_id, header.manifest_digest),
            )
        except Exception as exc:
            raise BucketImportError(
                translated_message="application.bucket_maintenance.errors.import_payload_invalid",
                context={"bucket_id": header.bucket_id, "error": str(exc)},
            ) from exc

        try:
            bundle = validate_bundle_payload(decrypted)
        except UnsupportedBundleSchemaVersionError as exc:
            raise BucketImportError(
                translated_message="application.user_profile.errors.unsupported_bundle_schema_version",
                context=exc.context,
            ) from exc
        except Exception as exc:
            raise BucketImportError(
                translated_message="application.bucket_maintenance.errors.import_payload_invalid",
                context={"bucket_id": header.bucket_id, "error": str(exc)},
            ) from exc

        self._validate_imported_profile_filing_baseline(bundle)
        # Recovery is same-id: the bucket is provisioned under the bundle's
        # profile_id and the carry is restored under header.bucket_id, and the
        # bucket-local object keys embed that id. If a (hand-built or tampered)
        # archive's profile_id and header.bucket_id diverge, the provision and the
        # restore would target different ids and every bucket-local row would be
        # written under a stale key and become unreadable; fail closed instead.
        if bundle.profile.profile_id != header.bucket_id:
            raise BucketImportError(
                translated_message="application.bucket_maintenance.errors.import_payload_invalid",
                context={"bucket_id": header.bucket_id, "profile_id": bundle.profile.profile_id},
            )
        if existing is None:
            self._provision_imported_bucket(bundle)
        with profile_storage_session(header.bucket_id):
            deserialize_profile_bundle(bundle, target_bucket_id=header.bucket_id)
            occurred_at = now()
            self._append_event(
                bucket_id=header.bucket_id,
                event_type=BucketEventType.BUCKET_IMPORTED,
                object_id=header.bucket_id,
                occurred_at=occurred_at,
                payload_version=_IMPORT_PAYLOAD_VERSION,
                payload={
                    "source_path": command.source_path.name,
                    "manifest_digest": header.manifest_digest,
                    "archive_schema_version": str(header.archive_schema_version),
                    "force_replace": str(command.force_replace).lower(),
                },
            )
        return ImportBucketResult(
            bucket_id=header.bucket_id,
            manifest_digest=header.manifest_digest,
            archive_schema_version=header.archive_schema_version,
            occurred_at=occurred_at,
        )

    def inspect(self, command: InspectBucketArchiveCommand) -> InspectBucketArchiveResult:
        """Read a sealed bucket archive's header without decrypting or restoring it.

        Composes :func:`read_sealed_archive` (the same reader ``import_`` uses
        for layout and header validation) with the on-disk file size. No
        session is opened, no key is required, and no bucket state is
        written or read — this is a pure inspection of the archive file
        itself, so an operator can confirm a backup's identity, age, and
        recovery-wrap presence before deciding whether and how to restore
        it.

        Returns:
            An :class:`InspectBucketArchiveResult` describing the archive header.
        """
        from ...adapters.persistence.storage.bucket import read_sealed_archive

        contents = read_sealed_archive(command.source_path)
        header = contents.header
        size_bytes = command.source_path.stat().st_size
        return InspectBucketArchiveResult(
            bucket_id=header.bucket_id,
            manifest_digest=header.manifest_digest,
            recovery_wrap_present=header.recovery_wrap_present,
            archive_schema_version=header.archive_schema_version,
            created_at=header.created_at,
            size_bytes=size_bytes,
        )

    def _append_event(
        self,
        *,
        bucket_id: str,
        event_type: BucketEventType,
        object_id: str,
        occurred_at: datetime,
        payload_version: int,
        payload: dict[str, str],
    ) -> None:
        event = BucketEvent(
            event_id=derive_bucket_event_id(
                bucket_id=bucket_id,
                event_type=event_type,
                occurred_at=occurred_at,
                actor="bucket-maintenance",
                object_type=BucketEventObjectType.BUCKET,
                object_id=object_id,
                payload=payload,
            ),
            bucket_id=bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor="bucket-maintenance",
            object_type=BucketEventObjectType.BUCKET,
            object_id=object_id,
            payload_version=payload_version,
            payload=payload,
        )
        repository = self._event_repository or self._event_repository_for_bucket(bucket_id)
        repository.save(append_bucket_event(repository.load(), event))

    @staticmethod
    def _validate_imported_profile_filing_baseline(bundle: UserProfilePortableExport) -> None:
        missing_flags = missing_filing_baseline_flags(record_to_path_values(bundle.profile))
        if not missing_flags:
            return
        raise BucketImportError(
            translated_message="application.bucket_maintenance.errors.import_missing_filing_baseline",
            context={"missing_flags": _format_missing_flags(missing_flags)},
        )

    @staticmethod
    def _provision_imported_bucket(bundle: UserProfilePortableExport) -> None:
        from ..workflow import workflow_state_repository

        profile_id = bundle.profile.profile_id
        with profile_create_storage_span(profile_id) as routing_profile_id:
            workflow_state_repository().update(
                lambda current: register_active_profile(
                    current,
                    profile_id=profile_id,
                    display_name=bundle.profile.display_name,
                    facts=bundle.profile.facts,
                    enforce_unique_tax_id=False,
                    routing_profile_id=routing_profile_id,
                ),
            )


def recovery_wrap_passphrase_present(command: ExportBucketCommand) -> bool:
    """Return whether ``command`` requests a recovery-passphrase archive."""
    return command.recovery_wrap_passphrase is not None


def _archive_associated_data(bucket_id: str, manifest_digest: str) -> bytes:
    return f"{PRODUCT_IDENTITY.python_package}.bucket-maintenance.archive.v3:{bucket_id}:{manifest_digest}".encode()


def _format_missing_flags(missing_flags: tuple[str, ...]) -> str:
    return " ".join(f"--{flag}" for flag in missing_flags)


class _RecoveryWrapKdf(NamedTuple):
    """Argon2id parameters read back from a sealed archive's recovery-wrap member."""

    salt: bytes
    memory_cost: int
    time_cost: int
    parallelism: int


def _recovery_wrap_bytes(salt: bytes, *, memory_cost: int, time_cost: int, parallelism: int) -> bytes:
    return json.dumps(
        {
            "kdf": "argon2id",
            "salt_b64": base64.b64encode(salt).decode("ascii"),
            "memory_cost": memory_cost,
            "time_cost": time_cost,
            "parallelism": parallelism,
        },
    ).encode(UTF_8_ENCODING)


def _recovery_wrap_kdf(payload: bytes) -> _RecoveryWrapKdf:
    try:
        raw = json.loads(payload.decode(UTF_8_ENCODING))
        if raw.get("kdf") != "argon2id":
            raise ValueError("unsupported recovery-wrap kdf")
        salt = base64.b64decode(raw["salt_b64"].encode("ascii"), validate=True)
        memory_cost = int(raw["memory_cost"])
        time_cost = int(raw["time_cost"])
        parallelism = int(raw["parallelism"])
        if memory_cost <= 0 or time_cost <= 0 or parallelism <= 0:
            raise ValueError("non-positive argon2 parameter")
        return _RecoveryWrapKdf(
            salt=salt,
            memory_cost=memory_cost,
            time_cost=time_cost,
            parallelism=parallelism,
        )
    except Exception as exc:
        raise BucketImportError(
            translated_message="application.bucket_maintenance.errors.import_recovery_wrap_invalid",
        ) from exc
