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
from ...core.bucket_pointer import require_active_bucket_id
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
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
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .audit_operation_ports import ModeloAuditOperationPorts, ModeloAuditOperationPortsFactory

MODELO_AUDIT_READ_OPERATION_DEFINITION_ID = "modelo.audit.read"
MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID = "modelo.audit.query"
MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID = "modelo.audit.export"
_HUMAN_FRONTENDS = frozenset({OperationFrontendProjection.CLI})
_QUERY_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.MCP})
_ACTIONS = frozenset(
    {AccessAction.SUBMIT, AccessAction.START, AccessAction.RESUME, AccessAction.OBSERVE, AccessAction.RESULT}
)
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


def _require_profile[T: BaseModel](
    request: OperationRequest[T], context: OperationExecutorContext, profile_id: UUID
) -> None:
    if (
        request.subject_ref != profile_operation_subject(str(profile_id))
        or context.identity.definition_id != request.definition_id
        or context.identity.subject_ref != request.subject_ref
        or require_active_bucket_id() != str(profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _compose[T: BaseModel](
    factory: ModeloAuditOperationPortsFactory,
    request: OperationRequest[T],
    context: OperationExecutorContext,
    profile_id: UUID,
) -> ModeloAuditOperationPorts:
    _require_profile(request, context, profile_id)
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
        _require_profile(request, context, payload.profile_id)
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
        _require_profile(request, context, payload.profile_id)
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
    recording = expected == MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID
    query = expected == MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID
    if expected not in {
        MODELO_AUDIT_READ_OPERATION_DEFINITION_ID,
        MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID,
        MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID,
    }:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = request.payload
    if type(payload) is not (ModeloAuditExportRequest if recording else ModeloAuditReadRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if not isinstance(payload, (ModeloAuditReadRequest, ModeloAuditExportRequest)):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    frontends = _HUMAN_FRONTENDS if recording else _QUERY_FRONTENDS if query else _HUMAN_FRONTENDS
    if context.frontend not in frontends:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    actions = _ACTIONS | frozenset({AccessAction.COMMIT}) if recording else _ACTIONS
    if context.action not in actions:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    admitted = context.admitted_request
    if admitted is not None and context.action not in {AccessAction.SUBMIT, AccessAction.START, AccessAction.RESUME}:
        if (
            admitted.profile_id != payload.profile_id
            or admitted.definition_id != expected
            or admitted.destination_id != context.destination_id
            or admitted.frontend is not context.frontend
            or admitted.action is not AccessAction.SUBMIT
            or admitted.periods
            or not admitted.period_independent
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    elif context.authority_operation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    disclosures = frozenset[DisclosurePermission]()
    if context.action is AccessAction.OBSERVE:
        disclosures = frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
            )
        )
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None or schema.schema_id != expected + ".result":
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosures = frozenset(
            DisclosurePermission(
                destination_id=context.destination_id,
                projection_id=schema.schema_id,
                category=category,
            )
            for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=payload.profile_id,
            definition_id=expected,
            action=context.action,
            frontend=context.frontend,
            periods=frozenset(),
            period_independent=True,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=expected,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=actions,
            disclosures=disclosures,
            periods=frozenset(),
            allow_period_independent=True,
            requires_all_periods=True,
            requires_human=not query,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )


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
    if (
        receipt.identity.definition_id != expected
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not effect
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("Modelo audit result differs from its exact-purpose terminal receipt")
    return type(projection).model_validate_json(projection.model_dump_json(), strict=True)


def _capabilities(*, recording: bool) -> OperationCapabilities:
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE
        if recording
        else OperationSensitiveInputPolicy.NONE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=(
            frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN})
            if recording
            else frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
        ),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def build_modelo_audit_operation_definitions(
    factory: ModeloAuditOperationPortsFactory,
) -> tuple[OperationDefinition, ...]:
    """Enroll canonical integrity reads and separately authorized human ZIP output."""
    reads = tuple(
        OperationDefinition(
            definition_id=definition_id,
            request_type=ModeloAuditReadRequest,
            result_type=result_type,
            executor_factory=OperationExecutorFactory(
                request_type=ModeloAuditReadRequest,
                executor_type=ModeloAuditReadExecutor,
                build=lambda query=query: ModeloAuditReadExecutor(factory, query=query),
            ),
            phase_codes=(definition_id,),
            interaction_kinds=frozenset(),
            capabilities=_capabilities(recording=False),
            reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
            permitted_frontends=frontends,
        )
        for definition_id, result_type, query, frontends in (
            (MODELO_AUDIT_READ_OPERATION_DEFINITION_ID, ModeloAuditReadExecutionResult, False, _HUMAN_FRONTENDS),
            (MODELO_AUDIT_QUERY_OPERATION_DEFINITION_ID, ModeloAuditQueryExecutionResult, True, _QUERY_FRONTENDS),
        )
    )
    recording = OperationDefinition(
        definition_id=MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID,
        request_type=ModeloAuditExportRequest,
        result_type=ModeloAuditExportExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloAuditExportRequest,
            executor_type=ModeloAuditExportExecutor,
            build=lambda: ModeloAuditExportExecutor(factory),
        ),
        phase_codes=(MODELO_AUDIT_EXPORT_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=_capabilities(recording=True),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
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
        OperationPublicDefinitionRegistrationV1.compose(
            definition=definition,
            request_schema=OperationSchemaBindingV1.bind(
                schema_id=definition.definition_id + ".request",
                schema_version=1,
                model_type=models[definition.definition_id][0],
            ),
            result_schema=OperationSchemaBindingV1.bind(
                schema_id=definition.definition_id + ".result",
                schema_version=1,
                model_type=models[definition.definition_id][1],
            ),
            result_projector=project_modelo_audit_operation_result,
            access_resolver=resolve_modelo_audit_operation_access,
        )
        for definition in definitions
    )
