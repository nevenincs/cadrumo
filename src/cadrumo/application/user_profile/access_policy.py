"""Pure, fail-closed policy over fresh application-owned authorization facts.

No function authenticates, decrypts, changes the human active profile, or retains
ambient authority. The runtime must evaluate again at admission, start/resume,
private release and local commit while holding its authoritative denial fence.
"""

from __future__ import annotations

from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.registry import OperationRegistry
from .access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDecision,
    AccessDenialCode,
    AccessDenied,
    AccessEvaluationContext,
    AccessScope,
    AccessSession,
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
    Availability,
    DisclosureCategory,
    LoginEligibility,
    OperationAccessPolicy,
    OperationAccessRequest,
    ProfileAccessState,
    SessionKind,
    SessionState,
)


def scope_is_subset(child: AccessScope, parent: AccessScope) -> bool:
    """Prove narrowing in every dimension, including disclosure destinations."""
    return (
        child.operations <= parent.operations
        and child.actions <= parent.actions
        and child.disclosures <= parent.disclosures
        and (parent.periods is None or (child.periods is not None and child.periods <= parent.periods))
        and (not child.allow_period_independent or parent.allow_period_independent)
        and (not child.allow_delegation or parent.allow_delegation)
    )


def intersect_scopes(scopes: tuple[AccessScope, ...]) -> AccessScope:
    """Intersect explicit permissions; an empty authority chain grants nothing."""
    if not scopes:
        return AccessScope(
            operations=frozenset(),
            actions=frozenset(),
            disclosures=frozenset(),
            periods=frozenset(),
            allow_period_independent=False,
            allow_delegation=False,
        )
    first, *rest = scopes
    operations, actions, disclosures, periods = first.operations, first.actions, first.disclosures, first.periods
    for scope in rest:
        operations &= scope.operations
        actions &= scope.actions
        disclosures &= scope.disclosures
        if scope.periods is not None:
            periods = scope.periods if periods is None else periods & scope.periods
    return AccessScope(
        operations=operations,
        actions=actions,
        disclosures=disclosures,
        periods=periods,
        allow_period_independent=all(scope.allow_period_independent for scope in scopes),
        allow_delegation=all(scope.allow_delegation for scope in scopes),
    )


