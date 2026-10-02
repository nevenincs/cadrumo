"""Authenticated inspection of the bound profile's recovery enrollment."""

from __future__ import annotations

import asyncio
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
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
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
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
        if (
            type(request.payload) is not RecoveryStatusRequest
            or request.definition_id != RECOVERY_STATUS_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(profile_id))
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != str(profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
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
    if context.frontend not in _FRONTENDS:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    if context.action not in _ACTIONS:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
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


def project_recovery_status_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> RecoveryStatusProjection:
    """Validate the typed result against a successful read-only terminal receipt."""
    if (
        type(result) is not RecoveryStatusResult
        or receipt.identity.definition_id != RECOVERY_STATUS_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(result.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("recovery status contradicts its terminal receipt")
    return RecoveryStatusProjection.model_validate_json(result.model_dump_json(), strict=True)


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
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
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
