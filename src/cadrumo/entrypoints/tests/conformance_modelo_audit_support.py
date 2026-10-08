"""Registered-executor conformance scenarios for the Modelo audit operation family.

One evidence bundle is sealed through the production evidence service into
the profile's encrypted store, bound to a real work unit. The operations
supply no record loader, so every referenced record is unreachable: a check
reports the bundle INCOMPLETE and an export needs ``force_incomplete``.
"""

from __future__ import annotations

import hashlib
from zipfile import ZipFile

from ...application.evidence.models import (
    BundleVerificationState,
    EvidenceBundle,
    VerificationCheck,
)
from ...application.evidence.service import EvidenceBundleService
from ...application.modelo.audit_operation import (
    MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID,
    MODELO_AUDIT_READ_OPERATION_DEFINITION_ID,
    ModeloAuditCheckFindingSnapshot,
    ModeloAuditCheckReportSnapshot,
    ModeloAuditExportProjection,
    ModeloAuditExportRequest,
    ModeloAuditQueryBundle,
    ModeloAuditQueryProjection,
    ModeloAuditQueryRecord,
    ModeloAuditReadProjection,
    ModeloAuditReadRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.buckets.event import BucketEventObjectType
from ..modelo_audit_operation_composition import build_modelo_audit_operation_ports
from . import modelo_operation_test_support
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_RECORD_ID = "conformance-calculation-evidence"
_RECORD_PAYLOAD = b"synthetic conformance calculation evidence"
_NOTES = "synthetic conformance audit note"


def _seed_bundle(context: ConformanceFamilyContext) -> EvidenceBundle:
    unit = modelo_operation_test_support.seeded_modelo_work_unit(context.profile_id, operation=context.operation)
    ports = build_modelo_audit_operation_ports(profile_id=context.profile_id, operation=context.operation)
    return EvidenceBundleService(ports=ports.evidence).build(
        bucket_id=str(context.profile_id),
        work_unit_id=unit.work_unit_id,
        record_payloads={(BucketEventObjectType.CALCULATION_REVISION.value, _RECORD_ID): _RECORD_PAYLOAD},
        notes=_NOTES,
    )


def _prepare_read(context: ConformanceFamilyContext) -> ConformancePreparation:
    bundle = _seed_bundle(context)
    bucket_id = str(context.profile_id)
    # EvidenceBundleService.check, application/evidence/service.py:287-382: the
    # bucket, work unit and manifest digest bind; the one record is unreachable,
    # which leaves zero digests to compare and a byte-weighted completeness of 0.
    findings = (
        ModeloAuditCheckFindingSnapshot(
            check=VerificationCheck.BUCKET_BINDING, passed=True, detail=f"manifest bucket={bucket_id!r}"
        ),
        ModeloAuditCheckFindingSnapshot(
            check=VerificationCheck.WORK_UNIT_BINDING, passed=True, detail=f"work_unit_id={bundle.work_unit_id!r}"
        ),
        ModeloAuditCheckFindingSnapshot(
            check=VerificationCheck.OBJECT_REACHABILITY, passed=False, detail="0/1 reachable"
        ),
        ModeloAuditCheckFindingSnapshot(
            check=VerificationCheck.RECORD_DIGESTS, passed=True, detail="0/0 digest matches"
        ),
        ModeloAuditCheckFindingSnapshot(
            check=VerificationCheck.MANIFEST_DIGEST,
            passed=True,
            detail=f"expected {bundle.bundle_id!r}, got {bundle.bundle_id!r}",
        ),
    )
    return ConformancePreparation(
        subject_ref=profile_operation_subject(bucket_id),
        request=ModeloAuditReadRequest(profile_id=context.profile_id, kind="check", bundle_id=bundle.bundle_id),
        expected_result=ModeloAuditReadProjection(
            profile_id=context.profile_id,
            kind="check",
            report=ModeloAuditCheckReportSnapshot(
                bundle_id=bundle.bundle_id,
                verification_state=BundleVerificationState.INCOMPLETE,
                findings=findings,
                completeness_ratio=0.0,
            ),
        ),
    )


def _prepare_query(context: ConformanceFamilyContext) -> ConformancePreparation:
    bundle = _seed_bundle(context)
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        # An unambiguous prefix resolves to the one bundle in the profile.
        request=ModeloAuditReadRequest(profile_id=context.profile_id, kind="view", bundle_id=bundle.bundle_id[:12]),
        expected_result=ModeloAuditQueryProjection(
            profile_id=context.profile_id,
            kind="view",
            bundle=ModeloAuditQueryBundle(
                bundle_id=bundle.bundle_id,
                manifest_version=1,
                bucket_id=str(context.profile_id),
                work_unit_id=bundle.work_unit_id,
                calculation_revision_id=None,
                filing_record_id=None,
                # A freshly built manifest is PENDING and records a completeness of 1 when it has records.
                verification_state=BundleVerificationState.PENDING,
                completeness_ratio=1.0,
                records=(
                    ModeloAuditQueryRecord(
                        object_type=BucketEventObjectType.CALCULATION_REVISION,
                        content_sha256=hashlib.sha256(_RECORD_PAYLOAD).hexdigest(),
                        payload_size_bytes=len(_RECORD_PAYLOAD),
                    ),
                ),
                created_at=bundle.created_at,
                # The agent query discloses only whether notes exist, never their text.
                notes_present=True,
            ),
        ),
    )


def _prepare_export(context: ConformanceFamilyContext) -> ConformancePreparation:
    bundle = _seed_bundle(context)
    output = context.input_root / "audit-export.zip"

    def verify(_outcome: ConformanceOutcome) -> None:
        # Unreachable records are skipped and manifest.json is written last.
        with ZipFile(output) as archive:
            assert archive.namelist() == ["manifest.json"]
            manifest = archive.read("manifest.json")
        assert EvidenceBundle.model_validate_json(manifest) == bundle

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=ModeloAuditExportRequest(
            profile_id=context.profile_id, bundle_id=bundle.bundle_id, output=output, force_incomplete=True
        ),
        # The receipt reports the stored manifest's state, not the check's.
        expected_result=ModeloAuditExportProjection(
            profile_id=context.profile_id,
            bundle_id=bundle.bundle_id,
            output=str(output),
            verification_state=BundleVerificationState.PENDING,
            records=1,
        ),
        verify=verify,
    )


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    definition_id = context.definition.definition_id
    if definition_id == MODELO_AUDIT_READ_OPERATION_DEFINITION_ID:
        return _prepare_read(context)
    if definition_id == MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID:
        return _prepare_query(context)
    if definition_id == MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID:
        return _prepare_export(context)
    raise AssertionError(f"no Modelo audit conformance scenario for {definition_id}")


MODELO_AUDIT_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            MODELO_AUDIT_READ_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (MODELO_AUDIT_READ_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID,),
        ),
        RegisteredExecutorConformanceCase(
            MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)
