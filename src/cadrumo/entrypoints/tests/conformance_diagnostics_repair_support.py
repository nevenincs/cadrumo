"""Registered-executor conformance scenarios for the repair operations that run in a profile's worker.

The store the scenarios act on is the enrolled profile's own. The check and
the quarantine are given one sound row and one row whose ciphertext no longer
authenticates, and the reset is given saved progress to discard. The matrix
binds the connectivity probe's browser port to :data:`OBSERVED_SITE`, so that
scenario judges the report against an observation it did not take.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from uuid import UUID

from pydantic import AnyHttpUrl

from ...adapters.outbound.aeat.browser.site_health_records import SiteHealthEvidence, SiteHealthStatus
from ...adapters.persistence.storage.bucket.directory_layout import bucket_paths
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ...adapters.persistence.storage.secure_object_namespaces import (
    TEST_RUNTIME_PROFILE_NAMESPACE,
    TEST_SESSION_LIFECYCLE_NAMESPACE,
)
from ...application.diagnostics_repair_documents import (
    RepairConnectivityDocument,
    RepairConnectivityEvidenceDocument,
    RepairConnectivityStatusDocument,
    RepairIntegrityObjectsDocument,
    RepairQuarantineDocument,
    RepairResetProgressDocument,
)
from ...application.diagnostics_repair_operations import (
    CONNECTIVITY_PROBE_OPERATION_DEFINITION_ID,
    SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID,
    SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID,
    WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID,
    ConnectivityProbeRequest,
    SecureObjectsCheckRequest,
    SecureObjectsQuarantineRequest,
    WorkflowProgressResetRequest,
)
from ...application.workflow.persistence import workflow_state_repository
from ...application.workflow.state_models import WorkflowState
from ...core.errors.hierarchy import SiteHealthState
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.paths import effective_storage_root
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_SOUND_NAMESPACE = TEST_SESSION_LIFECYCLE_NAMESPACE.namespace
_TORN_NAMESPACE = TEST_RUNTIME_PROFILE_NAMESPACE.namespace
_SEEDED_PROGRESS_AT = datetime(2026, 4, 2, 9, 30, 11, tzinfo=UTC)
_OBSERVED_AT = datetime(2026, 4, 2, 9, 31, 0, tzinfo=UTC)

OBSERVED_SITE = SiteHealthStatus(
    state=SiteHealthState.MANTENIMIENTO,
    evidence=SiteHealthEvidence(
        url=AnyHttpUrl("https://probe.example.org/inicio"),
        http_status=503,
        html_fragment="<html>synthetic maintenance page</html>",
        detected_markers=("mantenimiento", "retry-after:120"),
    ),
    observed_at=_OBSERVED_AT,
    retry_after_seconds=120,
)
"""What the matrix's browser port observed: a synthetic maintenance page, never a live site."""


def observe_synthetic_site() -> SiteHealthStatus:
    """Answer the connectivity probe's port with :data:`OBSERVED_SITE`, starting no browser."""
    return OBSERVED_SITE


def _seed_a_sound_and_a_torn_row(profile_id: UUID) -> None:
    """Store two rows through the profile's own repository, then flip the last ciphertext byte of one."""
    repository = secure_object_repository_for_active_bucket()
    for definition in (TEST_SESSION_LIFECYCLE_NAMESPACE, TEST_RUNTIME_PROFILE_NAMESPACE):
        repository.save(
            namespace=definition.namespace,
            object_key=definition.object_key_grammar,
            classification=definition.sensitivity,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=f"synthetic-{definition.key}".encode(),
        )
    database = bucket_paths(effective_storage_root(), str(profile_id)).database_file
    with sqlite3.connect(database) as connection:
        row_id, payload = connection.execute(
            "SELECT id, payload FROM secure_objects WHERE namespace = ? ORDER BY id DESC LIMIT 1", (_TORN_NAMESPACE,)
        ).fetchone()
        connection.execute(
            "UPDATE secure_objects SET payload = ? WHERE id = ?", (payload[:-1] + bytes([payload[-1] ^ 0xFF]), row_id)
        )
    connection.close()


