"""Exact-profile registered mutation of an encrypted auth diagnostic phone report."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.not_found import CoreNotFoundError
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ..operations.access_resolution import (
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access,
    operation_disclosures,
    require_declared_frontend_and_action,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_profile_operation_identity
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .diagnostics import (
    AuthDiagnosticPhoneState,
    AuthDiagnosticReportResult,
    persist_auth_diagnostic_phone_state,
    prepare_auth_diagnostic_phone_state,
)
from .diagnostics_ports import AuthDiagnosticPersistencePort

AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID = "auth.diagnostics.phone-state-report"
AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE = "REFUSED_AUTH_DIAGNOSTIC_NOT_FOUND"
_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})
_ACTIONS = frozenset(
    {AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT, AccessAction.OBSERVE, AccessAction.RESULT}
)


class AuthDiagnosticNotFoundError(CoreNotFoundError):
    """The requested encrypted diagnostic record does not exist in this profile."""


class AuthDiagnosticReportRequest(BaseModel):
    """Exact profile, bounded record ID, and closed operator phone-state token."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    diagnostic_id: str = Field(min_length=1, max_length=128)
    phone_state: AuthDiagnosticPhoneState


class AuthDiagnosticReportProjection(BaseModel):
    """Canonical report result or a typed prewrite absence refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    operation_id: Literal["auth.diagnostics.phone-state-report"]
    outcome: Literal["completed", "prewrite_refusal"]
    effect: OperationEffect
    report: AuthDiagnosticReportResult | None = None
    refusal_code: str | None = None

    @model_validator(mode="after")
    def _one_outcome(self) -> Self:
        if self.outcome == "completed":
            if self.effect is not OperationEffect.UPDATED or self.report is None or self.refusal_code is not None:
                raise ValueError("completed diagnostic report must prove an updated record")
        elif (
            self.effect is not OperationEffect.NONE
            or self.report is not None
            or self.refusal_code != AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE
        ):
            raise ValueError("diagnostic absence must be a prewrite refusal")
        return self


class AuthDiagnosticReportExecutionResult(BaseModel):
    """Private encrypted terminal detail awaiting authorized projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: AuthDiagnosticReportProjection


@dataclass(frozen=True, slots=True)
class AuthDiagnosticReportPorts:
    """One diagnostic persistence capability bound to an exact profile."""

    bucket_id: str
    persistence: AuthDiagnosticPersistencePort


class AuthDiagnosticReportPortsFactory(Protocol):
    """Compose encrypted diagnostic storage without choosing an ambient profile."""

    def __call__(self, *, bucket_id: str) -> AuthDiagnosticReportPorts:
        """Return only the named profile's encrypted diagnostic capability."""
        ...


