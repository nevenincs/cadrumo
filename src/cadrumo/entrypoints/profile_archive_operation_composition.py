"""Compose canonical archive services for one immutable authenticated worker."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from ..adapters.outbound.storage.factory import get_storage_provider, resolve_required_drive_root_folder_id
from ..adapters.outbound.storage.mirror_push import (
    AdmittedMirrorStorageProvider,
    build_profile_archive_push_report,
    push_secure_object_mirror_rows,
)
from ..adapters.outbound.storage.protocol import StorageProvider
from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..application.user_profile.archive_operation_ports import (
    ArchiveLocalWriter,
    ArchiveProviderHandoff,
    ProfileArchiveOperationPorts,
    ProfileArchivePushReport,
)
from ..application.user_profile.bundle_export import ProfileBundleExportReconciliation, reconcile_prepared_exports
from ..application.user_profile.capabilities import resolve_capability
from ..application.user_profile.capsule_archive import ProfileCapsuleArchiveReceipt, export_profile_capsule_archive
from ..application.user_profile.capsule_record import ProfileRecordStore
from ..application.user_profile.profile_record_repository import require_profile_record_session
from ..core.bucket_pointer import require_active_bucket_id
from ..core.capabilities import ServiceCapability
from ..core.config import load_settings
from ..domain.calculations.registry.authority import PinnedAuthorityOperation


def build_profile_archive_operation_ports(
    *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> ProfileArchiveOperationPorts:
    """Bind the selected published pin; resolve remote credentials only for push."""

    def require_profile() -> None:
        if require_active_bucket_id() != str(profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

    require_profile()

    def export(target: Path, *, write: ArchiveLocalWriter) -> ProfileCapsuleArchiveReceipt:
        require_profile()
        return export_profile_capsule_archive(profile_id=profile_id, target=target, write=write)

    def push(
        *, namespace_filter: str | None, limit: int | None, dry_run: bool, before_handoff: ArchiveProviderHandoff
    ) -> ProfileArchivePushReport:
        require_profile()
        settings = load_settings().model_copy(update={"cadrumo_storage_provider_kind": "google_drive"})
        session = require_profile_record_session(profile_id, profile_decode_context=operation.profile_decode_context())
        record = ProfileRecordStore(session=session).load().record
        if not resolve_capability(ServiceCapability.GOOGLE_EXPORT, profile_record=record, settings=settings).enabled:
            raise ProfileAccessRefusedError(AccessDenialCode.PROVIDER_REQUIRED)
        root_folder_id = resolve_required_drive_root_folder_id(profile=str(profile_id), settings=settings)

        def provider_factory() -> StorageProvider:
            require_profile()
            provider = get_storage_provider(settings=settings)
            require_profile()
            return provider

        repository = secure_object_repository_for_bucket(str(profile_id))
        result = push_secure_object_mirror_rows(
            provider=AdmittedMirrorStorageProvider(provider_factory, before_handoff),
            repository=repository,
            namespace_filter=namespace_filter,
            limit=limit,
            dry_run=dry_run,
        )
        return build_profile_archive_push_report(
            profile=str(profile_id),
            root_folder_id=root_folder_id,
            dry_run=dry_run,
            namespace_filter=namespace_filter,
            limit=limit,
            result=result,
        )

    def reconcile(*, write: ArchiveLocalWriter) -> ProfileBundleExportReconciliation:
        require_profile()
        repository = BucketEventHistoryRepository(
            objects=secure_object_repository_for_bucket(str(profile_id)), mutation_writer=write
        )
        return reconcile_prepared_exports(
            profile_decode_context=operation.profile_decode_context(),
            authorized_profile_id=str(profile_id),
            mutation_writer=write,
            event_repository=repository,
        )

    return ProfileArchiveOperationPorts(
        profile_id=profile_id, operation=operation, export=export, push=push, reconcile=reconcile
    )
