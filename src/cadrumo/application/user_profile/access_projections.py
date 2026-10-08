"""Allowlisted non-secret inventory projections of profile-access authority.

Only authorized inventory consumers receive these records. Installation/OS-owner
bindings, custody epochs and clock internals remain inside the lifecycle owner.
Projection never authenticates and never changes the source authority facts.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import UtcInstant
from .access_contracts import (
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
    ProfileAccessState,
    ProfileAccessStatus,
    SessionKind,
    SessionState,
)
from .access_policy import intersect_scopes
from .session_authority_policy import evaluate_session_authority


class PublicAutomationGrant(BaseModel):
    """Authorized grant inventory without protected binding or credential data."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    grant_id: UUID
    profile_id: UUID
    client_id: UUID
    state: AuthorityState
    scope: AccessScope
    valid_from: UtcInstant
    expires_at: UtcInstant
    unattended: bool
    allow_os_lock: bool


class PublicApiKey(BaseModel):
    """Key inventory that cannot be used to prove possession."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key_id: UUID
    grant_id: UUID
    profile_id: UUID
    state: AuthorityState
    valid_from: UtcInstant
    expires_at: UtcInstant
    last_used_at: UtcInstant | None


class PublicAccessSession(BaseModel):
    """Session inventory; IDs are observation identities, never bearers."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    session_id: UUID
    profile_id: UUID
    client_id: UUID
    parent_session_id: UUID | None
    grant_id: UUID | None
    key_id: UUID | None
    kind: SessionKind
    state: SessionState
    scope: AccessScope
    expires_at: UtcInstant


def project_automation_grant(grant: AutomationGrant) -> PublicAutomationGrant:
    """Copy only explicitly public fields from verified grant facts."""
    return PublicAutomationGrant(
        grant_id=grant.grant_id,
        profile_id=grant.binding.profile_id,
        client_id=grant.client_id,
        state=grant.state,
        scope=grant.scope,
        valid_from=grant.valid_from,
        expires_at=grant.expires_at,
        unattended=grant.unattended,
        allow_os_lock=grant.allow_os_lock,
    )


def project_api_key(key: ApiKeyRecord) -> PublicApiKey:
    """Project key validity without a secret, verifier or credential-store locator."""
    return PublicApiKey(
        key_id=key.key_id,
        grant_id=key.grant_id,
        profile_id=key.binding.profile_id,
        state=key.state,
        valid_from=key.valid_from,
        expires_at=key.expires_at,
        last_used_at=key.last_used_at,
    )


def project_access_session(session: AccessSession) -> PublicAccessSession:
    """Project one session without runtime transport or custody details."""
    return PublicAccessSession(
        session_id=session.session_id,
        profile_id=session.binding.profile_id,
        client_id=session.client_id,
        parent_session_id=session.parent_session_id,
        grant_id=session.grant_id,
        key_id=session.key_id,
        kind=session.kind,
        state=session.state,
        scope=session.scope,
        expires_at=session.expires_at,
    )


def _effective_access_scope(
    *,
    allowed: bool,
    session: AccessSession | None,
    ancestors: tuple[AccessSession, ...],
    grant: AutomationGrant | None,
    profile: ProfileAccessState,
) -> AccessScope:
    if not allowed or session is None:
        return intersect_scopes(())
    scopes = (profile.scope, session.scope, *(item.scope for item in ancestors))
    if grant is not None and session.kind is not SessionKind.HUMAN:
        scopes += (grant.scope,)
    return intersect_scopes(scopes)


def _session_status_facts(
    session: AccessSession | None,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
) -> tuple[UUID | None, UUID | None, UtcInstant | None, bool, bool]:
    if session is None:
        return None, None, None, False, False
    credential_authenticated = (
        session.connection_id == context.connection_id
        and session.runtime_boot_id == context.runtime_boot_id
        and session.client_id == context.authenticated_client_id
    )
    return (
        session.binding.profile_id,
        session.session_id,
        session.expires_at,
        session.binding == profile.binding,
        credential_authenticated,
    )


def _grant_status_facts(
    grant: AutomationGrant | None,
    context: AccessEvaluationContext,
) -> tuple[AuthorityState | None, UtcInstant | None, bool]:
    if grant is None:
        return None, None, False
    return (
        grant.state,
        grant.expires_at,
        grant.state is AuthorityState.ACTIVE and grant.valid_from <= context.now < grant.expires_at,
    )


def _status_denial(decision: AccessDecision) -> AccessDenialCode | None:
    return decision.code if isinstance(decision, AccessDenied) else None


def project_access_status(
    *,
    session: AccessSession | None,
    ancestors: tuple[AccessSession, ...],
    grant: AutomationGrant | None,
    key: ApiKeyRecord | None,
    profile: ProfileAccessState,
    context: AccessEvaluationContext,
    published_authority: Availability,
    provider: Availability,
) -> ProfileAccessStatus:
    """Report independently observed facts and currently effective scope.

    This projection presumes an established local connection. Grant/key inventory
    must already be authorized for this caller. Effective scope is empty when
    session authority refuses; operation-specific checks still apply per call.
    """
    decision = evaluate_session_authority(
        session=session,
        ancestors=ancestors,
        grant=grant,
        key=key,
        profile=profile,
        context=context,
    )
    denied = isinstance(decision, AccessDenied)
    profile_id, session_id, session_expires_at, profile_bound, credential_authenticated = _session_status_facts(
        session, profile, context
    )
    grant_state, grant_expires_at, grant_valid = _grant_status_facts(grant, context)
    return ProfileAccessStatus(
        connected=True,
        credential_authenticated=credential_authenticated,
        profile_id=profile_id,
        session_id=session_id,
        session_expires_at=session_expires_at,
        grant_state=grant_state,
        grant_expires_at=grant_expires_at,
        grant_valid=grant_valid,
        profile_bound=profile_bound,
        storage=profile.storage,
        automation_custody=profile.automation_custody,
        published_authority=published_authority,
        provider=provider,
        effective_scope=_effective_access_scope(
            allowed=not denied,
            session=session,
            ancestors=ancestors,
            grant=grant,
            profile=profile,
        ),
        denial=_status_denial(decision),
    )
