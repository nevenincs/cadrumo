"""Exact-profile worker operation for the existing workstation health report."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Annotated, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ..core.async_cleanup import await_cancellation_complete
from ..core.bucket_pointer import require_active_bucket_id
from ..core.capabilities import ServiceCapability
from ..core.hashing import canonical_json_bytes
from ..core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..core.time.clock import now
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from .auth.operator_probe_ports import OperatorProbePorts
from .operations.access_resolution import (
    LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_period_independent_admission,
)
from .operations.capabilities import RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_READ_CAPABILITIES
from .operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from .operations.operation_definition import OperationDefinition, build_single_phase_definition
from .operations.owner import OperationExecutorContext
from .operations.profile_guard import require_access_request_profile_payload
from .operations.public_scalar import PublicNamedScalar, project_facts, restore_facts
from .operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from .operator_actions.projection import PreconditionVerdictSnapshot
from .preflight import HealthSeverity, PreflightCheck
from .provisioning import DependencyStatus
from .runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from .user_profile.access_contracts import (
    AccessDenialCode,
)
from .user_profile.access_errors import ProfileAccessRefusedError
from .user_profile.capabilities import CapabilityDecision, CapabilitySource
from .workstation_check import WorkstationCheckReport

WORKSTATION_CHECK_OPERATION_DEFINITION_ID = "diagnostics.workstation.check"
type CheckText = Annotated[str, Field(min_length=1, max_length=4096)]


class WorkstationCheckRequest(CredentialFreeOperationRequest):
    """Only the immutable worker profile is supplied by the frontend."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class WorkstationCapabilitySnapshot(BaseModel):
    """The canonical effective capability and its owning source."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    capability: ServiceCapability
    enabled: bool
    source: CapabilitySource
    reason: CheckText


class WorkstationDependencySnapshot(BaseModel):
    """Complete dependency facts with the canonical recovery verdict."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    service: CheckText
    available: bool
    facts: Annotated[tuple[PublicNamedScalar, ...], Field(max_length=4096)] = ()
    precondition_verdict: PreconditionVerdictSnapshot | None = None

    def to_status(self) -> DependencyStatus:
        """Restore exact canonical scalar facts and dependency outcome checks."""
        return DependencyStatus.model_validate(
            {
                "service": self.service,
                "available": self.available,
                "facts": restore_facts(self.facts),
                "precondition_verdict": self.precondition_verdict.to_verdict() if self.precondition_verdict else None,
            },
            strict=True,
        )

    @model_validator(mode="after")
    def _canonical(self) -> WorkstationDependencySnapshot:
        self.to_status()
        return self


class WorkstationPreflightSnapshot(BaseModel):
    """The existing report-only preflight health and recovery facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    check: CheckText
    healthy: bool
    severity: HealthSeverity
    facts: Annotated[tuple[PublicNamedScalar, ...], Field(max_length=4096)] = ()
    precondition_verdict: PreconditionVerdictSnapshot | None = None

    def to_check(self) -> PreflightCheck:
        """Restore the existing report-only health row and its canonical verdict."""
        return PreflightCheck.model_validate(
            {
                "check": self.check,
                "healthy": self.healthy,
                "severity": self.severity,
                "facts": restore_facts(self.facts),
                "precondition_verdict": self.precondition_verdict.to_verdict() if self.precondition_verdict else None,
            },
            strict=True,
        )

    @model_validator(mode="after")
    def _canonical(self) -> WorkstationPreflightSnapshot:
        self.to_check()
        return self


class WorkstationCheckProjection(BaseModel):
    """Closed encrypted projection of the whole canonical workstation report."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    capabilities: Annotated[tuple[WorkstationCapabilitySnapshot, ...], Field(max_length=128)]
    dependencies: Annotated[tuple[WorkstationDependencySnapshot, ...], Field(max_length=4096)]
    preflight: Annotated[tuple[WorkstationPreflightSnapshot, ...], Field(max_length=4096)]
    issues: Annotated[tuple[CheckText, ...], Field(max_length=4096)]

    @classmethod
    def from_report(cls, report: WorkstationCheckReport) -> WorkstationCheckProjection:
        """Copy every original row, ordered fact and recovery verdict."""
        return cls(
            profile_id=report.profile_id,
            capabilities=tuple(_capability_snapshot(row) for row in report.capabilities),
            dependencies=tuple(_dependency_snapshot(row) for row in report.dependencies),
            preflight=tuple(_preflight_snapshot(row) for row in report.preflight),
            issues=report.issues,
        )

    def to_report(self) -> WorkstationCheckReport:
        """Restore full canonical rows so frontends retain their existing presenters."""
        return WorkstationCheckReport(
            profile_id=self.profile_id,
            capabilities=tuple(
                CapabilityDecision(capability=row.capability, enabled=row.enabled, source=row.source, reason=row.reason)
                for row in self.capabilities
            ),
            dependencies=tuple(row.to_status() for row in self.dependencies),
            preflight=tuple(row.to_check() for row in self.preflight),
            issues=self.issues,
        )