def _seeded_counts(document: RepairIntegrityObjectsDocument | RepairQuarantineDocument) -> dict[str, tuple[int, int]]:
    return {
        row.namespace: (row.readable, row.unreadable)
        for row in document.namespaces or ()
        if row.namespace in {_SOUND_NAMESPACE, _TORN_NAMESPACE}
    }


def _prepare_check(context: ConformanceFamilyContext) -> ConformancePreparation:
    _seed_a_sound_and_a_torn_row(context.profile_id)

    def verify(outcome: ConformanceOutcome) -> None:
        document = outcome.resolve_result(RepairIntegrityObjectsDocument)
        assert _seeded_counts(document) == {_SOUND_NAMESPACE: (1, 0), _TORN_NAMESPACE: (0, 1)}
        assert document.unreadable_total == 1
        assert document.readable_total == sum(row.readable for row in document.namespaces)
        assert (document.check.status, document.check.summary) == ("fail", "1 unreadable secure-object rows")

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=SecureObjectsCheckRequest(profile_id=context.profile_id),
        verify=verify,
    )


def _prepare_quarantine(context: ConformanceFamilyContext) -> ConformancePreparation:
    _seed_a_sound_and_a_torn_row(context.profile_id)

    def verify(outcome: ConformanceOutcome) -> None:
        document = outcome.resolve_result(RepairQuarantineDocument)
        assert document.dry_run is False
        assert _seeded_counts(document) == {_SOUND_NAMESPACE: (1, 0), _TORN_NAMESPACE: (0, 1)}
        assert document.unreadable_total == 1
        repository = secure_object_repository_for_active_bucket()
        assert repository.exists(_SOUND_NAMESPACE, TEST_SESSION_LIFECYCLE_NAMESPACE.object_key_grammar)
        assert not repository.exists(_TORN_NAMESPACE, TEST_RUNTIME_PROFILE_NAMESPACE.object_key_grammar)

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=SecureObjectsQuarantineRequest(profile_id=context.profile_id, dry_run=False),
        verify=verify,
    )


def _prepare_reset(context: ConformanceFamilyContext) -> ConformancePreparation:
    workflow_state_repository().save(WorkflowState(updated_at=_SEEDED_PROGRESS_AT))

    def verify(outcome: ConformanceOutcome) -> None:
        document = outcome.resolve_result(RepairResetProgressDocument)
        assert document.dry_run is False
        assert document.fingerprint is not None
        assert document.fingerprint.reason_class == "readable"
        assert document.fingerprint.recovered_bucket_id == str(context.profile_id)
        assert not secure_object_repository_for_active_bucket().exists("cadrumo.workflow", "state")

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=WorkflowProgressResetRequest(profile_id=context.profile_id, dry_run=False),
        verify=verify,
    )


def _prepare_connectivity(context: ConformanceFamilyContext) -> ConformancePreparation:
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=ConnectivityProbeRequest(profile_id=context.profile_id),
        expected_result=RepairConnectivityDocument(
            target="aeat_sede",
            status=RepairConnectivityStatusDocument(
                state="mantenimiento",
                evidence=RepairConnectivityEvidenceDocument(
                    # A result names a site by its origin: no path or query of a URL is written out.
                    url="https://probe.example.org",
                    http_status=503,
                    html_fragment="<html>synthetic maintenance page</html>",
                    detected_markers=("mantenimiento", "retry-after:120"),
                ),
                observed_at="2026-04-02T09:31:00Z",
                retry_after_seconds=120,
            ),
        ),
    )


_PREPARATIONS = {
    SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID: _prepare_check,
    SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID: _prepare_quarantine,
    WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID: _prepare_reset,
    CONNECTIVITY_PROBE_OPERATION_DEFINITION_ID: _prepare_connectivity,
}


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    prepare = _PREPARATIONS.get(context.definition.definition_id)
    if prepare is None:
        raise AssertionError(f"no repair conformance scenario for {context.definition.definition_id}")
    return prepare(context)


DIAGNOSTICS_REPAIR_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (SECURE_OBJECTS_CHECK_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (SECURE_OBJECTS_QUARANTINE_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (WORKFLOW_PROGRESS_RESET_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            CONNECTIVITY_PROBE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (CONNECTIVITY_PROBE_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)
