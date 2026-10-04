"""Registered-executor conformance scenarios for the profile archive family."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from ...adapters.outbound.google.records import DriveConfig
from ...adapters.outbound.google.session_store import save_drive_config
from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository, build_bucket_event_history_repository
from ...adapters.persistence.storage.bucket.sealed_archive_writer import CADRUMO_BUCKET_BUNDLE_SUFFIX
from ...adapters.persistence.storage.secure_object_namespaces import GOOGLE_DRIVE_CONFIG_NAMESPACE
from ...application.bucket_event_projection import BucketEventProjection
from ...application.user_profile.archive_operation import (
    PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID,
    PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID,
    PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID,
    ArchiveReconciledExport,
    ProfileArchiveExportProjection,
    ProfileArchiveExportReceiptSnapshot,
    ProfileArchiveExportRequest,
    ProfileArchivePushProjection,
    ProfileArchivePushRequest,
    ProfileArchiveReconcileProjection,
    ProfileArchiveReconcileRequest,
)
from ...application.user_profile.bundle_export_contracts import (
    ProfileBundleExportPurpose,
    ProfileBundleExportTarget,
    ProfileBundleExportTransport,
)
from ...application.user_profile.bundle_export_operation import (
    ProfileBundleExportJournalRepository,
    ProfileBundleExportOperation,
    ProfileBundleExportOperationStatus,
    derive_export_operation_id,
    profile_export_staged_path,
)
from ...application.user_profile.capsule_archive import inspect_profile_capsule_archive, read_profile_capsule_archive
from ...application.user_profile.custody_ports import profile_capsule_archive_schema_version
from ...application.user_profile.history_contracts import ProfileHistoryProjection, ProfileHistoryRequest
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ...domain.buckets.event_repository import build_bucket_event
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)


def _prepare_export(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile_id = context.profile_id
    target = context.input_root / ("profile-archive" + CADRUMO_BUCKET_BUNDLE_SUFFIX)
    assert not target.exists()
    schema_version = profile_capsule_archive_schema_version()

    def verify(outcome: ConformanceOutcome) -> None:
        del outcome
        header = inspect_profile_capsule_archive(target)
        assert header.bucket_id == str(profile_id)
        assert header.archive_schema_version == schema_version

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(profile_id)),
        request=ProfileArchiveExportRequest(profile_id=profile_id, target=target),
        expected_result=ProfileArchiveExportProjection(
            profile_id=profile_id,
            receipt=ProfileArchiveExportReceiptSnapshot(
                bucket_id=str(profile_id),
                target=str(target),
                archive_schema_version=schema_version,
                recovery_enrolled=False,
            ),
        ),
        verify=verify,
    )


def _prepare_push(context: ConformanceFamilyContext) -> ConformancePreparation:
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=ProfileArchivePushRequest(profile_id=context.profile_id),
    )


def _exported_event_count(profile_id: str) -> int:
    catalogue = build_bucket_event_history_repository(bucket_id=profile_id).load()
    return len(catalogue.for_bucket(profile_id, event_types=(BucketEventType.PROFILE_EXPORTED,)))


def _prepare_reconcile(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile_id = context.profile_id
    exported_before = _exported_event_count(str(profile_id))

    def verify(outcome: ConformanceOutcome) -> None:
        del outcome
        assert _exported_event_count(str(profile_id)) == exported_before

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(profile_id)),
        request=ProfileArchiveReconcileRequest(profile_id=profile_id),
        expected_result=ProfileArchiveReconcileProjection(profile_id=profile_id, reconciled=(), failed=()),
        verify=verify,
    )


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    definition_id = context.definition.definition_id
    if definition_id == PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID:
        return _prepare_export(context)
    if definition_id == PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID:
        return _prepare_push(context)
    if definition_id == PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID:
        return _prepare_reconcile(context)
    raise AssertionError(f"no profile archive conformance scenario for {definition_id}")


PROFILE_ARCHIVE_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID,),
            expected_refusal_ref="REFUSED_OUTBOUND_STORAGE_VALIDATION",
        ),
        RegisteredExecutorConformanceCase(
            PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)


def _retained_archive_prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    definition_id = context.definition.definition_id
    if definition_id == "profile.archive.export":
        target = context.input_root / "sealed-profile.cadrumo-bucket.tar.gz"

        def verify(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(ProfileArchiveExportProjection)
            assert result.profile_id == context.profile_id and result.receipt.target == str(target)
            assert result.receipt.bucket_id == profile and result.receipt.archive_schema_version == 4
            inspection = inspect_profile_capsule_archive(target)
            assert inspection.bucket_id == profile and inspection.archive_schema_version == 4
            source = read_profile_capsule_archive(target)
            assert source.password_envelope.profile_id == context.profile_id
            assert target.stat().st_size > 4096

        return ConformancePreparation(
            profile_operation_subject(profile),
            ProfileArchiveExportRequest(profile_id=context.profile_id, target=target),
            verify=verify,
        )
    if definition_id == "profile.archive.push":
        save_drive_config(profile, DriveConfig(root_folder_id="synthetic-mirror-root"))

        def verify(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(ProfileArchivePushProjection)
            report = result.report
            assert result.profile_id == context.profile_id and report.profile == profile
            assert report.dry_run and report.root_folder_id == "synthetic-mirror-root"
            assert report.pushed_total == report.failed_total == report.manifest_pushed_total == 0
            assert report.skipped_total == 1
            assert tuple((row.namespace, row.count) for row in report.skipped_by_namespace) == (
                (GOOGLE_DRIVE_CONFIG_NAMESPACE.namespace, 1),
            )

        return ConformancePreparation(
            profile_operation_subject(profile),
            ProfileArchivePushRequest(
                profile_id=context.profile_id, namespace_filter=GOOGLE_DRIVE_CONFIG_NAMESPACE.namespace, dry_run=True
            ),
            verify=verify,
        )
    if definition_id == "profile.archive.reconcile":
        destination = context.input_root / "unpublished-profile.json"
        staged = profile_export_staged_path(destination, process_id=os.getpid(), nonce="a" * 8)
        staged.write_bytes(b"synthetic unpublished bundle")
        export_target = ProfileBundleExportTarget(destination=destination)
        instant = datetime(2026, 4, 1, tzinfo=UTC)
        purpose = ProfileBundleExportPurpose.PORTABLE_TRANSFER
        journal = ProfileBundleExportJournalRepository()
        pending = ProfileBundleExportOperation(
            operation_id=derive_export_operation_id(
                profile_id=profile, target_identity=export_target.identity, purpose=purpose
            ),
            status=ProfileBundleExportOperationStatus.PREPARED,
            profile_id=profile,
            display_name="synthetic",
            target_identity=export_target.identity,
            destination=str(destination),
            staged_path=str(staged),
            content_sha256=sha256_hex(staged.read_bytes()),
            purpose=purpose,
            transport=ProfileBundleExportTransport.CLEARTEXT_LOCAL,
            bundle_schema_version=1,
            data_categories=("profile",),
            started_at=instant,
            updated_at=instant,
            event_occurred_at=instant,
        )
        journal.save(pending)

        def verify(outcome: ConformanceOutcome) -> None:
            assert not staged.exists() and (not destination.exists())
            assert not journal.path_for(pending.operation_id).exists()

        expected = ProfileArchiveReconcileProjection(
            profile_id=context.profile_id,
            reconciled=(
                ArchiveReconciledExport(
                    operation_id=pending.operation_id, destination=str(destination), purpose=purpose
                ),
            ),
            failed=(),
        )
        return ConformancePreparation(
            profile_operation_subject(profile),
            ProfileArchiveReconcileRequest(profile_id=context.profile_id),
            expected_result=expected,
            verify=verify,
        )
    if definition_id == "profile.history":
        repository = BucketEventHistoryRepository()
        selected = build_bucket_event(
            bucket_id=profile,
            event_type=BucketEventType.PROFILE_EXPORTED,
            object_type=BucketEventObjectType.PROFILE,
            object_id="selected-conformance-export",
            actor="conformance-history",
            payload={"synthetic": "selected"},
            payload_version=1,
            occurred_at=datetime(2026, 4, 1, tzinfo=UTC),
        )
        excluded = build_bucket_event(
            bucket_id=profile,
            event_type=BucketEventType.PROFILE_EXPORTED,
            object_type=BucketEventObjectType.PROFILE,
            object_id="excluded-conformance-export",
            actor="other-history",
            payload={"synthetic": "excluded"},
            payload_version=1,
            occurred_at=datetime(2026, 4, 2, tzinfo=UTC),
        )
        catalogue = repository.load()
        catalogue = catalogue.model_copy(
            update={"events": {**catalogue.events, selected.event_id: selected, excluded.event_id: excluded}}
        )
        repository.save(catalogue)
        request = ProfileHistoryRequest(
            profile_id=context.profile_id,
            event_types=(BucketEventType.PROFILE_EXPORTED,),
            actor="conformance-history",
            object_id=selected.object_id,
        )
        expected = ProfileHistoryProjection(
            profile_id=context.profile_id,
            event_types=request.event_types,
            actor=request.actor,
            object_id=request.object_id,
            event_count=1,
            events=(BucketEventProjection.from_event(selected),),
        )
        return ConformancePreparation(profile_operation_subject(profile), request, expected_result=expected)
    raise AssertionError(definition_id)


ARCHIVE_MATERIAL_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=tuple(
        RegisteredExecutorConformanceCase(
            definition_id,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED
            if definition_id in {"profile.archive.export", "profile.archive.reconcile"}
            else OperationEffect.NONE,
            (definition_id,),
        )
        for definition_id in (
            "profile.archive.export",
            "profile.archive.push",
            "profile.archive.reconcile",
            "profile.history",
        )
    ),
    prepare=_retained_archive_prepare,
)
