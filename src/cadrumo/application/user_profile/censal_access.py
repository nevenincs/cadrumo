"""Shared exact-profile access stages for recorded censal operations."""

from __future__ import annotations

from pydantic import BaseModel

from ..operations.access_resolution import OperationAccessContext
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest
from .access_contracts import AccessAction, AccessDenialCode, DisclosureCategory, DisclosurePermission
from .access_errors import ProfileAccessRefusedError


def require_admitted_profile_censal_request(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> None:
    """Refuse terminal access when its admitted submit belongs to another request."""
    admitted = context.admitted_request
    if (
        admitted is not None
        and context.action
        in {
            AccessAction.OBSERVE,
            AccessAction.RESULT,
            AccessAction.CANCEL,
            AccessAction.DETACH,
        }
        and (
            admitted.profile_id != context.profile_id
            or admitted.definition_id != request.definition_id
            or admitted.action is not AccessAction.SUBMIT
            or not admitted.period_independent
            or admitted.periods
        )
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def profile_censal_access_disclosure(context: OperationAccessContext) -> DisclosurePermission | None:
    """Return the narrow metadata or result disclosure admitted for this action."""
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        return DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    if context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=schema.schema_id,
            category=DisclosureCategory.PROFILE_VALUES,
        )
    return None