def _session_refusal(
    session: AccessSession,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> AccessDenialCode | None:
    if session.binding.profile_id != profile.binding.profile_id:
        return AccessDenialCode.PROFILE_MISMATCH
    if session.binding != profile.binding:
        return AccessDenialCode.CUSTODY_CHANGED
    if session.profile_lock_generation != profile.lock_generation or profile.globally_locked:
        return AccessDenialCode.PROFILE_LOCKED
    if session.runtime_boot_id != context.runtime_boot_id:
        return AccessDenialCode.RUNTIME_CHANGED
    if session.state is not SessionState.ACTIVE:
        return AccessDenialCode.SESSION_INACTIVE
    if (
        context.clock_rollback_detected
        or context.now < session.issued_at
        or context.monotonic_now < session.issued_monotonic
    ):
        return AccessDenialCode.CLOCK_INVALID
    elapsed = context.monotonic_now - session.issued_monotonic
    if context.now >= session.expires_at or elapsed >= (session.expires_at - session.issued_at).total_seconds():
        return AccessDenialCode.SESSION_EXPIRED
    return None


def _grant_refusal(
    session: AccessSession,
    grant: AutomationGrant | None,
    key: ApiKeyRecord | None,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> AccessDenialCode | None:
    if grant is None or grant.grant_id != session.grant_id or grant.generation != session.grant_generation:
        return AccessDenialCode.GRANT_INACTIVE
    if grant.binding != profile.binding:
        return AccessDenialCode.CUSTODY_CHANGED
    if grant.client_id != session.client_id:
        return AccessDenialCode.CLIENT_MISMATCH
    if grant.state is not AuthorityState.ACTIVE:
        return AccessDenialCode.GRANT_INACTIVE
    if grant.profile_lock_generation != profile.lock_generation:
        return AccessDenialCode.AUTOMATION_SUSPENDED
    if not grant.valid_from <= context.now < grant.expires_at:
        return AccessDenialCode.GRANT_EXPIRED
    if session.issued_at < grant.valid_from or session.expires_at > grant.expires_at:
        return AccessDenialCode.PRIVILEGE_EXPANSION
    if not scope_is_subset(session.scope, grant.scope):
        return AccessDenialCode.PRIVILEGE_EXPANSION
    if not profile.automation_enabled:
        return AccessDenialCode.AUTOMATION_SUSPENDED
    if session.kind is SessionKind.API_KEY:
        if not grant.unattended:
            return AccessDenialCode.GRANT_INACTIVE
        if profile.automation_custody is not Availability.AVAILABLE:
            return AccessDenialCode.CUSTODY_UNAVAILABLE
        if (
            key is None
            or key.key_id != session.key_id
            or key.generation != session.key_generation
            or key.grant_id != grant.grant_id
            or key.binding != profile.binding
            or key.state is not AuthorityState.ACTIVE
        ):
            return AccessDenialCode.KEY_INACTIVE
        if not key.valid_from <= context.now < key.expires_at:
            return AccessDenialCode.KEY_EXPIRED
        if (
            key.valid_from < grant.valid_from
            or key.expires_at > grant.expires_at
            or session.issued_at < key.valid_from
            or session.expires_at > key.expires_at
        ):
            return AccessDenialCode.PRIVILEGE_EXPANSION
    if session.kind is SessionKind.API_KEY:
        eligible = tuple(
            login
            for login in context.login_contexts
            if login.os_owner_id == profile.binding.os_owner_id
            and login.active
            and login.unattended is LoginEligibility.ELIGIBLE
            and login.credential_facilities is Availability.AVAILABLE
        )
        if not eligible:
            return AccessDenialCode.OS_SESSION_UNAVAILABLE
        if not grant.allow_os_lock and all(login.locked for login in eligible):
            return AccessDenialCode.OS_LOCKED
    return None


def evaluate_session_authority(
    *,
    session: AccessSession | None,
    ancestors: tuple[AccessSession, ...],
    grant: AutomationGrant | None,
    key: ApiKeyRecord | None,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> AccessDecision:
    """Validate a complete live lineage, supplied immediate parent first.

    The owner resolves every ancestor from current state. A missing, repeated,
    unrelated or stale ancestor refuses. Agent labels are deliberately absent:
    only the peer-authenticated connection and enrolled client identity count.
    """
    if session is None:
        return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
    if not context.private_work_available:
        return AccessDenied(code=AccessDenialCode.OS_SESSION_UNAVAILABLE)
    if session.connection_id != context.connection_id:
        return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
    if session.client_id != context.authenticated_client_id:
        return AccessDenied(code=AccessDenialCode.CLIENT_MISMATCH)
    chain = (session, *ancestors)
    if len({item.session_id for item in chain}) != len(chain):
        return AccessDenied(code=AccessDenialCode.PARENT_INVALID)
    for index, item in enumerate(chain):
        refusal = _session_refusal(item, profile, context)
        if refusal is not None:
            return AccessDenied(code=refusal)
        if item.kind is not SessionKind.HUMAN:
            refusal = _grant_refusal(item, grant, key, profile, context)
            if refusal is not None:
                return AccessDenied(code=refusal)
        if item.kind is not SessionKind.API_KEY:
            login = next(
                (
                    login
                    for login in context.login_contexts
                    if login.login_id == item.originating_login_id
                    and login.os_owner_id == item.binding.os_owner_id
                    and login.active
                ),
                None,
            )
            if login is None:
                return AccessDenied(code=AccessDenialCode.OS_SESSION_UNAVAILABLE)
            if login.locked:
                return AccessDenied(code=AccessDenialCode.OS_LOCKED)
        parent = chain[index + 1] if index + 1 < len(chain) else None
        if item.parent_session_id != (None if parent is None else parent.session_id):
            return AccessDenied(code=AccessDenialCode.PARENT_INVALID)
        if parent is not None:
            refusal = _parent_refusal(item, parent)
            if refusal is not None:
                return AccessDenied(code=refusal)
    if profile.storage is not Availability.AVAILABLE:
        return AccessDenied(code=AccessDenialCode.STORAGE_UNAVAILABLE)
    return AccessAllowed(
        profile_id=session.binding.profile_id, session_id=session.session_id, expires_at=session.expires_at
    )


def _parent_refusal(child: AccessSession, parent: AccessSession) -> AccessDenialCode | None:
    if not parent.scope.allow_delegation or not scope_is_subset(child.scope, parent.scope):
        return AccessDenialCode.PRIVILEGE_EXPANSION
    if child.issued_at < parent.issued_at or child.expires_at > parent.expires_at:
        return AccessDenialCode.PRIVILEGE_EXPANSION
    if child.kind is SessionKind.API_KEY:
        if (
            parent.kind is not SessionKind.API_KEY
            or child.grant_id != parent.grant_id
            or child.key_id != parent.key_id
            or child.client_id != parent.client_id
        ):
            return AccessDenialCode.PARENT_INVALID
    elif (child.kind is SessionKind.ATTENDED and parent.kind not in {SessionKind.HUMAN, SessionKind.ATTENDED}) or (
        child.kind is SessionKind.ATTENDED and child.originating_login_id != parent.originating_login_id
    ):
        return AccessDenialCode.PARENT_INVALID
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
    """Require exact binding and intersect every authority before private access.

    Success is only the policy half of an application operation. It does not
    certify calculation/filing readiness or supply an apply/reject capability.
    RESPOND always hands off with a refusal requiring the existing response
    authority service; this evaluator cannot recover a lost capability.
    """
    if request.profile_id != profile.binding.profile_id:
        return AccessDenied(code=AccessDenialCode.PROFILE_MISMATCH)
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
    try:
        contract = registry.lookup_public_contract(request.definition_id)
    except KeyError:
        return AccessDenied(code=AccessDenialCode.OPERATION_UNAVAILABLE)
    if (
        policy.definition_id != contract.definition_id
        or policy.definition_contract_digest != contract.definition_contract_digest
    ):
        return AccessDenied(code=AccessDenialCode.OPERATION_UNAVAILABLE)
    if request.frontend not in contract.permitted_frontends:
        return AccessDenied(code=AccessDenialCode.FRONTEND_DENIED)
    scopes = (profile.scope, session.scope, *(item.scope for item in ancestors))
    if grant is not None and session.kind is not SessionKind.HUMAN:
        scopes += (grant.scope,)
    scope = intersect_scopes(scopes)
    if (
        request.definition_id not in scope.operations
        or request.action not in scope.actions
        or request.action not in policy.actions
    ):
        return AccessDenied(code=AccessDenialCode.OPERATION_DENIED)
    if (
        (request.period_independent and not (scope.allow_period_independent and policy.allow_period_independent))
        or (scope.periods is not None and not request.periods <= scope.periods)
        or (policy.periods is not None and not request.periods <= policy.periods)
    ):
        return AccessDenied(code=AccessDenialCode.PERIOD_DENIED)
    if not policy.disclosures <= scope.disclosures or any(
        item.destination_id != request.destination_id for item in policy.disclosures
    ):
        return AccessDenied(code=AccessDenialCode.DISCLOSURE_DENIED)
    if request.action is AccessAction.OBSERVE and (
        not policy.disclosures
        or any(
            item.projection_id != OPERATION_OBSERVATION_PROJECTION_ID
            or item.category is not DisclosureCategory.OPERATION_METADATA
            for item in policy.disclosures
        )
    ):
        return AccessDenied(code=AccessDenialCode.DISCLOSURE_DENIED)
    projection = {
        AccessAction.RESULT: contract.result_schema,
        AccessAction.REVIEW: contract.review_projection_schema,
    }.get(request.action)
    if request.action in {AccessAction.RESULT, AccessAction.REVIEW} and (
        projection is None
        or not policy.disclosures
        or any(item.projection_id != projection.schema_id for item in policy.disclosures)
    ):
        return AccessDenied(code=AccessDenialCode.DISCLOSURE_DENIED)
    for readiness, refusal in (
        (policy.backend, AccessDenialCode.BACKEND_UNAVAILABLE),
        (policy.published_authority, AccessDenialCode.AUTHORITY_UNAVAILABLE),
        (policy.provider, AccessDenialCode.PROVIDER_REQUIRED),
    ):
        if readiness not in {Availability.AVAILABLE, Availability.NOT_REQUIRED}:
            return AccessDenied(code=refusal)
    if request.action is AccessAction.RESPOND:
        return AccessDenied(code=AccessDenialCode.RESPONSE_AUTHORITY_REQUIRED)
    if policy.transaction_authority_required:
        return AccessDenied(code=AccessDenialCode.TRANSACTION_AUTHORITY_REQUIRED)
    return decision
