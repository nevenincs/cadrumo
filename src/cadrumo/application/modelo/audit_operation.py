"""Registered exact-profile audit reads and explicit human ZIP export.

The existing evidence service remains the verification and export authority.
Its current default treats referenced payloads as unreachable; these operations
do not add a record loader. Human projections preserve notes and finding text.
Agent projections omit those strings and arbitrary source-record addresses.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...core.unit_proportion import UnitFraction
from ...domain.buckets.event import BucketEventObjectType
from ..evidence.bundle_text import EvidenceBundleNotes
from ..evidence.models import (
    BundleVerificationState,
    EvidenceBundle,
    EvidenceBundleCheckResult,
    EvidenceRecordRef,
    VerificationCheck,
)
from ..evidence.service import EvidenceBundleService, EvidenceBundleVerificationReport
from ..ledger.commit_fence import LedgerCommitAttemptTracker, run_with_ledger_commit_fence
from ..operations.access_resolution import (
    HUMAN_RESUMABLE_COMMITTING_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS,
    HUMAN_RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS,
    RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS,
    OperationAccessContext,
    OperationAccessProfile,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_declared_frontend_and_action,
    require_period_independent_replay_or_authority,
)
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
    RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_terminal_receipt_match
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .audit_operation_ports import ModeloAuditOperationPorts, ModeloAuditOperationPortsFactory

MODELO_AUDIT_READ_OPERATION_DEFINITION_ID = "modelo.audit.read"
MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID = "modelo.audit.query"
MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID = "modelo.audit.export"
_HUMAN_FRONTENDS = frozenset({OperationFrontendProjection.CLI})
_QUERY_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.MCP})
type ModeloAuditReadKind = Literal["view", "check"]


class ModeloAuditReadRequest(BaseModel):
    """Canonical exact-or-unambiguous-prefix lookup in the selected profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: ModeloAuditReadKind
    bundle_id: str


class ModeloAuditExportRequest(BaseModel):
    """Explicit local output authorization, never evidence bytes or credentials."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    bundle_id: str
    output: Path
    force_incomplete: bool = False


class ModeloAuditBundleSnapshot(BaseModel):
    """Lossless protected human manifest, including existing notes and record addresses."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    bundle_id: ContentDigest
    manifest_version: Annotated[int, Field(ge=1)]
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId | None = None
    filing_record_id: FilingRecordId | None = None
    records: tuple[EvidenceRecordRef, ...] = ()
    verification_state: BundleVerificationState = BundleVerificationState.PENDING
    completeness_ratio: UnitFraction = 1.0
    created_at: datetime
    notes: EvidenceBundleNotes = ""

    def to_bundle(self) -> EvidenceBundle:
        """Restore the canonical manifest for existing human presentation."""
        return EvidenceBundle.model_validate(self.model_dump())


class ModeloAuditCheckFindingSnapshot(BaseModel):
    """A canonical finding after the service has applied its existing prose bound."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    check: VerificationCheck
    passed: bool
    detail: str

    def to_finding(self) -> EvidenceBundleCheckResult:
        """Restore the canonical finding without reinterpreting its outcome."""
        return EvidenceBundleCheckResult(check=self.check, passed=self.passed, detail=self.detail)


class ModeloAuditCheckReportSnapshot(BaseModel):
    """Full canonical human integrity report with every finding in service order."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    bundle_id: ContentDigest
    verification_state: BundleVerificationState
    findings: tuple[ModeloAuditCheckFindingSnapshot, ...]
    completeness_ratio: UnitFraction

    @classmethod
    def from_report(cls, report: EvidenceBundleVerificationReport) -> ModeloAuditCheckReportSnapshot:
        """Copy every canonical outcome and already-bounded finding string."""
        return cls(
            bundle_id=report.bundle_id,
            verification_state=report.verification_state,
            completeness_ratio=report.completeness_ratio,
            findings=tuple(
                ModeloAuditCheckFindingSnapshot(check=row.check, passed=row.passed, detail=row.detail)
                for row in report.findings
            ),
        )

    def to_report(self) -> EvidenceBundleVerificationReport:
        """Restore the complete canonical service report for human presenters."""
        return EvidenceBundleVerificationReport(
            bundle_id=self.bundle_id,
            verification_state=self.verification_state,
            completeness_ratio=self.completeness_ratio,
            findings=tuple(row.to_finding() for row in self.findings),
        )