def project_auth_diagnostic_report_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Require matching profile, operation, effect, and terminal evidence."""
    if type(result) is not AuthDiagnosticReportExecutionResult:
        raise ValueError("invalid private diagnostic report result")
    projection = result.projection
    if (
        receipt.identity.definition_id != projection.operation_id
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.effect is not projection.effect
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("diagnostic report differs from its receipt")
    if projection.outcome == "completed":
        _require_diagnostic_success_receipt(receipt)
    else:
        _require_diagnostic_absence_receipt(receipt)
    return projection


def _require_diagnostic_success_receipt(receipt: OperationTerminalReceipt) -> None:
    if (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
    ):
        raise ValueError("diagnostic success has incompatible terminal evidence")


def _require_diagnostic_absence_receipt(receipt: OperationTerminalReceipt) -> None:
    if (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.result_ref is not None
        or receipt.refusal_ref != AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
    ):
        raise ValueError("diagnostic absence has incompatible terminal evidence")


class AuthDiagnosticReportExecutor:
    """Prepare a canonical phone-state update and fence only its encrypted save."""

    def __init__(self, factory: AuthDiagnosticReportPortsFactory) -> None:
        """Retain the exact-profile factory until operation-owner execution."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[AuthDiagnosticReportRequest], context: OperationExecutorContext
    ) -> str | OperationRefusalEvidence:
        """Produce NONE on a known miss, UNKNOWN at attempted save, UPDATED on success."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, payload.profile_id)
        if await asyncio.to_thread(require_active_bucket_id) != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID)

        async def run() -> str | OperationRefusalEvidence:
            def prepare():
                if require_active_bucket_id() != bucket_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                ports = self._factory(bucket_id=bucket_id)
                if ports.bucket_id != bucket_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                prepared = prepare_auth_diagnostic_phone_state(
                    payload.diagnostic_id, payload.phone_state.value, persistence=ports.persistence
                )
                return ports, prepared

            ports, prepared = await asyncio.to_thread(prepare)
            if prepared is None:
                projection = AuthDiagnosticReportProjection(
                    profile_id=payload.profile_id,
                    operation_id=AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID,
                    outcome="prewrite_refusal",
                    effect=OperationEffect.NONE,
                    refusal_code=AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE,
                )
                reference = await context.operands.put(
                    AuthDiagnosticReportExecutionResult(projection=projection), written_at=now()
                )
                await context.events.effect(OperationEffect.NONE)
                return OperationRefusalEvidence(
                    refusal_code=AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE, detail_ref=reference
                )
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                await asyncio.to_thread(persist_auth_diagnostic_phone_state, prepared, persistence=ports.persistence)
                await context.events.effect(OperationEffect.UPDATED)
            projection = AuthDiagnosticReportProjection(
                profile_id=payload.profile_id,
                operation_id=AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID,
                outcome="completed",
                effect=OperationEffect.UPDATED,
                report=prepared.result,
            )
            return await context.operands.put(
                AuthDiagnosticReportExecutionResult(projection=projection), written_at=now()
            )

        return await await_cancellation_complete(run(), task_name=AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID)


def resolve_auth_diagnostic_report_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact human profile/all periods at mutation and result release."""
    payload = _require_auth_diagnostic_report_request(request, context)
    require_declared_frontend_and_action(context, frontends=_FRONTENDS, actions=_ACTIONS)
    _require_diagnostic_admission_or_authority(request, context)
    disclosures = operation_disclosures(
        context,
        observed_by=frozenset({AccessAction.OBSERVE}),
        result_categories=frozenset({DisclosureCategory.PROFILE_VALUES}),
        result_schema_id=AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID + ".result",
    )
    return bind_operation_access(
        context,
        profile_id=payload.profile_id,
        definition_id=request.definition_id,
        actions=_ACTIONS,
        disclosures=disclosures,
        periods=frozenset(),
        period_independent=True,
        requires_all_periods=True,
        requires_human=True,
        provider=Availability.NOT_REQUIRED,
    )


def _require_auth_diagnostic_report_request(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> AuthDiagnosticReportRequest:
    payload = request.payload
    if (
        request.definition_id != AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID
        or type(payload) is not AuthDiagnosticReportRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return payload


def _require_diagnostic_admission_or_authority(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> None:
    admitted = context.admitted_request
    if admitted is not None and context.action in {AccessAction.OBSERVE, AccessAction.RESULT}:
        if not _matches_diagnostic_admission(admitted, request, context):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    elif context.authority_operation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def _matches_diagnostic_admission(
    admitted: OperationAccessRequest, request: OperationRequest[BaseModel], context: OperationAccessContext
) -> bool:
    return (
        admitted.profile_id == context.profile_id
        and admitted.definition_id == request.definition_id
        and admitted.destination_id == context.destination_id
        and admitted.action is AccessAction.SUBMIT
        and not admitted.periods
        and admitted.period_independent
    )


def build_auth_diagnostic_report_definition(factory: AuthDiagnosticReportPortsFactory) -> OperationDefinition:
    """Declare the encrypted phone-state report as a real guarded mutation."""
    return OperationDefinition(
        definition_id=AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID,
        request_type=AuthDiagnosticReportRequest,
        result_type=AuthDiagnosticReportExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=AuthDiagnosticReportRequest,
            executor_type=AuthDiagnosticReportExecutor,
            build=lambda: AuthDiagnosticReportExecutor(factory),
        ),
        phase_codes=(AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=_FRONTENDS,
        refusal_detail_codes=frozenset({AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE}),
    )


def build_auth_diagnostic_report_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the closed request/result and current human access policy."""
    if definition.definition_id != AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID:
        raise ValueError("unexpected auth diagnostic report definition")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=AuthDiagnosticReportProjection,
        result_projector=project_auth_diagnostic_report_result,
        access_resolver=resolve_auth_diagnostic_report_access,
    )


__all__ = [
    "AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE",
    "AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID",
    "AuthDiagnosticNotFoundError",
    "AuthDiagnosticReportExecutionResult",
    "AuthDiagnosticReportPorts",
    "AuthDiagnosticReportPortsFactory",
    "AuthDiagnosticReportProjection",
    "AuthDiagnosticReportRequest",
    "build_auth_diagnostic_report_definition",
    "build_auth_diagnostic_report_registration",
    "project_auth_diagnostic_report_result",
    "resolve_auth_diagnostic_report_access",
]
