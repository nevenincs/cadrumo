"""Authenticated inspection of the bound profile's recovery enrollment."""

from __future__ import annotations

import asyncio
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from .access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from .access_errors import ProfileAccessRefusedError
from .recovery_custody import profile_recovery_status

RECOVERY_STATUS_OPERATION_DEFINITION_ID = "user-profile.recovery.status"
_ACTIONS = frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT})
_FRONTENDS = frozenset(OperationFrontendProjection)


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
    _require_recovery_access(context)
    disclosure = _recovery_disclosure(context)
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
            disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
            periods=frozenset(),
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
            requires_human=False,
        ),
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


def _require_recovery_access(context: OperationAccessContext) -> None:
    if context.frontend not in _FRONTENDS:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    if context.action not in _ACTIONS:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _recovery_disclosure(context: OperationAccessContext) -> DisclosurePermission | None:
    disclosure = None
    if context.action is AccessAction.OBSERVE:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None or schema.schema_id != RECOVERY_STATUS_OPERATION_DEFINITION_ID + ".result":
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=schema.schema_id,
            category=DisclosureCategory.PROFILE_VALUES,
        )
    return disclosure


def project_recovery_status_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> RecoveryStatusProjection:
    """Validate the typed result against a successful read-only terminal receipt."""
    if (
        type(result) is not RecoveryStatusResult
        or not _receipt_matches_recovery_result(result, receipt)
        or not _receipt_is_read_only_success(receipt)
    ):
        raise ValueError("recovery status contradicts its terminal receipt")
    return RecoveryStatusProjection.model_validate_json(result.model_dump_json(), strict=True)


def _receipt_matches_recovery_result(result: RecoveryStatusResult, receipt: OperationTerminalReceipt) -> bool:
    return (
        receipt.identity.definition_id == RECOVERY_STATUS_OPERATION_DEFINITION_ID
        and receipt.identity.subject_ref == profile_operation_subject(str(result.profile_id))
    )


def _receipt_is_read_only_success(receipt: OperationTerminalReceipt) -> bool:
    return (
        receipt.condition is OperationTerminalCondition.SUCCEEDED
        and receipt.effect is OperationEffect.NONE
        and receipt.result_ref is not None
        and receipt.refusal_ref is None
        and receipt.refusal_detail_ref is None
        and receipt.failure_error_code is None
        and receipt.diagnostic_ref is None
    )


def build_recovery_status_definition() -> OperationDefinition:
    """Compose the canonical recovery-status read executor."""
    return OperationDefinition(
        definition_id=RECOVERY_STATUS_OPERATION_DEFINITION_ID,
        request_type=RecoveryStatusRequest,
        result_type=RecoveryStatusResult,
        executor_factory=OperationExecutorFactory(
            request_type=RecoveryStatusRequest,
            executor_type=RecoveryStatusExecutor,
            build=RecoveryStatusExecutor,
        ),
        phase_codes=(RECOVERY_STATUS_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=_FRONTENDS,
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
