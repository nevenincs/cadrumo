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
from ..operations.refusal_evidence import OperationRefusalEvidence
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
        if (
            receipt.condition is not OperationTerminalCondition.SUCCEEDED
            or receipt.result_ref is None
            or receipt.refusal_ref is not None
            or receipt.refusal_detail_ref is not None
        ):
            raise ValueError("diagnostic success has incompatible terminal evidence")
    elif (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.result_ref is not None
        or receipt.refusal_ref != AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
    ):
        raise ValueError("diagnostic absence has incompatible terminal evidence")
    return projection


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
        if (
            request.definition_id != AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(bucket_id)
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or await asyncio.to_thread(require_active_bucket_id) != bucket_id
        ):
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
    if context.frontend not in _FRONTENDS:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    if context.action not in _ACTIONS:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    admitted = context.admitted_request
    if admitted is not None and context.action in {AccessAction.OBSERVE, AccessAction.RESULT}:
        if (
            admitted.profile_id != context.profile_id
            or admitted.definition_id != request.definition_id
            or admitted.destination_id != context.destination_id
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
        if schema is None or schema.schema_id != request.definition_id + ".result":
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosures = frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=schema.schema_id,
                    category=DisclosureCategory.PROFILE_VALUES,
                ),
            )
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=payload.profile_id,
            definition_id=request.definition_id,
            action=context.action,
            frontend=context.frontend,
            periods=frozenset(),
            period_independent=True,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=request.definition_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=_ACTIONS,
            disclosures=disclosures,
            periods=frozenset(),
            allow_period_independent=True,
            requires_all_periods=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
            requires_human=True,
        ),
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
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
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
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=AuthDiagnosticReportRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=AuthDiagnosticReportProjection,
        ),
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
