"""Exact-profile ledger disclosure with canonical period or whole-profile scope."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from ...core.operations import profile_operation_subject
from ...core.period import Period
from ..operations.access_resolution import (
    LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
)
from ..operations.models import OperationRequest
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError


def resolve_ledger_read_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
    *,
    profile_id: UUID,
    periods: frozenset[Period],
) -> ResolvedOperationAccess:
    """Bind a canonical immutable query scope, with empty scope meaning all periods."""
    independent = not periods
    if profile_id != context.profile_id or request.subject_ref != profile_operation_subject(str(profile_id)):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if request.definition_id != context.contract.definition_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    admitted = context.admitted_request
    if admitted is not None and (
        admitted.profile_id != profile_id
        or admitted.definition_id != request.definition_id
        or admitted.action is not AccessAction.SUBMIT
        or admitted.periods != periods
        or admitted.period_independent != independent
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return bind_operation_access_profile(
        context,
        LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS
        if independent
        else LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
        profile_id=context.profile_id,
        definition_id=request.definition_id,
        periods=periods,
    )
