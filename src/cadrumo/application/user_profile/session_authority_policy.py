"""Live session lineage and grant authorization policy."""

from __future__ import annotations

from .access_contracts import (
    AccessAllowed,
    AccessDecision,
    AccessDenialCode,
    AccessDenied,
    AccessEvaluationContext,
    AccessSession,
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
    Availability,
    LoginEligibility,
    OsLoginContext,
    ProfileAccessState,
    SessionKind,
    SessionState,
)
from .access_policy import scope_is_subset


def _session_refusal(
    session: AccessSession,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> AccessDenialCode | None:
    binding_refusal = _session_binding_refusal(session, profile, context)
    if binding_refusal is not None:
        return binding_refusal
    if session.state is not SessionState.ACTIVE:
        return AccessDenialCode.SESSION_INACTIVE
    return _session_time_refusal(session, context)


def _session_time_refusal(
    session: AccessSession,
    context: AccessEvaluationContext,
) -> AccessDenialCode | None:
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


def _session_binding_refusal(
    session: AccessSession,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> AccessDenialCode | None:
    """Match profile custody and runtime before considering session time/state."""
    if session.binding.profile_id != profile.binding.profile_id:
        return AccessDenialCode.PROFILE_MISMATCH
    if session.binding != profile.binding:
        return AccessDenialCode.CUSTODY_CHANGED
    if session.profile_lock_generation != profile.lock_generation or profile.globally_locked:
        return AccessDenialCode.PROFILE_LOCKED
    if session.runtime_boot_id != context.runtime_boot_id:
        return AccessDenialCode.RUNTIME_CHANGED
    return None


def _grant_refusal(
    session: AccessSession,
    grant: AutomationGrant | None,
    key: ApiKeyRecord | None,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> AccessDenialCode | None:
    if grant is None:
        return AccessDenialCode.GRANT_INACTIVE
    refusal = _grant_record_refusal(session, grant, profile, context)
    if refusal is not None:
        return refusal
    if session.kind is SessionKind.API_KEY:
        return _api_key_grant_refusal(session, grant, key, profile, context)
    return None


def _grant_record_refusal(
    session: AccessSession,
    grant: AutomationGrant,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> AccessDenialCode | None:
    """Check a grant's identity, lifecycle, time bound, and inherited scope."""
    refusal = _grant_identity_refusal(session, grant, profile)
    if refusal is not None:
        return refusal
    return _grant_window_refusal(session, grant, profile, context)


def _grant_identity_refusal(
    session: AccessSession,
    grant: AutomationGrant,
    profile: ProfileAccessState,
) -> AccessDenialCode | None:
    if grant.grant_id != session.grant_id or grant.generation != session.grant_generation:
        return AccessDenialCode.GRANT_INACTIVE
    if grant.binding != profile.binding:
        return AccessDenialCode.CUSTODY_CHANGED
    if grant.client_id != session.client_id:
        return AccessDenialCode.CLIENT_MISMATCH
    if grant.state is not AuthorityState.ACTIVE:
        return AccessDenialCode.GRANT_INACTIVE
    if grant.profile_lock_generation != profile.lock_generation:
        return AccessDenialCode.AUTOMATION_SUSPENDED
    return None


def _grant_window_refusal(
    session: AccessSession,
    grant: AutomationGrant,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> AccessDenialCode | None:
    if not grant.valid_from <= context.now < grant.expires_at:
        return AccessDenialCode.GRANT_EXPIRED
    if session.issued_at < grant.valid_from or session.expires_at > grant.expires_at:
        return AccessDenialCode.PRIVILEGE_EXPANSION
    if not scope_is_subset(session.scope, grant.scope):
        return AccessDenialCode.PRIVILEGE_EXPANSION
    if not profile.automation_enabled:
        return AccessDenialCode.AUTOMATION_SUSPENDED
    return None


def _api_key_grant_refusal(
    session: AccessSession,
    grant: AutomationGrant,
    key: ApiKeyRecord | None,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> AccessDenialCode | None:
    """Require unattended custody, exact key lineage, and eligible OS login."""
    refusal = _api_key_authority_refusal(grant, profile)
    if refusal is not None:
        return refusal
    refusal = _api_key_record_refusal(session, grant, key, profile, context)
    if refusal is not None:
        return refusal
    eligible = _eligible_api_logins(profile, context)
    if not eligible:
        return AccessDenialCode.OS_SESSION_UNAVAILABLE
    if not grant.allow_os_lock and not any(login.unlocked for login in eligible):
        return AccessDenialCode.OS_LOCKED
    return None


def _api_key_authority_refusal(
    grant: AutomationGrant,
    profile: ProfileAccessState,
) -> AccessDenialCode | None:
    if not grant.unattended:
        return AccessDenialCode.GRANT_INACTIVE
    if profile.automation_custody is not Availability.AVAILABLE:
        return AccessDenialCode.CUSTODY_UNAVAILABLE
    return None


def _api_key_record_refusal(
    session: AccessSession,
    grant: AutomationGrant,
    key: ApiKeyRecord | None,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> AccessDenialCode | None:
    if key is None:
        return AccessDenialCode.KEY_INACTIVE
    if not _api_key_matches_session(session, grant, key, profile):
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
    return None


def _api_key_matches_session(
    session: AccessSession,
    grant: AutomationGrant,
    key: ApiKeyRecord,
    profile: ProfileAccessState,
) -> bool:
    return (
        key.key_id == session.key_id
        and key.generation == session.key_generation
        and key.grant_id == grant.grant_id
        and key.binding == profile.binding
        and key.state is AuthorityState.ACTIVE
    )


def _eligible_api_logins(
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> tuple[OsLoginContext, ...]:
    """Return only live unattended OS sessions for this bound profile owner."""
    return tuple(
        login
        for login in context.login_contexts
        if login.os_owner_id == profile.binding.os_owner_id
        and login.active
        and login.unattended is LoginEligibility.ELIGIBLE
        and login.credential_facilities is Availability.AVAILABLE
    )


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
    refusal = _session_header_refusal(session, context)
    if refusal is not None:
        return AccessDenied(code=refusal)
    chain = (session, *ancestors)
    if len({item.session_id for item in chain}) != len(chain):
        return AccessDenied(code=AccessDenialCode.PARENT_INVALID)
    for index, item in enumerate(chain):
        parent = _lineage_parent(chain, index)
        refusal = _lineage_member_refusal(item, parent, grant, key, profile, context)
        if refusal is not None:
            return AccessDenied(code=refusal)
    if profile.storage is not Availability.AVAILABLE:
        return AccessDenied(code=AccessDenialCode.STORAGE_UNAVAILABLE)
    return AccessAllowed(
        profile_id=session.binding.profile_id, session_id=session.session_id, expires_at=session.expires_at
    )


def _session_header_refusal(
    session: AccessSession,
    context: AccessEvaluationContext,
) -> AccessDenialCode | None:
    if not context.private_work_available:
        return AccessDenialCode.OS_SESSION_UNAVAILABLE
    if session.connection_id != context.connection_id:
        return AccessDenialCode.CONNECTION_MISMATCH
    if session.client_id != context.authenticated_client_id:
        return AccessDenialCode.CLIENT_MISMATCH
    return None


def _lineage_parent(chain: tuple[AccessSession, ...], index: int) -> AccessSession | None:
    return chain[index + 1] if index + 1 < len(chain) else None


def _lineage_member_refusal(
    item: AccessSession,
    parent: AccessSession | None,
    grant: AutomationGrant | None,
    key: ApiKeyRecord | None,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> AccessDenialCode | None:
    """Validate one lease and its relationship to its immediate parent."""
    refusal = _session_refusal(item, profile, context)
    if refusal is not None:
        return refusal
    if item.kind is not SessionKind.HUMAN:
        refusal = _grant_refusal(item, grant, key, profile, context)
        if refusal is not None:
            return refusal
    if item.kind is not SessionKind.API_KEY:
        refusal = _originating_login_refusal(item, context)
        if refusal is not None:
            return refusal
    return _lineage_parent_refusal(item, parent)


def _originating_login_refusal(
    item: AccessSession,
    context: AccessEvaluationContext,
) -> AccessDenialCode | None:
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
        return AccessDenialCode.OS_SESSION_UNAVAILABLE
    if not login.unlocked:
        return AccessDenialCode.OS_LOCKED
    return None


def _lineage_parent_refusal(item: AccessSession, parent: AccessSession | None) -> AccessDenialCode | None:
    if item.parent_session_id != (None if parent is None else parent.session_id):
        return AccessDenialCode.PARENT_INVALID
    if parent is not None:
        return _parent_refusal(item, parent)
    return None


def _parent_refusal(child: AccessSession, parent: AccessSession) -> AccessDenialCode | None:
    if not parent.scope.allow_delegation or not scope_is_subset(child.scope, parent.scope):
        return AccessDenialCode.PRIVILEGE_EXPANSION
    if child.issued_at < parent.issued_at or child.expires_at > parent.expires_at:
        return AccessDenialCode.PRIVILEGE_EXPANSION
    if _api_key_parent_mismatch(child, parent):
        return AccessDenialCode.PARENT_INVALID
    if _attended_parent_mismatch(child, parent):
        return AccessDenialCode.PARENT_INVALID
    return None


def _api_key_parent_mismatch(child: AccessSession, parent: AccessSession) -> bool:
    return child.kind is SessionKind.API_KEY and (
        parent.kind is not SessionKind.API_KEY
        or child.grant_id != parent.grant_id
        or child.key_id != parent.key_id
        or child.client_id != parent.client_id
    )


def _attended_parent_mismatch(child: AccessSession, parent: AccessSession) -> bool:
    return child.kind is SessionKind.ATTENDED and (
        parent.kind not in {SessionKind.HUMAN, SessionKind.ATTENDED}
        or child.originating_login_id != parent.originating_login_id
    )
