"""Exact-profile human authority for provider login and its bounded result."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ...core.operations import EFFECTS_OF_A_SUCCEEDED_RECEIPT, OperationTerminalCondition, profile_operation_subject
from ..operations.access_resolution import (
    OperationAccessContext,
    ResolvedOperationAccess,
    resolve_human_profile_committing_access,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from .operation_definitions import AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID, AuthSessionAcquireOperationRequest
from .operator_results import AuthLoginResult

AUTH_SESSION_ACQUIRE_RESULT_SCHEMA_ID = AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID + ".result"


class AuthSessionAcquireOperationProjection(BaseModel):
    """The exact profile and provider outcome, without provider session material."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    profile_id: UUID
    result: AuthLoginResult


def resolve_auth_session_acquire_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require human authority separately at execution, publication and release."""
    return resolve_human_profile_committing_access(
        request,
        context,
        definition_id=AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
        request_type=AuthSessionAcquireOperationRequest,
    )


def project_auth_session_acquire_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Project only a verified login whose successful receipt identifies its profile."""
    if (
        type(result) is not AuthLoginResult
        or receipt.identity.definition_id != AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect not in EFFECTS_OF_A_SUCCEEDED_RECEIPT
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
