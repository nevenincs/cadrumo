"""Exact-profile authorization and disclosure for local provider teardown."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.operations import profile_operation_subject
from ..operations.access_resolution import (
    SINGLE_RUN_COMMITTING_ACTIONS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access,
    operation_disclosures,
    require_declared_frontend_and_action,
)
from ..operations.models import OperationRequest
from ..operations.registry import ALL_OPERATION_FRONTENDS
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .operation_definitions import (
    AUTH_LOGOUT_OPERATION_DEFINITION_ID,
    AUTH_RESET_OPERATION_DEFINITION_ID,
    AuthTeardownOperationRequest,
)

_DEFINITIONS = frozenset({AUTH_LOGOUT_OPERATION_DEFINITION_ID, AUTH_RESET_OPERATION_DEFINITION_ID})


def resolve_auth_teardown_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require an explicit grant for local teardown; confer no remote authority."""
    if type(request.payload) is not AuthTeardownOperationRequest or request.definition_id not in _DEFINITIONS:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if request.subject_ref != profile_operation_subject(str(context.profile_id)):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    require_declared_frontend_and_action(
        context, frontends=ALL_OPERATION_FRONTENDS, actions=SINGLE_RUN_COMMITTING_ACTIONS
    )
    disclosures = operation_disclosures(
        context,
        observed_by=frozenset({AccessAction.OBSERVE}),
        result_categories=frozenset({DisclosureCategory.PROFILE_VALUES}),
        result_schema_id=request.definition_id + ".result",
    )
    return bind_operation_access(
        context,
        profile_id=context.profile_id,
        definition_id=request.definition_id,
        actions=SINGLE_RUN_COMMITTING_ACTIONS,
        disclosures=disclosures,
        periods=frozenset(),
        period_independent=True,
        requires_all_periods=False,
        requires_human=False,
        provider=Availability.NOT_REQUIRED,
    )
