"""Synthetic grant, key, session and profile state for operation-access tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from cadrumo_client.contracts.access_refusals import AccessDecision
from cadrumo_client.contracts.access_vocabulary import (
    AccessScope,
    AuthorityState,
    Availability,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)

from ..operations.access_resolution import ResolvedOperationAccess
from ..operations.registry import OperationRegistry
from ..user_profile.access_contracts import (
    AccessEvaluationContext,
    AccessSession,
    ApiKeyRecord,
    AutomationGrant,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
    ProfileAccessBinding,
    ProfileAccessState,
    SessionKind,
    SessionState,
)
from ..user_profile.operation_access_policy import evaluate_operation_access


@dataclass(frozen=True, slots=True)
class AccessAuthority:
    """One active grant, key and session over a profile, with their evaluation context."""

    binding: ProfileAccessBinding
    profile: ProfileAccessState
    grant: AutomationGrant
    key: ApiKeyRecord
    session: AccessSession
    context: AccessEvaluationContext
    human: bool = False

    def evaluate(
        self,
        *,
        registry: OperationRegistry,
        request: OperationAccessRequest,
        policy: OperationAccessPolicy,
        ancestors: tuple[AccessSession, ...] = (),
    ) -> AccessDecision:
        """Evaluate ``request`` as this session; a human session carries no grant or key."""
        return evaluate_operation_access(
            request=request,
            policy=policy,
            registry=registry,
            session=self.session,
            ancestors=ancestors,
            grant=None if self.human else self.grant,
            key=None if self.human else self.key,
            profile=self.profile,
            context=self.context,
        )


def new_access_binding(profile_id: UUID) -> ProfileAccessBinding:
    """Return a fresh synthetic installation binding for ``profile_id``."""
    return ProfileAccessBinding(
        profile_id=profile_id,
        installation_id=uuid4(),
        os_owner_id="synthetic-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    )


def build_access_authority(
    *,
    binding: ProfileAccessBinding,
    now: datetime,
    grant_scope: AccessScope,
    session_scope: AccessScope | None = None,
    profile_scope: AccessScope | None = None,
    human: bool = False,
    grant_validity: timedelta = timedelta(days=1),
    session_lease: timedelta = timedelta(minutes=2),
    allow_os_lock: bool = False,
    login_id: str = "synthetic-login",
    client_id: UUID | None = None,
) -> AccessAuthority:
    """Build an active authority; scopes default to ``grant_scope``.

    ``human`` makes the session a human login session instead of an API-key session;
    the grant and key are still built so a caller can evaluate the other kind.
    """
    client = client_id if client_id is not None else uuid4()
    grant = AutomationGrant(
        grant_id=uuid4(),
        binding=binding,
        client_id=client,
        generation=1,
        profile_lock_generation=0,
        state=AuthorityState.ACTIVE,
        scope=grant_scope,
        valid_from=now - timedelta(days=1),
        expires_at=now + grant_validity,
        unattended=True,
        allow_os_lock=allow_os_lock,
    )
    key = ApiKeyRecord(
        key_id=uuid4(),
        grant_id=grant.grant_id,
        binding=binding,
        generation=1,
        state=AuthorityState.ACTIVE,
        valid_from=grant.valid_from,
        expires_at=grant.expires_at,
    )
    session = AccessSession(
        session_id=uuid4(),
        binding=binding,
        profile_lock_generation=0,
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        client_id=client,
        kind=SessionKind.HUMAN if human else SessionKind.API_KEY,
        originating_login_id=login_id if human else None,
        state=SessionState.ACTIVE,
        scope=session_scope if session_scope is not None else grant_scope,
        grant_id=None if human else grant.grant_id,
        grant_generation=None if human else grant.generation,
        key_id=None if human else key.key_id,
        key_generation=None if human else key.generation,
        issued_at=now,
        expires_at=now + session_lease,
        issued_monotonic=100.0,
    )
    return AccessAuthority(
        binding=binding,
        profile=ProfileAccessState(
            binding=binding,
            lock_generation=0,
            globally_locked=False,
            automation_enabled=True,
            scope=profile_scope if profile_scope is not None else grant_scope,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.AVAILABLE,
        ),
        grant=grant,
        key=key,
        session=session,
        context=AccessEvaluationContext(
            now=now,
            monotonic_now=100.0,
            clock_rollback_detected=False,
            runtime_boot_id=session.runtime_boot_id,
            connection_id=session.connection_id,
            authenticated_client_id=client,
            login_contexts=(
                OsLoginContext(
                    login_id=login_id,
                    os_owner_id=binding.os_owner_id,
                    active=True,
                    lock_state=OsLockState.UNLOCKED,
                    unattended=LoginEligibility.ELIGIBLE,
                    credential_facilities=Availability.AVAILABLE,
                ),
            ),
            private_work_available=True,
        ),
        human=human,
    )


def scoped_policy_decision(
    resolved: ResolvedOperationAccess,
    registry: OperationRegistry,
    *,
    profile_id: UUID,
    now: datetime,
    disclosures: frozenset[DisclosurePermission],
    all_periods: bool = True,
    operations: frozenset[str] | None = None,
    human: bool = False,
) -> AccessDecision:
    """Evaluate ``resolved`` for a session whose scope is exactly the request's operation and action."""
    scope = AccessScope(
        operations=operations if operations is not None else frozenset({resolved.request.definition_id}),
        actions=frozenset({resolved.request.action}),
        disclosures=disclosures,
        periods=None if all_periods else frozenset(),
        allow_period_independent=True,
        allow_delegation=False,
    )
    authority = build_access_authority(
        binding=new_access_binding(profile_id),
        now=now,
        grant_scope=scope,
        human=human,
    )
    return authority.evaluate(registry=registry, request=resolved.request, policy=resolved.policy)
