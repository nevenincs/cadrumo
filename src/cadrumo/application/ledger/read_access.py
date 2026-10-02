"""Exact-profile ledger disclosure with canonical period or whole-profile scope."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from ...core.operations import profile_operation_subject
from ...core.period import Period
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest
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
    disclosures = frozenset[DisclosurePermission]()
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        disclosures = frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
            )
        )
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosures = frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=schema.schema_id,
                    category=DisclosureCategory.TAX_VALUES,
                ),
            )
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            action=context.action,
            frontend=context.frontend,
            periods=periods,
            period_independent=independent,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=request.definition_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=frozenset(
                {
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                    AccessAction.CANCEL,
                    AccessAction.DETACH,
                }
            ),
            disclosures=disclosures,
            periods=periods,
            allow_period_independent=independent,
            requires_all_periods=independent,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )
