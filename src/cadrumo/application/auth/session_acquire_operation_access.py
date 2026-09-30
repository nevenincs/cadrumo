"""Exact-profile human authority for provider login and its bounded result."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.registry import OperationFrontendProjection
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
from .operation_definitions import AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID, AuthSessionAcquireOperationRequest
from .operator_results import AuthLoginResult

AUTH_SESSION_ACQUIRE_RESULT_SCHEMA_ID = AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID + ".result"
_ACTIONS = frozenset(
    {AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT, AccessAction.OBSERVE, AccessAction.RESULT}
)
_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})


class AuthSessionAcquireOperationProjection(BaseModel):
    """The exact profile and provider outcome, without provider session material."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    profile_id: UUID
    result: AuthLoginResult


def resolve_auth_session_acquire_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require human authority separately at execution, publication and release."""
    if (
        request.definition_id != AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID
        or type(request.payload) is not AuthSessionAcquireOperationRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if request.subject_ref != profile_operation_subject(str(context.profile_id)):
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
        if schema is None or schema.schema_id != AUTH_SESSION_ACQUIRE_RESULT_SCHEMA_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=schema.schema_id,
            category=DisclosureCategory.PROFILE_VALUES,
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=context.profile_id,
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
            requires_human=True,
        ),
    )


def project_auth_session_acquire_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Project only a verified login whose successful receipt identifies its profile."""
    if (
        type(result) is not AuthLoginResult
        or receipt.identity.definition_id != AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect not in {OperationEffect.NONE, OperationEffect.UPDATED}
    ):
        raise ValueError("invalid provider login result")
    try:
        profile_id = UUID(receipt.identity.subject_ref.removeprefix("profile:"))
    except ValueError:
        raise ValueError("invalid provider login subject") from None
    if receipt.identity.subject_ref != profile_operation_subject(str(profile_id)):
        raise ValueError("invalid provider login subject")
    validated = AuthLoginResult.model_validate_json(result.model_dump_json(), strict=True)
    if not validated.authenticated or validated.removed_sessions < 0:
        raise ValueError("invalid verified provider login")
    return AuthSessionAcquireOperationProjection(profile_id=profile_id, result=validated)
