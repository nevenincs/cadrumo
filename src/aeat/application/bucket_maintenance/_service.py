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

import base64
import json
import secrets
from typing import TYPE_CHECKING, NamedTuple

from ...core.external_constants import UTF_8_ENCODING
from ...core.time import now
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    BucketImportError,
    append_bucket_event,
    derive_bucket_event_id,
)
from ..user_profile import (
    delete_profile_with_lifecycle_span,
    deserialize_profile_bundle,
    profile_create_storage_span,
    profile_storage_session,
    remove_profile_bucket_directory,
    rename_profile,
    serialize_profile_bundle,
)
from ..workflow import read_profile_bucket_by_id
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

if TYPE_CHECKING:  # pragma: no cover - import-cycle guard
    from datetime import datetime

    from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
    from ...domain.user_profile import UserProfilePortableExport


_RENAME_PAYLOAD_VERSION = 1
_DELETE_PAYLOAD_VERSION = 1
_EXPORT_PAYLOAD_VERSION = 1
_IMPORT_PAYLOAD_VERSION = 1
_ARCHIVE_SCHEMA_VERSION = 1
_RECOVERY_WRAP_SALT_BYTES = 16


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

    def export(self, command: ExportBucketCommand) -> ExportBucketResult:
        """Write a sealed bucket archive for ``command.bucket_id``.

        The method composes the existing profile portable-bundle serializer,
        sealed-archive writer, active bucket DEK, and bucket-event history.
        It does not reimplement profile export logic. When a recovery
        passphrase is supplied, the payload is sealed under a passphrase-derived
        key and the archive carries a small recovery-wrap salt member; otherwise
        the currently active bucket DEK seals the payload for same-host backup.

        Returns:
            An :class:`ExportBucketResult` describing the written sealed archive.
        """
        from ...adapters.persistence.storage import get_active_master_key
        from ...adapters.persistence.storage.bucket import ExportArchiveHeader, bucket_paths, read_manifest
        from ...adapters.persistence.storage.bucket._sealed_archive_writer import write_sealed_archive
        from ...adapters.persistence.storage.crypto import encrypt_record
        from ...adapters.persistence.storage.master_key import (
            ARGON2_MEMORY_COST_KIB,
            ARGON2_PARALLELISM,
            ARGON2_TIME_COST,
            derive_kek_with_params,
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
            bundle = serialize_profile_bundle(bucket_id=command.bucket_id)
            manifest = read_manifest(bucket_paths(load_settings().aeat_local_storage_root, command.bucket_id))
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
                    "output_path": str(command.output_path),
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
        the canonical profile create span before the bundle data is restored.

        Returns:
            An :class:`ImportBucketResult` describing the restored bucket.
        """
        from ...adapters.persistence.storage import get_active_master_key
        from ...adapters.persistence.storage.bucket._sealed_archive_reader import read_sealed_archive
        from ...adapters.persistence.storage.crypto import EncryptedBlob, decrypt_record
        from ...adapters.persistence.storage.master_key import derive_kek_with_params
        from ...domain.user_profile import UserProfilePortableExport

        contents = read_sealed_archive(command.source_path)
        header = contents.header
        if header.archive_schema_version != _ARCHIVE_SCHEMA_VERSION:
            raise BucketImportError(
                translated_message="application.bucket_maintenance.errors.unsupported_archive_schema_version",
                context={"archive_schema_version": str(header.archive_schema_version)},
            )
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
            bundle = UserProfilePortableExport.model_validate_json(decrypted)
        except Exception as exc:
            raise BucketImportError(
                translated_message="application.bucket_maintenance.errors.import_payload_invalid",
                context={"bucket_id": header.bucket_id},
            ) from exc

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
                    "source_path": str(command.source_path),
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
    def _provision_imported_bucket(bundle: UserProfilePortableExport) -> None:
        from ..user_profile import register_active_profile
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
    return f"aeat.bucket-maintenance.archive.v1:{bucket_id}:{manifest_digest}".encode()


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