def _capability_snapshot(row: CapabilityDecision) -> WorkstationCapabilitySnapshot:
    return WorkstationCapabilitySnapshot(
        capability=row.capability,
        enabled=row.enabled,
        source=row.source,
        reason=row.reason,
    )


def _dependency_snapshot(row: DependencyStatus) -> WorkstationDependencySnapshot:
    return WorkstationDependencySnapshot(
        service=row.service,
        available=row.available,
        facts=project_facts(row.facts),
        precondition_verdict=(
            PreconditionVerdictSnapshot.from_verdict(row.precondition_verdict)
            if row.precondition_verdict is not None
            else None
        ),
    )


def _preflight_snapshot(row: PreflightCheck) -> WorkstationPreflightSnapshot:
    return WorkstationPreflightSnapshot(
        check=row.check,
        healthy=row.healthy,
        severity=row.severity,
        facts=project_facts(row.facts),
        precondition_verdict=(
            PreconditionVerdictSnapshot.from_verdict(row.precondition_verdict)
            if row.precondition_verdict is not None
            else None
        ),
    )


class WorkstationCheckExecutionResult(BaseModel):
    """Keep the retained report separate from its receipt-checked projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: WorkstationCheckProjection


class WorkstationCheckPort(Protocol):
    """Invoke the canonical report through the worker's composition."""

    def __call__(self) -> WorkstationCheckReport:
        """Return the full report without frontend presentation."""
        ...


@dataclass(frozen=True, slots=True)
class WorkstationCheckPorts:
    """Exact immutable profile and retained authority identities."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    operator_probe_ports: OperatorProbePorts
    report: WorkstationCheckPort


class WorkstationCheckPortsFactory(Protocol):
    """Bind profile-sensitive probes at the production composition root."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> WorkstationCheckPorts:
        """Build only the requested authenticated profile's report."""
        ...


