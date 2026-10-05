"""Authenticated inspection of the bound profile's recovery enrollment."""

from __future__ import annotations

import asyncio
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
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
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES
from ..operations.models import (
    CredentialFreeOperationRequest,
    OperationRequest,
    OperationTerminalReceipt,
    require_terminal_receipt_match,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationSchemaBindingV1,
)
from .access_contracts import AccessAction, AccessDenialCode, Availability, DisclosureCategory
from .access_errors import ProfileAccessRefusedError
from .recovery_custody import profile_recovery_status

RECOVERY_STATUS_OPERATION_DEFINITION_ID = "user-profile.recovery.status"
_ACTIONS = frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT})


class RecoveryStatusRequest(CredentialFreeOperationRequest):
    """Exact profile whose committed recovery enrollment is inspected."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class RecoveryStatusResult(BaseModel):
    """Enrollment presence without recovery material or capsule paths."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    enrolled: bool


class RecoveryStatusProjection(RecoveryStatusResult):
    """Receipt-validated public recovery enrollment presence."""


class RecoveryStatusExecutor:
    """Read the canonical custody status only inside matching worker custody."""

    async def execute(self, request: OperationRequest[RecoveryStatusRequest], context: OperationExecutorContext) -> str:
        """Persist the allowlisted result in encrypted operation operands."""
        profile_id = request.payload.profile_id
        if type(request.payload) is not RecoveryStatusRequest:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        if request.definition_id != RECOVERY_STATUS_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, profile_id)
        await context.events.phase(RECOVERY_STATUS_OPERATION_DEFINITION_ID)

        async def read_and_publish() -> str:
            status = await asyncio.to_thread(profile_recovery_status, profile_id=profile_id)
            if status.profile_id != str(profile_id):
                raise ValueError("recovery status does not match the worker profile")
            result = RecoveryStatusResult(profile_id=profile_id, enrolled=status.enrolled)
            await context.events.effect(OperationEffect.NONE)
            return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(read_and_publish(), task_name="profile-recovery-status")


def resolve_recovery_status_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require explicit operation and disclosure permission for the exact profile."""
    payload = _validated_recovery_request(request, context)
    require_declared_frontend_and_action(context, frontends=ALL_OPERATION_FRONTENDS, actions=_ACTIONS)
    disclosures = operation_disclosures(
        context,
        observed_by=frozenset({AccessAction.OBSERVE}),
        result_categories=frozenset({DisclosureCategory.PROFILE_VALUES}),
        result_schema_id=RECOVERY_STATUS_OPERATION_DEFINITION_ID + ".result",
    )
    return bind_operation_access(
        context,
        profile_id=payload.profile_id,
        definition_id=request.definition_id,
        actions=_ACTIONS,
        disclosures=disclosures,
        periods=frozenset(),
        period_independent=True,
        requires_all_periods=False,
        requires_human=False,
        provider=Availability.NOT_REQUIRED,
    )


def _validated_recovery_request(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> RecoveryStatusRequest:
    payload = request.payload
    if (
        type(payload) is not RecoveryStatusRequest
        or request.definition_id != RECOVERY_STATUS_OPERATION_DEFINITION_ID
        or context.contract.definition_id != request.definition_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return payload


def project_recovery_status_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> RecoveryStatusProjection:
    """Validate the typed result against a successful read-only terminal receipt."""
    message = "recovery status contradicts its terminal receipt"
    if type(result) is not RecoveryStatusResult:
        raise ValueError(message)
    require_terminal_receipt_match(
        receipt,
        definition_id=RECOVERY_STATUS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        message=message,
    )
    return RecoveryStatusProjection.model_validate_json(result.model_dump_json(), strict=True)


def build_recovery_status_definition() -> OperationDefinition:
    """Compose the canonical recovery-status read executor."""
    return build_single_phase_definition(
        definition_id=RECOVERY_STATUS_OPERATION_DEFINITION_ID,
        request_type=RecoveryStatusRequest,
        result_type=RecoveryStatusResult,
        executor_type=RecoveryStatusExecutor,
        build=RecoveryStatusExecutor,
        capabilities=RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def build_recovery_status_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind strict public schemas and fresh output disclosure checks."""
    if definition.definition_id != RECOVERY_STATUS_OPERATION_DEFINITION_ID:
        raise ValueError("unexpected recovery status definition")
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=RECOVERY_STATUS_OPERATION_DEFINITION_ID + ".request",
            schema_version=1,
            model_type=RecoveryStatusRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=RECOVERY_STATUS_OPERATION_DEFINITION_ID + ".result",
            schema_version=1,
            model_type=RecoveryStatusProjection,
        ),
        result_projector=project_recovery_status_result,
        access_resolver=resolve_recovery_status_access,
    )
