"""Registered operation and response-scope policy evaluation."""

from __future__ import annotations

from ...core.operations import OperationInteractionKind
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.registry import OperationPublicDefinitionContractV1, OperationRegistry
from .access_contracts import (
    AccessAction,
    AccessDecision,
    AccessDenialCode,
    AccessDenied,
    AccessEvaluationContext,
    AccessScope,
    AccessSession,
    ApiKeyRecord,
    AutomationGrant,
    Availability,
    DisclosureCategory,
    OperationAccessPolicy,
    OperationAccessRequest,
    OperationResponseScopeAllowed,
    ProfileAccessState,
    SessionKind,
)
from .access_policy import intersect_scopes
from .session_authority_policy import evaluate_session_authority


def operation_scope_refusal(
    *, request: OperationAccessRequest, policy: OperationAccessPolicy, scope: AccessScope
) -> AccessDenied | None:
    """Apply one authority ceiling without authenticating or granting an operation."""
    refusal = _operation_action_refusal(request, policy, scope)
    if refusal is not None:
        return refusal
    refusal = _operation_period_refusal(request, policy, scope)
    if refusal is not None:
        return refusal
    refusal = _operation_disclosure_scope_refusal(request, policy, scope)
    if refusal is not None:
        return refusal
    return None


def _operation_action_refusal(
    request: OperationAccessRequest,
    policy: OperationAccessPolicy,
    scope: AccessScope,
) -> AccessDenied | None:
    if (
        request.definition_id not in scope.operations
        or request.action not in scope.actions
        or request.action not in policy.actions
    ):
        return AccessDenied(code=AccessDenialCode.OPERATION_DENIED)
    return None


def _operation_period_refusal(
    request: OperationAccessRequest,
    policy: OperationAccessPolicy,
    scope: AccessScope,
) -> AccessDenied | None:
    if (
        (request.period_independent and not (scope.allow_period_independent and policy.allow_period_independent))
        or (policy.requires_all_periods and scope.periods is not None)
        or (scope.periods is not None and not request.periods <= scope.periods)
        or (policy.periods is not None and not request.periods <= policy.periods)
    ):
        return AccessDenied(code=AccessDenialCode.PERIOD_DENIED)
    return None


def _operation_disclosure_scope_refusal(
    request: OperationAccessRequest,
    policy: OperationAccessPolicy,
    scope: AccessScope,
) -> AccessDenied | None:
    if not policy.disclosures <= scope.disclosures or any(
        item.destination_id != request.destination_id for item in policy.disclosures
    ):
        return AccessDenied(code=AccessDenialCode.DISCLOSURE_DENIED)
    return None


