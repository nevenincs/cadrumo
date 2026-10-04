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
    with_commit_action,
)
from ..operations.models import OperationRequest
from ..operations.profile_guard import require_access_request_payload
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessRequest
from ..user_profile.access_errors import ProfileAccessRefusedError


def _require_admitted_read_scope(
    admitted: OperationAccessRequest | None,
    *,
    profile_id: UUID,
    definition_id: str,
    periods: frozenset[Period],
    period_independent: bool,
) -> None:
    """Require the admission decision to match the exact read profile and period scope."""
    if admitted is not None and (
        admitted.profile_id != profile_id
        or admitted.definition_id != definition_id
        or admitted.action is not AccessAction.SUBMIT
        or admitted.periods != periods
        or admitted.period_independent != period_independent
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


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
    _require_admitted_read_scope(
        context.admitted_request,
        profile_id=profile_id,
        definition_id=request.definition_id,
        periods=periods,
        period_independent=independent,
    )
    return bind_operation_access_profile(
        context,
        LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS
        if independent
        else LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
        profile_id=context.profile_id,
        definition_id=request.definition_id,
        periods=periods,
    )


def resolve_ledger_commit_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
    *,
    profile_id: UUID,
    periods: frozenset[Period],
) -> ResolvedOperationAccess:
    """Bind the ledger read scope and add the explicit COMMIT door for a mutation."""
    return with_commit_action(resolve_ledger_read_access(request, context, profile_id=profile_id, periods=periods))


def resolve_ledger_request_read_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
    *,
    definition_id: str,
    request_type: type[BaseModel],
) -> ResolvedOperationAccess:
    """Bind whole-profile read access for exactly ``request_type`` under ``definition_id``."""
    payload = require_access_request_payload(request, definition_id=definition_id, payload_type=request_type)
    profile_id = getattr(payload, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=profile_id, periods=frozenset())
