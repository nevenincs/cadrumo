"""Shared profile-boundary checks for operation executors."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import profile_operation_subject
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .models import OperationRequest
from .owner import OperationExecutorContext


def require_operation_profile[RequestPayloadT: BaseModel](
    request: OperationRequest[RequestPayloadT],
    context: OperationExecutorContext,
    profile_id: UUID,
    *,
    expected_subject_ref: str | None = None,
) -> None:
    """Require the operation target and executor identity to match the active profile."""
    require_profile_operation_identity(
        request,
        context,
        profile_id,
        expected_subject_ref=expected_subject_ref,
    )
    if require_active_bucket_id() != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def require_profile_operation_identity[RequestPayloadT: BaseModel](
    request: OperationRequest[RequestPayloadT],
    context: OperationExecutorContext,
    profile_id: UUID,
    *,
    expected_subject_ref: str | None = None,
) -> None:
    """Require request and executor identities to agree on the profile target."""
    subject_ref = profile_operation_subject(str(profile_id)) if expected_subject_ref is None else expected_subject_ref
    if (
        request.subject_ref != subject_ref
        or context.identity.definition_id != request.definition_id
        or context.identity.subject_ref != request.subject_ref
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