def _evaluate_operation_scope(
    *,
    request: OperationAccessRequest,
    policy: OperationAccessPolicy,
    registry: OperationRegistry,
    session: AccessSession | None,
    ancestors: tuple[AccessSession, ...],
    grant: AutomationGrant | None,
    key: ApiKeyRecord | None,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> AccessDecision:
    """Require exact binding and intersect every authority before private access.

    Success is only the policy half of an application operation. It does not
    certify calculation/filing readiness or supply an apply/reject capability.
    Response callers receive a separate scope-only result from their public
    evaluator; the existing response owner must still prove its capability.
    """
    profile_refusal = _operation_profile_refusal(request, profile)
    if profile_refusal is not None:
        return profile_refusal
    decision = evaluate_session_authority(
        session=session,
        ancestors=ancestors,
        grant=grant,
        key=key,
        profile=profile,
        context=context,
    )
    if isinstance(decision, AccessDenied):
        return decision
    # The admitting result proves a non-null session without publishing one.
    if session is None:
        return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
    contract = _registered_contract_or_refusal(request, policy, registry, session)
    if isinstance(contract, AccessDenied):
        return contract
    scope = _effective_operation_scope(session, ancestors, grant, profile)
    refusal = operation_scope_refusal(request=request, policy=policy, scope=scope)
    if refusal is not None:
        return refusal
    refusal = _registered_disclosure_refusal(request, policy, contract)
    if refusal is not None:
        return refusal
    refusal = _operation_readiness_refusal(policy)
    if refusal is not None:
        return refusal
    return decision


def _effective_operation_scope(
    session: AccessSession,
    ancestors: tuple[AccessSession, ...],
    grant: AutomationGrant | None,
    profile: ProfileAccessState,
) -> AccessScope:
    scopes = (profile.scope, session.scope, *(item.scope for item in ancestors))
    if grant is not None and session.kind is not SessionKind.HUMAN:
        scopes += (grant.scope,)
    return intersect_scopes(scopes)


def _operation_profile_refusal(
    request: OperationAccessRequest,
    profile: ProfileAccessState,
) -> AccessDenied | None:
    if request.profile_id != profile.binding.profile_id:
        return AccessDenied(code=AccessDenialCode.PROFILE_MISMATCH)
    return None


def _registered_contract_or_refusal(
    request: OperationAccessRequest,
    policy: OperationAccessPolicy,
    registry: OperationRegistry,
    session: AccessSession,
) -> OperationPublicDefinitionContractV1 | AccessDenied:
    """Resolve the registered public contract before checking disclosures."""
    try:
        contract = registry.lookup_public_contract(request.definition_id)
    except KeyError:
        return AccessDenied(code=AccessDenialCode.OPERATION_UNAVAILABLE)
    if (
        policy.definition_id != contract.definition_id
        or policy.definition_contract_digest != contract.definition_contract_digest
    ):
        return AccessDenied(code=AccessDenialCode.OPERATION_UNAVAILABLE)
    if policy.requires_human and session.kind is not SessionKind.HUMAN:
        return AccessDenied(code=AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
    if request.frontend not in contract.permitted_frontends:
        return AccessDenied(code=AccessDenialCode.FRONTEND_DENIED)
    return contract


def _registered_disclosure_refusal(
    request: OperationAccessRequest,
    policy: OperationAccessPolicy,
    contract: OperationPublicDefinitionContractV1,
) -> AccessDenied | None:
    """Match action disclosure destinations to the exact registered projection."""
    if request.action is AccessAction.OBSERVE:
        return _observation_disclosure_refusal(policy)
    if request.action in {AccessAction.RESULT, AccessAction.REVIEW}:
        return _result_disclosure_refusal(request, policy, contract)
    return None


def _observation_disclosure_refusal(policy: OperationAccessPolicy) -> AccessDenied | None:
    if not policy.disclosures or any(
        item.projection_id != OPERATION_OBSERVATION_PROJECTION_ID
        or item.category is not DisclosureCategory.OPERATION_METADATA
        for item in policy.disclosures
    ):
        return AccessDenied(code=AccessDenialCode.DISCLOSURE_DENIED)
    return None


def _result_disclosure_refusal(
    request: OperationAccessRequest,
    policy: OperationAccessPolicy,
    contract: OperationPublicDefinitionContractV1,
) -> AccessDenied | None:
    projection = {
        AccessAction.RESULT: contract.result_schema,
        AccessAction.REVIEW: contract.review_projection_schema,
    }[request.action]
    if (
        projection is None
        or not policy.disclosures
        or any(item.projection_id != projection.schema_id for item in policy.disclosures)
    ):
        return AccessDenied(code=AccessDenialCode.DISCLOSURE_DENIED)
    return None


def _operation_readiness_refusal(policy: OperationAccessPolicy) -> AccessDenied | None:
    for readiness, refusal in (
        (policy.backend, AccessDenialCode.BACKEND_UNAVAILABLE),
        (policy.published_authority, AccessDenialCode.AUTHORITY_UNAVAILABLE),
        (policy.provider, AccessDenialCode.PROVIDER_REQUIRED),
    ):
        if readiness not in {Availability.AVAILABLE, Availability.NOT_REQUIRED}:
            return AccessDenied(code=refusal)
    if policy.transaction_authority_required:
        return AccessDenied(code=AccessDenialCode.TRANSACTION_AUTHORITY_REQUIRED)
    return None


def evaluate_operation_access(
    *,
    request: OperationAccessRequest,
    policy: OperationAccessPolicy,
    registry: OperationRegistry,
    session: AccessSession | None,
    ancestors: tuple[AccessSession, ...],
    grant: AutomationGrant | None,
    key: ApiKeyRecord | None,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> AccessDecision:
    """Check current operation permissions without granting response authority."""
    decision = _evaluate_operation_scope(
        request=request,
        policy=policy,
        registry=registry,
        session=session,
        ancestors=ancestors,
        grant=grant,
        key=key,
        profile=profile,
        context=context,
    )
    if isinstance(decision, AccessDenied):
        return decision
    if request.action is AccessAction.RESPOND:
        return AccessDenied(code=AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
    return decision


def evaluate_response_scope(
    *,
    request: OperationAccessRequest,
    policy: OperationAccessPolicy,
    registry: OperationRegistry,
    session: AccessSession | None,
    ancestors: tuple[AccessSession, ...],
    grant: AutomationGrant | None,
    key: ApiKeyRecord | None,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> OperationResponseScopeAllowed | AccessDenied:
    """Validate only the profile scope half of a canonical REVIEW response.

    This distinct result cannot supply the original transaction capability.
    The response owner must independently prove and consume that capability.
    """
    if request.action is not AccessAction.RESPOND:
        return AccessDenied(code=AccessDenialCode.OPERATION_DENIED)
    decision = _evaluate_operation_scope(
        request=request,
        policy=policy,
        registry=registry,
        session=session,
        ancestors=ancestors,
        grant=grant,
        key=key,
        profile=profile,
        context=context,
    )
    if isinstance(decision, AccessDenied):
        return decision
    contract = registry.lookup_public_contract(request.definition_id)
    projection = contract.review_projection_schema
    if (
        OperationInteractionKind.REVIEW not in contract.interaction_kinds
        or contract.interaction_response_schema is None
        or projection is None
    ):
        return AccessDenied(code=AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
    if not policy.disclosures or any(item.projection_id != projection.schema_id for item in policy.disclosures):
        return AccessDenied(code=AccessDenialCode.DISCLOSURE_DENIED)
    return OperationResponseScopeAllowed(
        profile_id=decision.profile_id, session_id=decision.session_id, expires_at=decision.expires_at
    )