class ModeloAuditReadProjection(BaseModel):
    """One full human view or check, bound to the exact admitted profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: ModeloAuditReadKind
    bundle: ModeloAuditBundleSnapshot | None = None
    report: ModeloAuditCheckReportSnapshot | None = None

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if (self.bundle is not None) != (self.kind == "view") or (self.report is not None) != (self.kind == "check"):
            raise ValueError("audit read must contain only its selected canonical outcome")
        if self.bundle is not None and self.bundle.bucket_id != str(self.profile_id):
            raise ValueError("audit manifest differs from its exact profile")
        return self


class ModeloAuditQueryRecord(BaseModel):
    """Closed integrity metadata without the manifest's arbitrary source-record address."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    object_type: BucketEventObjectType
    content_sha256: ContentDigest
    payload_size_bytes: Annotated[int, Field(ge=0)]


class ModeloAuditQueryBundle(BaseModel):
    """Reviewed manifest identities and integrity facts, excluding raw operator prose."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    bundle_id: ContentDigest
    manifest_version: Annotated[int, Field(ge=1)]
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId | None
    filing_record_id: FilingRecordId | None
    verification_state: BundleVerificationState
    completeness_ratio: UnitFraction
    records: tuple[ModeloAuditQueryRecord, ...]
    created_at: datetime
    notes_present: bool

    @classmethod
    def from_bundle(cls, bundle: EvidenceBundle) -> ModeloAuditQueryBundle:
        """Select only declared fields from the same canonical manifest read."""
        return cls(
            bundle_id=bundle.bundle_id,
            manifest_version=bundle.manifest_version,
            bucket_id=bundle.bucket_id,
            work_unit_id=bundle.work_unit_id,
            calculation_revision_id=bundle.calculation_revision_id,
            filing_record_id=bundle.filing_record_id,
            verification_state=bundle.verification_state,
            completeness_ratio=bundle.completeness_ratio,
            created_at=bundle.created_at,
            notes_present=bool(bundle.notes),
            records=tuple(
                ModeloAuditQueryRecord(
                    object_type=row.object_type,
                    content_sha256=row.content_sha256,
                    payload_size_bytes=row.payload_size_bytes,
                )
                for row in bundle.records
            ),
        )


class ModeloAuditQueryFinding(BaseModel):
    """Closed verification identity and boolean outcome without finding detail text."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    check: VerificationCheck
    passed: bool


class ModeloAuditQueryReport(BaseModel):
    """Canonical check facts, excluding arbitrary source-record text from failures."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    bundle_id: ContentDigest
    verification_state: BundleVerificationState
    completeness_ratio: UnitFraction
    findings: tuple[ModeloAuditQueryFinding, ...]

    @classmethod
    def from_report(cls, report: EvidenceBundleVerificationReport) -> ModeloAuditQueryReport:
        """Select existing outcomes without another verification algorithm."""
        return cls(
            bundle_id=report.bundle_id,
            verification_state=report.verification_state,
            completeness_ratio=report.completeness_ratio,
            findings=tuple(ModeloAuditQueryFinding(check=row.check, passed=row.passed) for row in report.findings),
        )


class ModeloAuditQueryProjection(BaseModel):
    """Separately consented agent integrity query with immutable exact profile identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: ModeloAuditReadKind
    bundle: ModeloAuditQueryBundle | None = None
    report: ModeloAuditQueryReport | None = None

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if (self.bundle is not None) != (self.kind == "view") or (self.report is not None) != (self.kind == "check"):
            raise ValueError("audit query must contain only its selected canonical outcome")
        if self.bundle is not None and self.bundle.bucket_id != str(self.profile_id):
            raise ValueError("audit query manifest differs from its exact profile")
        return self


class ModeloAuditExportProjection(BaseModel):
    """Existing human output receipt; no archive bytes or source payloads."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    bundle_id: ContentDigest
    output: Annotated[str, Field(min_length=1)]
    verification_state: BundleVerificationState
    records: Annotated[int, Field(ge=0)]


class ModeloAuditReadExecutionResult(BaseModel):
    """Encrypted full human audit retention."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: ModeloAuditReadProjection


class ModeloAuditQueryExecutionResult(BaseModel):
    """Encrypted reviewed agent integrity retention."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: ModeloAuditQueryProjection


class ModeloAuditExportExecutionResult(BaseModel):
    """Encrypted human output receipt retention."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: ModeloAuditExportProjection


def _compose[T: BaseModel](
    factory: ModeloAuditOperationPortsFactory,
    request: OperationRequest[T],
    context: OperationExecutorContext,
    profile_id: UUID,
) -> ModeloAuditOperationPorts:
    require_operation_profile(request, context, profile_id)
    operation = context.authority_operation
    ports = factory(profile_id=profile_id, operation=operation)
    if ports.profile_id != profile_id or ports.operation is not operation:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


