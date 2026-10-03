"""Registered-executor conformance scenarios for the profile archive family."""

from __future__ import annotations

from ...adapters.persistence.profile.buckets import build_bucket_event_history_repository
from ...adapters.persistence.storage.bucket.sealed_archive_writer import CADRUMO_BUCKET_BUNDLE_SUFFIX
from ...application.user_profile.archive_operation import (
    PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID,
    PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID,
    PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID,
    ProfileArchiveExportProjection,
    ProfileArchiveExportReceiptSnapshot,
    ProfileArchiveExportRequest,
    ProfileArchivePushRequest,
    ProfileArchiveReconcileProjection,
    ProfileArchiveReconcileRequest,
)
from ...application.user_profile.capsule_archive import inspect_profile_capsule_archive
from ...application.user_profile.custody_ports import profile_capsule_archive_schema_version
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.buckets.event import BucketEventType
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)


def _prepare_export(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile_id = context.profile_id
    # The sealed-container writer refuses any other suffix
    # (adapters/persistence/storage/bucket/sealed_archive_writer.py:120).
    target = context.input_root / ("profile-archive" + CADRUMO_BUCKET_BUNDLE_SUFFIX)
    assert not target.exists()
    schema_version = profile_capsule_archive_schema_version()

    def verify(outcome: ConformanceOutcome) -> None:
        del outcome
        # The sealed header names the exported profile without any key.
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
                # Registration never enrols recovery
                # (application/user_profile/registration.py:163).
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
        # With no prepared export journal there is nothing to finalise, so no
        # completion event may appear.
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


# Each definition is single-phase and publishes its own id before any port
# runs (application/user_profile/archive_operation.py:301).
PROFILE_ARCHIVE_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        # The fenced writer receipt settles UPDATED (archive_operation.py:265-266).
        RegisteredExecutorConformanceCase(
            PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (PROFILE_ARCHIVE_EXPORT_OPERATION_DEFINITION_ID,),
        ),
        # Google export defaults on, so the push reaches the Drive root
        # precondition before any provider handoff
        # (entrypoints/profile_archive_operation_composition.py:58-60,
        # adapters/outbound/storage/factory.py:329-339); no handoff means NONE.
        RegisteredExecutorConformanceCase(
            PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (PROFILE_ARCHIVE_PUSH_OPERATION_DEFINITION_ID,),
            expected_refusal_ref="REFUSED_OUTBOUND_STORAGE_VALIDATION",
        ),
        # No journal, no confirmed write (archive_operation.py:267).
        RegisteredExecutorConformanceCase(
            PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (PROFILE_ARCHIVE_RECONCILE_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)