class WorkstationCheckExecutor:
    """Own read settlement and delegate report semantics unchanged."""

    def __init__(self, factory: WorkstationCheckPortsFactory) -> None:
        """Keep the composition-owned factory without opening private custody."""
        self._factory = factory

    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str:
        """Retain complete private facts only for the immutable worker profile."""
        if not isinstance(request.payload, WorkstationCheckRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        payload = _request(request, profile_id=request.payload.profile_id)
        if (
            context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

        async def run() -> str:
            await context.events.phase(WORKSTATION_CHECK_OPERATION_DEFINITION_ID)
            await context.events.effect(OperationEffect.NONE)
            operation = context.authority_operation
            ports = self._factory(profile_id=payload.profile_id, operation=operation)
            if ports.profile_id != payload.profile_id or ports.operation is not operation:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

            def read() -> WorkstationCheckProjection:
                if require_active_bucket_id() != str(payload.profile_id):
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                report = ports.report()
                if report.profile_id != payload.profile_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                return WorkstationCheckProjection.from_report(report)

            result = await asyncio.to_thread(read)
            if require_active_bucket_id() != str(payload.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            if len(canonical_json_bytes(result.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            return await context.operands.put(WorkstationCheckExecutionResult(projection=result), written_at=now())

        return await await_cancellation_complete(run(), task_name=WORKSTATION_CHECK_OPERATION_DEFINITION_ID)


def _request(request: OperationRequest[BaseModel], *, profile_id: UUID) -> WorkstationCheckRequest:
    return require_access_request_profile_payload(
        request,
        definition_id=WORKSTATION_CHECK_OPERATION_DEFINITION_ID,
        payload_type=WorkstationCheckRequest,
        access_profile_id=profile_id,
        exact_type=True,
    )


def build_workstation_check_definition(factory: WorkstationCheckPortsFactory) -> OperationDefinition:
    """Enroll the existing private CLI health report without additional frontends."""
    return build_single_phase_definition(
        definition_id=WORKSTATION_CHECK_OPERATION_DEFINITION_ID,
        request_type=WorkstationCheckRequest,
        result_type=WorkstationCheckExecutionResult,
        executor_type=WorkstationCheckExecutor,
        build=lambda: WorkstationCheckExecutor(factory),
        capabilities=RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_READ_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def resolve_workstation_check_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Scope only period-independent profile facts and authorized profile configuration output."""
    _request(request, profile_id=context.profile_id)
    if (
        context.authority_operation is None
        or context.contract.definition_id != request.definition_id
        or context.frontend is not OperationFrontendProjection.CLI
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    admitted = context.admitted_request
    if admitted is not None:
        require_period_independent_admission(
            admitted, profile_id=context.profile_id, definition_id=request.definition_id
        )
    return bind_operation_access_profile(
        context,
        LIFECYCLE_PERIOD_INDEPENDENT_REGISTERED_RESULT_PROFILE_VALUES_ACCESS,
        profile_id=context.profile_id,
        definition_id=request.definition_id,
        periods=frozenset(),
    )


def project_workstation_check_result(
    result: BaseModel, receipt: OperationTerminalReceipt, /
) -> WorkstationCheckProjection:
    """Release only the full exact-profile read with a successful NONE receipt."""
    execution = _workstation_check_execution_result(result)
    projection = execution.projection
    if (
        not _receipt_identifies_workstation_check(projection, receipt)
        or not _receipt_is_successful_result(receipt)
        or len(canonical_json_bytes(projection.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES
    ):
        raise ValueError("workstation check result contradicts its terminal receipt")
    return projection


def _workstation_check_execution_result(result: BaseModel) -> WorkstationCheckExecutionResult:
    if type(result) is not WorkstationCheckExecutionResult or not isinstance(result, WorkstationCheckExecutionResult):
        raise ValueError("invalid workstation check result")
    return result


def _receipt_identifies_workstation_check(
    projection: WorkstationCheckProjection,
    receipt: OperationTerminalReceipt,
) -> bool:
    return (
        receipt.identity.definition_id == WORKSTATION_CHECK_OPERATION_DEFINITION_ID
        and receipt.identity.subject_ref == profile_operation_subject(str(projection.profile_id))
    )


def _receipt_is_successful_result(receipt: OperationTerminalReceipt) -> bool:
    if receipt.condition is not OperationTerminalCondition.SUCCEEDED or receipt.effect is not OperationEffect.NONE:
        return False
    return receipt.result_ref is not None and all(
        reference is None
        for reference in (
            receipt.refusal_ref,
            receipt.refusal_detail_ref,
            receipt.failure_error_code,
            receipt.diagnostic_ref,
        )
    )


def build_workstation_check_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Compile the closed secure-request and complete human-preview schemas."""
    if (
        definition.definition_id != WORKSTATION_CHECK_OPERATION_DEFINITION_ID
        or definition.request_type is not WorkstationCheckRequest
        or definition.result_type is not WorkstationCheckExecutionResult
    ):
        raise ValueError("invalid workstation check definition contract")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=WorkstationCheckProjection,
        result_projector=project_workstation_check_result,
        access_resolver=resolve_workstation_check_access,
    )