def _canonical_read(
    payload: ModeloAuditReadRequest, service: EvidenceBundleService
) -> EvidenceBundle | EvidenceBundleVerificationReport:
    if payload.kind == "view":
        result = service.show(bucket_id=str(payload.profile_id), bundle_id=payload.bundle_id)
        if result.bucket_id != str(payload.profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return result
    return service.check(bucket_id=str(payload.profile_id), bundle_id=payload.bundle_id)


class ModeloAuditReadExecutor:
    """Run one canonical read implementation for independent human and query purposes."""

    def __init__(self, factory: ModeloAuditOperationPortsFactory, *, query: bool) -> None:
        """Bind the exact composition and reviewed output purpose."""
        self._factory = factory
        self._query = query

    async def execute(
        self, request: OperationRequest[ModeloAuditReadRequest], context: OperationExecutorContext
    ) -> str:
        """Read canonical encrypted audit facts without adding record reachability."""
        expected = (
            MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID if self._query else MODELO_AUDIT_READ_OPERATION_DEFINITION_ID
        )
        if request.definition_id != expected or type(request.payload) is not ModeloAuditReadRequest:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        payload = request.payload
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(expected)

        def read() -> ModeloAuditReadExecutionResult | ModeloAuditQueryExecutionResult:
            ports = _compose(self._factory, request, context, payload.profile_id)
            result = _canonical_read(payload, EvidenceBundleService(ports=ports.evidence))
            if self._query:
                return ModeloAuditQueryExecutionResult(
                    projection=ModeloAuditQueryProjection(
                        profile_id=payload.profile_id,
                        kind=payload.kind,
                        bundle=ModeloAuditQueryBundle.from_bundle(result)
                        if isinstance(result, EvidenceBundle)
                        else None,
                        report=ModeloAuditQueryReport.from_report(result)
                        if isinstance(result, EvidenceBundleVerificationReport)
                        else None,
                    )
                )
            return ModeloAuditReadExecutionResult(
                projection=ModeloAuditReadProjection(
                    profile_id=payload.profile_id,
                    kind=payload.kind,
                    bundle=ModeloAuditBundleSnapshot.model_validate(result.model_dump())
                    if isinstance(result, EvidenceBundle)
                    else None,
                    report=ModeloAuditCheckReportSnapshot.from_report(result)
                    if isinstance(result, EvidenceBundleVerificationReport)
                    else None,
                )
            )

        result = await await_cancellation_complete(asyncio.to_thread(read), task_name=expected)
        await context.events.effect(OperationEffect.NONE)
        return await context.operands.put(result, written_at=now())


class ModeloAuditExportExecutor:
    """Fence only the canonical plaintext output writer after verification preparation."""

    def __init__(self, factory: ModeloAuditOperationPortsFactory) -> None:
        """Bind the exact-profile canonical evidence repositories."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloAuditExportRequest], context: OperationExecutorContext
    ) -> str:
        """Preserve incomplete/failed refusal and settle actual ZIP write uncertainty."""
        if (
            request.definition_id != MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID
            or type(request.payload) is not ModeloAuditExportRequest
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        payload = request.payload
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID)

        async def settle() -> str:
            tracker = LedgerCommitAttemptTracker()

            def work() -> ModeloAuditExportExecutionResult:
                ports = _compose(self._factory, request, context, payload.profile_id)
                service = EvidenceBundleService(ports=ports.evidence)
                path = service.export(
                    bucket_id=str(payload.profile_id),
                    bundle_id=payload.bundle_id,
                    output_path=payload.output,
                    force_incomplete=payload.force_incomplete,
                    write=tracker.call_writer,
                )
                # Preserve the existing CLI's post-export manifest read and receipt state.
                bundle = service.show(bucket_id=str(payload.profile_id), bundle_id=payload.bundle_id)
                return ModeloAuditExportExecutionResult(
                    projection=ModeloAuditExportProjection(
                        profile_id=payload.profile_id,
                        bundle_id=bundle.bundle_id,
                        output=str(path),
                        verification_state=bundle.verification_state,
                        records=len(bundle.records),
                    )
                )

            try:
                result = await run_with_ledger_commit_fence(
                    work, tracker=tracker, context=context, task_name=MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID
                )
            except BaseException:
                effect = (
                    OperationEffect.UNKNOWN
                    if tracker.has_uncertain_write
                    else OperationEffect.UPDATED
                    if tracker.confirmed_write
                    else OperationEffect.NONE
                )
                await context.events.effect(effect)
                raise
            if not tracker.confirmed_write or tracker.has_uncertain_write or tracker.attempt_count != 1:
                raise ValueError("audit ZIP outcome disagrees with its concrete writer receipt")
            await context.events.effect(OperationEffect.UPDATED)
            return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(settle(), task_name="modelo-audit-export-settlement")


def resolve_modelo_audit_operation_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Authorize exact purpose/profile and complete reviewed destination disclosure."""
    expected = request.definition_id
    recording, query = _audit_access_mode(expected)
    payload = require_access_request_profile_payload(
        request,
        definition_id=expected,
        payload_type=ModeloAuditExportRequest if recording else ModeloAuditReadRequest,
        access_profile_id=context.profile_id,
        exact_type=True,
    )
    frontends, access_profile = _audit_access_policy(recording=recording, query=query)
    require_declared_frontend_and_action(context, frontends=frontends, actions=access_profile.actions)
    require_period_independent_replay_or_authority(context, profile_id=payload.profile_id, definition_id=expected)
    return bind_operation_access_profile(
        context, access_profile, profile_id=payload.profile_id, definition_id=expected, periods=frozenset()
    )


def _audit_access_mode(expected: str) -> tuple[bool, bool]:
    if expected not in {
        MODELO_AUDIT_READ_OPERATION_DEFINITION_ID,
        MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID,
        MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID,
    }:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return (
        expected == MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID,
        expected == MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID,
    )


def _audit_access_policy(
    *,
    recording: bool,
    query: bool,
) -> tuple[frozenset[OperationFrontendProjection], OperationAccessProfile]:
    frontends = _HUMAN_FRONTENDS if recording else _QUERY_FRONTENDS if query else _HUMAN_FRONTENDS
    access_profile = (
        HUMAN_RESUMABLE_COMMITTING_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS
        if recording
        else RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS
        if query
        else HUMAN_RESUMABLE_READ_WHOLE_PROFILE_DEFINITION_RESULT_PROFILE_AND_TAX_VALUES_ACCESS
    )
    return frontends, access_profile


def project_modelo_audit_operation_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the matching settled purpose's complete typed result."""
    if type(result) is ModeloAuditReadExecutionResult:
        expected = MODELO_AUDIT_READ_OPERATION_DEFINITION_ID
        projection: ModeloAuditReadProjection | ModeloAuditQueryProjection | ModeloAuditExportProjection = (
            result.projection
        )
        effect = OperationEffect.NONE
    elif type(result) is ModeloAuditQueryExecutionResult:
        expected = MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID
        projection = result.projection
        effect = OperationEffect.NONE
    elif type(result) is ModeloAuditExportExecutionResult:
        expected = MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID
        projection = result.projection
        effect = OperationEffect.UPDATED
    else:
        raise ValueError("invalid Modelo audit execution result")
    require_terminal_receipt_match(
        receipt,
        definition_id=expected,
        subject_ref=profile_operation_subject(str(projection.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        message="Modelo audit result differs from its exact-purpose terminal receipt",
    )
    return type(projection).model_validate_json(projection.model_dump_json(), strict=True)


def build_modelo_audit_operation_definitions(
    factory: ModeloAuditOperationPortsFactory,
) -> tuple[OperationDefinition, ...]:
    """Enroll canonical integrity reads and separately authorized human ZIP output."""
    reads = tuple(
        build_single_phase_definition(
            definition_id=definition_id,
            request_type=ModeloAuditReadRequest,
            result_type=result_type,
            executor_type=ModeloAuditReadExecutor,
            build=lambda query=query: ModeloAuditReadExecutor(factory, query=query),
            capabilities=RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES,
            permitted_frontends=frontends,
        )
        for definition_id, result_type, query, frontends in (
            (MODELO_AUDIT_READ_OPERATION_DEFINITION_ID, ModeloAuditReadExecutionResult, False, _HUMAN_FRONTENDS),
            (MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID, ModeloAuditQueryExecutionResult, True, _QUERY_FRONTENDS),
        )
    )
    recording = build_single_phase_definition(
        definition_id=MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID,
        request_type=ModeloAuditExportRequest,
        result_type=ModeloAuditExportExecutionResult,
        executor_type=ModeloAuditExportExecutor,
        build=lambda: ModeloAuditExportExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=_HUMAN_FRONTENDS,
    )
    return (*reads, recording)


def build_modelo_audit_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind closed schemas and independent human/query result consent scopes."""
    models: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
        MODELO_AUDIT_READ_OPERATION_DEFINITION_ID: (ModeloAuditReadRequest, ModeloAuditReadProjection),
        MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID: (ModeloAuditReadRequest, ModeloAuditQueryProjection),
        MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID: (ModeloAuditExportRequest, ModeloAuditExportProjection),
    }
    if len(definitions) != len(models) or {definition.definition_id for definition in definitions} != set(models):
        raise ValueError("incomplete Modelo audit operation family")
    return tuple(
        OperationPublicDefinitionRegistrationV1.compose_request_result(
            definition=definition,
            public_result_type=models[definition.definition_id][1],
            result_projector=project_modelo_audit_operation_result,
            access_resolver=resolve_modelo_audit_operation_access,
        )
        for definition in definitions
    )
