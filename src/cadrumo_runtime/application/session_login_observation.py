"""Classify a lease's originating OS login against the runtime's current observation."""

from __future__ import annotations

from cadrumo.application.user_profile.access_contracts import AccessSession, LoginEligibility, OsLockState
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied
from cadrumo_client.contracts.session_policy import session_requires_grant

from .session_authority_contracts import SessionAuthorityFacts


def observable_login_ids(facts: SessionAuthorityFacts, os_owner_id: str) -> set[str]:
    """Keep live and uncertain owner logins distinct from positively absent ones."""
    live_logins = {
        login.login_id
        for login in facts.context.login_contexts
        if login.active and login.unlocked and login.os_owner_id == os_owner_id
    }
    uncertain_logins = {
        login.login_id
        for login in facts.context.login_contexts
        if login.os_owner_id == os_owner_id
        and login.lock_state is OsLockState.UNKNOWN
        and login.unattended is LoginEligibility.UNKNOWN
    }
    return live_logins | uncertain_logins


def unavailable_observation_reason(session: AccessSession, facts: SessionAuthorityFacts) -> str:
    """Describe an admission observation without exposing session or owner IDs."""
    if not facts.context.private_work_available:
        return "private_work_unavailable"
    if session_requires_grant(session):
        return "unattended_login_unavailable"
    return _originating_login_reason(session, facts)


def _originating_login_reason(session: AccessSession, facts: SessionAuthorityFacts) -> str:
    """Name which observation of the session's own originating login is missing or uncertain."""
    matching = tuple(
        login
        for login in facts.context.login_contexts
        if login.login_id == session.originating_login_id and login.os_owner_id == session.binding.os_owner_id
    )
    if not matching:
        return "originating_login_absent"
    active = next((login for login in matching if login.active), None)
    if active is None:
        return "originating_login_inactive"
    if active.lock_state is OsLockState.UNKNOWN:
        return "originating_lock_unknown"
    return "ancestor_or_other_observation_unavailable"


def uncertain_login_denial(session: AccessSession, facts: SessionAuthorityFacts, decision: AccessDenied) -> bool:
    """Observation failure denies work without turning uncertainty into logout."""
    return decision.code is AccessDenialCode.OS_SESSION_UNAVAILABLE and any(
        login.login_id == session.originating_login_id
        and login.os_owner_id == session.binding.os_owner_id
        and login.lock_state is OsLockState.UNKNOWN
        and login.unattended is LoginEligibility.UNKNOWN
        for login in facts.context.login_contexts
    )
