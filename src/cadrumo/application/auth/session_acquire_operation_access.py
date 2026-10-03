"""Exact-profile human authority for provider login and its bounded result."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..operations.access_resolution import (
    HUMAN_SINGLE_RUN_COMMITTING_PERIOD_INDEPENDENT_DEFINITION_RESULT_PROFILE_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_declared_frontend_and_action,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.registry import OperationFrontendProjection
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .operation_definitions import AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID, AuthSessionAcquireOperationRequest
from .operator_results import AuthLoginResult

AUTH_SESSION_ACQUIRE_RESULT_SCHEMA_ID = AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID + ".result"
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
    access_profile = HUMAN_SINGLE_RUN_COMMITTING_PERIOD_INDEPENDENT_DEFINITION_RESULT_PROFILE_VALUES_ACCESS
    require_declared_frontend_and_action(context, frontends=_FRONTENDS, actions=access_profile.actions)
    return bind_operation_access_profile(
        context, access_profile, profile_id=context.profile_id, definition_id=request.definition_id, periods=frozenset()
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
