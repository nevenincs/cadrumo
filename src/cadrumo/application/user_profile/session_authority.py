"""Connection-bound access leases over existing custody and authorization policy.

The authority retains non-secret live leases only. Its owner supplies verified
transport/login observations, the shared lifecycle fence and profile-bound key
custody. None of these ports accepts facts deserialized from a client request.
Durable grants remain in the existing automation control store.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, ExitStack, contextmanager
from dataclasses import dataclass
from datetime import timedelta
from math import isfinite
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import SecretBytes

from ...core.async_cleanup import AsyncResourceCleanupError
from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.time.utc import UtcInstant
from ..operations.registry import OperationRegistry
from .access_administration import (
    AccessAdministrationAction,
    AccessAdministrationRequest,
    evaluate_access_administration,
)
from .access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessAllowed,
    AccessDecision,
    AccessDenialCode,
    AccessDenied,
    AccessEvaluationContext,
    AccessScope,
    AccessSession,
    ApiKeyRecord,
    AutomationGrant,
    Availability,
    OperationAccessPolicy,
    OperationAccessRequest,
    OperationResponseScopeAllowed,
    ProfileAccessBinding,
    ProfileAccessState,
    ProfileAccessStatus,
    SessionKind,
    SessionState,
)
from .access_errors import ProfileAccessRefusedError
from .access_policy import (
    evaluate_operation_access,
    evaluate_response_scope,
    evaluate_session_authority,
    intersect_scopes,
)
from .access_projections import PublicAccessSession, project_access_session, project_access_status
from .automation_custody_port import AutomationCustodyError, AutomationCustodyPort, AutomationCustodySnapshot
from .automation_enrollment import AdministrationFacts, AutomationKeyIssuer
from .automation_lifecycle import AutomationDenial, AutomationDenialKind
from .login_session import ProfileLoginOutcome


@dataclass(frozen=True)
class SessionAuthorityFacts:
    """Fresh observations from the lifecycle and authenticated transport owners."""

    profile: ProfileAccessState
    context: AccessEvaluationContext


class SessionAuthorityOwner(Protocol):
    """Trusted host integration; never a frontend request or alternate login service."""

    def admission_guard(self) -> AbstractContextManager[None]:
        """Share the denial fence with administration, revocation and private effects."""
        ...

    def facts(self, connection_id: UUID) -> SessionAuthorityFacts:
        """Reobserve the exact live connection, clocks, profile and OS login contexts."""
        ...

    def prepare_api_admission(self, connection_id: UUID) -> AbstractContextManager[float]:
        """Prepare the exact worker without keys or leases; lend its original deadline.

        Preparation leaves the shared denial guard. Activation must use that same
        worker and connection, within the remaining original preparation budget.
        Exiting this context never publishes an application lease.
        """
        ...

    def activate(self, session: AccessSession, dek: bytearray) -> None:
        """Copy borrowed material into exact-profile worker custody or raise.

        Failure must retire any partially installed worker custody. The borrowed
        buffer is wiped by the caller; it must not be retained. No active-profile
        selector or process-global human deadline may be changed here.
        """
        ...

    def retire(self, session_id: UUID) -> None:
        """Fence and release lease custody; an uninstalled/already retired ID is a no-op."""
        ...

    def share(self, session: AccessSession, parent: AccessSession) -> None:
        """Attach a narrowed child to the parent's profile custody or raise atomically."""
        ...

    def refresh(self, session: AccessSession) -> None:
        """Apply the reauthorized root lease to its existing exact-profile worker."""
        ...

    def bind_human(self, session: AccessSession) -> None:
        """Attach this lease to the exact worker admitted by authenticate_human."""
        ...

    def human_admission_deadline(self, connection_id: UUID) -> float:
        """Lend the original monotonic preparation bound for this exact candidate."""
        ...

    def authenticate_human(self, connection_id: UUID) -> AbstractContextManager[tuple[ProfileLoginOutcome, str] | None]:
        """Use the existing profile admission/login lifecycle in its bound worker.

        Lend its verified login outcome and originating native login identity.
        The call may reuse valid human admission but must never promote an API
        session, synthesize a login outcome or renew a deadline for agent activity.
        Release candidate custody on every exit unless bind_human committed it;
        a failed candidate must not retire another connection's existing custody.
        """
        ...


class _ProspectiveSessionRetirement:
    """Retain one prospective lease whose original physical retirement failed."""

    def __init__(self, owner: SessionAuthorityOwner, release: Callable[[], None]) -> None:
        self.owner, self._release = owner, release
        self._released = False

    def close_now(self) -> None:
        with self.owner.admission_guard():
            if not self._released:
                self._release()
                self._released = True

    async def close(self) -> None:
        await asyncio.to_thread(self.close_now)

    def retain_failure(self, primary: BaseException, cleanup: AsyncResourceCleanupError) -> None:
        seen: set[int] = set()
        for field in ("async_cleanup_error", "cleanup_error"):
            previous = primary.__dict__.get(field)
            if isinstance(previous, AsyncResourceCleanupError) and id(previous) not in seen:
                seen.add(id(previous))
                cleanup = previous.merged_with(cleanup)
        primary.__dict__["async_cleanup_error"] = cleanup
        primary.add_note("Prospective session retirement failed; cleanup owner retained")
        if isinstance(primary, asyncio.CancelledError):
            primary.__dict__["cleanup_error"] = cleanup


class ProfileSessionAuthority:
    """One profile's ephemeral leases for one runtime boot, serialized by its owner."""

    def __init__(
        self,
        *,
        binding: ProfileAccessBinding,
        runtime_boot_id: UUID,
        owner: SessionAuthorityOwner,
        custody: AutomationCustodyPort,
        issuer: AutomationKeyIssuer,
    ) -> None:
        """Bind trusted collaborators; construction grants no session authority."""
        self.binding = binding
        self.runtime_boot_id = runtime_boot_id
        self.owner = owner
        self.custody = custody
        self.issuer = issuer
        self._sessions: dict[UUID, AccessSession] = {}
        self._pending_retirements: set[UUID] = set()
        self._last_observation: tuple[UtcInstant, float] | None = None
        self._closed = False

    def _facts(self, connection_id: UUID) -> SessionAuthorityFacts | AccessDenied:
        if self._closed:
            return AccessDenied(code=AccessDenialCode.RUNTIME_CHANGED)
        facts = self.owner.facts(connection_id)
        if facts.context.connection_id != connection_id:
            return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
        if facts.context.runtime_boot_id != self.runtime_boot_id:
            return AccessDenied(code=AccessDenialCode.RUNTIME_CHANGED)
        if facts.profile.binding != self.binding:
            return AccessDenied(code=AccessDenialCode.CUSTODY_CHANGED)
        observed = (facts.context.now, facts.context.monotonic_now)
        previous = self._last_observation
        self._last_observation = observed
        if facts.context.clock_rollback_detected or (
            previous is not None and (observed[0] < previous[0] or observed[1] < previous[1])
        ):
            self._retire(set(self._sessions))
            return AccessDenied(code=AccessDenialCode.CLOCK_INVALID)
        live_logins = {
            login.login_id
            for login in facts.context.login_contexts
            if login.active and not login.locked and login.os_owner_id == self.binding.os_owner_id
        }
        self._retire(
            {
                session.session_id
                for session in self._sessions.values()
                if session.originating_login_id is not None and session.originating_login_id not in live_logins
            }
        )
        return facts

    def _snapshot(self, facts: SessionAuthorityFacts) -> AutomationCustodySnapshot | AccessDenied:
        snapshot = self.custody.snapshot()
        if snapshot.binding != self.binding:
            return AccessDenied(code=AccessDenialCode.CUSTODY_CHANGED)
        if snapshot.profile_lock_generation != facts.profile.lock_generation:
            return AccessDenied(code=AccessDenialCode.PROFILE_LOCKED)
        if not snapshot.automation_enabled:
            return AccessDenied(code=AccessDenialCode.AUTOMATION_SUSPENDED)
        return snapshot

    def _ancestors(self, session: AccessSession) -> tuple[AccessSession, ...]:
        result: list[AccessSession] = []
        seen = {session.session_id}
        parent_id = session.parent_session_id
        while parent_id is not None and parent_id not in seen:
            parent = self._sessions.get(parent_id)
            if parent is None:
                break
            seen.add(parent_id)
            result.append(parent)
            parent_id = parent.parent_session_id
        return tuple(result)

    @staticmethod
    def _records(
        snapshot: AutomationCustodySnapshot, *, key_id: UUID | None, grant_id: UUID | None = None
    ) -> tuple[AutomationGrant | None, ApiKeyRecord | None]:
        keys = tuple(item for item in snapshot.keys if item.key_id == key_id)
        key = keys[0] if len(keys) == 1 else None
        target = key.grant_id if key is not None else grant_id
        grants = tuple(item for item in snapshot.grants if item.grant_id == target)
        return (grants[0] if len(grants) == 1 else None), key

    def _evaluate(
        self,
        session: AccessSession,
        facts: SessionAuthorityFacts,
        grant: AutomationGrant | None,
        key: ApiKeyRecord | None,
    ) -> AccessDecision:
        decision = evaluate_session_authority(
            session=session,
            ancestors=self._ancestors(session),
            grant=grant,
            key=key,
            profile=facts.profile,
            context=facts.context,
        )
        if (
            isinstance(decision, AccessDenied)
            and session.session_id in self._sessions
            and decision.code not in {AccessDenialCode.CONNECTION_MISMATCH, AccessDenialCode.CLIENT_MISMATCH}
        ):
            self._retire({session.session_id})
        return decision

    @contextmanager
    def _activation(self, session_id: UUID) -> Generator[None]:
        # A resource's exit may fail after the host accepted custody. The lease
        # is still unpublished, and the host must relinquish that candidate too.
        try:
            yield
        except BaseException:
            self._retire({session_id})
            raise

    def admit_api_key(
        self, *, connection_id: UUID, target: ProfileAccessBinding, credential: SecretBytes, scope: AccessScope
    ) -> AccessSession | AccessDenied:
        """Prove key possession and admit a fresh lease without any human session.

        The transport verifies the native peer before providing this credential.
        A parsed key identifier is routing only; unwrap must prove possession.
        Both durable state and trusted lifecycle facts are checked again after it.
        """
        identity = uuid4()
        with self.owner.admission_guard():
            if target != self.binding:
                return AccessDenied(code=AccessDenialCode.PROFILE_MISMATCH)
            facts = self._facts(connection_id)
            if isinstance(facts, AccessDenied):
                return facts
            snapshot = self._snapshot(facts)
            if isinstance(snapshot, AccessDenied):
                return snapshot
            key_id, _ = self.issuer.verifier(credential)
            grant, key = self._records(snapshot, key_id=key_id)
            if grant is None or key is None:
                return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
            expires = min(facts.context.now + ACCESS_LEASE_MAXIMUM, grant.expires_at, key.expires_at)
            if expires <= facts.context.now:
                return AccessDenied(code=AccessDenialCode.KEY_EXPIRED)
            session = AccessSession(
                session_id=identity,
                binding=self.binding,
                profile_lock_generation=facts.profile.lock_generation,
                runtime_boot_id=self.runtime_boot_id,
                connection_id=connection_id,
                client_id=facts.context.authenticated_client_id,
                kind=SessionKind.API_KEY,
                state=SessionState.ACTIVE,
                scope=intersect_scopes((scope, grant.scope, facts.profile.scope)),
                grant_id=grant.grant_id,
                grant_generation=grant.generation,
                key_id=key.key_id,
                key_generation=key.generation,
                issued_at=facts.context.now,
                expires_at=expires,
                issued_monotonic=facts.context.monotonic_now,
            )
            decision = self._evaluate(session, facts, grant, key)
            if isinstance(decision, AccessDenied):
                return decision
        committed = False
        binding_attempted = False
        primary: BaseException | None = None
        retirement = _ProspectiveSessionRetirement(self.owner, lambda: self._retire({identity}))
        try:
            with ExitStack() as preparation:
                deadline = preparation.enter_context(self.owner.prepare_api_admission(connection_id))
                with self.owner.admission_guard():
                    current = self._facts(connection_id)
                    if isinstance(current, AccessDenied):
                        return current
                    if not isfinite(deadline) or current.context.monotonic_now >= deadline:
                        return AccessDenied(code=AccessDenialCode.SESSION_EXPIRED)
                    if current.profile.lock_generation != facts.profile.lock_generation:
                        return AccessDenied(code=AccessDenialCode.PROFILE_LOCKED)
                    latest = self._snapshot(current)
                    if isinstance(latest, AccessDenied):
                        return latest
                    if latest != snapshot:
                        return AccessDenied(code=AccessDenialCode.CUSTODY_CHANGED)
                    decision = self._evaluate(session, current, grant, key)
                    if isinstance(decision, AccessDenied):
                        return decision
                    # Unwrap, exact-worker installation and the borrowed-buffer
                    # wipe remain serialized with durable denial and revocation.
                    with self.custody.unlocked(credential=credential, now=current.context.now) as dek:
                        current = self._facts(connection_id)
                        if isinstance(current, AccessDenied):
                            return current
                        if current.context.monotonic_now >= deadline:
                            return AccessDenied(code=AccessDenialCode.SESSION_EXPIRED)
                        latest = self._snapshot(current)
                        if isinstance(latest, AccessDenied):
                            return latest
                        if latest != snapshot:
                            return AccessDenied(code=AccessDenialCode.CUSTODY_CHANGED)
                        decision = self._evaluate(session, current, grant, key)
                        if isinstance(decision, AccessDenied):
                            return decision
                        binding_attempted = True
                        self.owner.activate(session, dek)
                    # The key-free context's successful finalizer only releases
                    # its preparation reservation. Keep material admission and
                    # publication atomic against queued revocation; no lease
                    # escapes a failed finalizer or an expired original bound.
                    preparation.close()
                    current = self._facts(connection_id)
                    if isinstance(current, AccessDenied):
                        return current
                    if current.context.monotonic_now >= deadline:
                        return AccessDenied(code=AccessDenialCode.SESSION_EXPIRED)
                    latest = self._snapshot(current)
                    if isinstance(latest, AccessDenied):
                        return latest
                    if latest != snapshot:
                        return AccessDenied(code=AccessDenialCode.CUSTODY_CHANGED)
                    decision = self._evaluate(session, current, grant, key)
                    if isinstance(decision, AccessDenied):
                        return decision
                    self._sessions[identity] = session
                    committed = True
                    return session
        except BaseException as error:
            primary = error
            raise
        finally:
            if binding_attempted and not committed:
                try:
                    retirement.close_now()
                except BaseException as failure:
                    cleanup = AsyncResourceCleanupError(
                        (retirement,), (failure,), retry_task_name="api-session-retirement", close_attempts=1
                    )
                    if primary is not None:
                        retirement.retain_failure(primary, cleanup)
                    else:
                        raise cleanup from failure

    def admit_human(self, *, connection_id: UUID) -> AccessSession | AccessDenied:
        """Bind existing password admission without consulting automation custody."""
        with self.owner.admission_guard():
            facts = self._facts(connection_id)
            if isinstance(facts, AccessDenied):
                return facts
        identity = uuid4()
        committed = False
        binding_attempted = False
        primary: BaseException | None = None
        retirement = _ProspectiveSessionRetirement(self.owner, lambda: self._retire({identity}))
        try:
            with self.owner.authenticate_human(connection_id) as authenticated:
                if authenticated is None:
                    return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
                outcome, login_id = authenticated
                deadline = self.owner.human_admission_deadline(connection_id)
                if str(outcome.bucket_id) != str(self.binding.profile_id):
                    return AccessDenied(code=AccessDenialCode.PROFILE_MISMATCH)
                with self.owner.admission_guard():
                    current = self._facts(connection_id)
                    if isinstance(current, AccessDenied):
                        return current
                    if not isfinite(deadline) or current.context.monotonic_now >= deadline:
                        return AccessDenied(code=AccessDenialCode.SESSION_EXPIRED)
                    if current.profile.lock_generation != facts.profile.lock_generation:
                        return AccessDenied(code=AccessDenialCode.PROFILE_LOCKED)
                    if current.context.authenticated_client_id != facts.context.authenticated_client_id:
                        return AccessDenied(code=AccessDenialCode.CLIENT_MISMATCH)
                    expires = min(outcome.idle_deadline, outcome.absolute_deadline)
                    if expires <= current.context.now or outcome.authenticated_at > current.context.now:
                        return AccessDenied(code=AccessDenialCode.SESSION_EXPIRED)
                    session = AccessSession(
                        session_id=identity,
                        binding=self.binding,
                        profile_lock_generation=facts.profile.lock_generation,
                        runtime_boot_id=self.runtime_boot_id,
                        connection_id=connection_id,
                        client_id=facts.context.authenticated_client_id,
                        kind=SessionKind.HUMAN,
                        originating_login_id=login_id,
                        state=SessionState.ACTIVE,
                        scope=current.profile.scope,
                        issued_at=current.context.now,
                        expires_at=expires,
                        issued_monotonic=current.context.monotonic_now,
                    )
                    decision = self._evaluate(session, current, None, None)
                    if isinstance(decision, AccessDenied):
                        return decision
                    binding_attempted = True
                    self.owner.bind_human(session)
            # Candidate release may fail or overlap denial. Publish only after
            # it settles and the original generation is freshly reauthorized.
            with self.owner.admission_guard():
                current = self._facts(connection_id)
                if isinstance(current, AccessDenied):
                    return current
                if not isfinite(deadline) or current.context.monotonic_now >= deadline:
                    return AccessDenied(code=AccessDenialCode.SESSION_EXPIRED)
                decision = self._evaluate(session, current, None, None)
                if isinstance(decision, AccessDenied):
                    return decision
                self._sessions[identity] = session
                committed = True
                return session
        except BaseException as error:
            primary = error
            raise
        finally:
            if binding_attempted and not committed:
                try:
                    retirement.close_now()
                except BaseException as failure:
                    cleanup = AsyncResourceCleanupError(
                        (retirement,), (failure,), retry_task_name="human-session-retirement", close_attempts=1
                    )
                    if primary is not None:
                        retirement.retain_failure(primary, cleanup)
                    else:
                        raise cleanup from failure

    def refresh_api_key(self, *, connection_id: UUID, session_id: UUID) -> AccessSession | AccessDenied:
        """Refresh a live root API lease; expired or disconnected leases require login."""
        with self.owner.admission_guard():
            session = self._sessions.get(session_id)
            if session is None:
                return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
            if session.kind is not SessionKind.API_KEY or session.parent_session_id is not None:
                return AccessDenied(code=AccessDenialCode.PARENT_INVALID)
            facts = self._facts(connection_id)
            if isinstance(facts, AccessDenied):
                return facts
            snapshot = self._snapshot(facts)
            if isinstance(snapshot, AccessDenied):
                self._retire({session_id})
                return snapshot
            grant, key = self._records(snapshot, key_id=session.key_id)
            decision = self._evaluate(session, facts, grant, key)
            if isinstance(decision, AccessDenied):
                return decision
            if grant is None or key is None:
                return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
            refreshed = AccessSession.model_validate(
                {
                    **{name: getattr(session, name) for name in AccessSession.model_fields},
                    "issued_at": facts.context.now,
                    "issued_monotonic": facts.context.monotonic_now,
                    "expires_at": min(facts.context.now + ACCESS_LEASE_MAXIMUM, grant.expires_at, key.expires_at),
                }
            )
            # Descendants were clipped to the previous monotonic budget. They
            # must be freshly delegated, never silently inherit the new budget.
            self._retire({s.session_id for s in self._sessions.values() if s.parent_session_id == session_id})
            with self._activation(session_id):
                self.owner.refresh(refreshed)
            self._sessions[session_id] = refreshed
            return refreshed

    def delegate(
        self,
        *,
        connection_id: UUID,
        parent_session_id: UUID,
        recipient_connection_id: UUID,
        grant_id: UUID,
        scope: AccessScope,
    ) -> AccessSession | AccessDenied:
        """Issue a narrowed child to a separately verified recipient connection."""
        with self.owner.admission_guard():
            parent = self._sessions.get(parent_session_id)
            if parent is None:
                return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
            facts = self._facts(connection_id)
            recipient = self._facts(recipient_connection_id)
            if isinstance(facts, AccessDenied):
                return facts
            if isinstance(recipient, AccessDenied):
                return recipient
            snapshot = self._snapshot(recipient)
            if isinstance(snapshot, AccessDenied):
                return snapshot
            grant, key = self._records(snapshot, key_id=parent.key_id, grant_id=grant_id)
            if grant is None or grant.grant_id != grant_id:
                return AccessDenied(code=AccessDenialCode.GRANT_INACTIVE)
            decision = self._evaluate(parent, facts, grant, key)
            if isinstance(decision, AccessDenied):
                return decision
            remaining = (parent.expires_at - parent.issued_at).total_seconds() - (
                recipient.context.monotonic_now - parent.issued_monotonic
            )
            expires = min(
                recipient.context.now + ACCESS_LEASE_MAXIMUM,
                recipient.context.now + timedelta(seconds=max(0, remaining)),
                parent.expires_at,
                grant.expires_at,
            )
            if expires <= recipient.context.now:
                return AccessDenied(code=AccessDenialCode.SESSION_EXPIRED)
            child = AccessSession(
                session_id=uuid4(),
                binding=self.binding,
                profile_lock_generation=recipient.profile.lock_generation,
                runtime_boot_id=self.runtime_boot_id,
                connection_id=recipient_connection_id,
                client_id=recipient.context.authenticated_client_id,
                kind=SessionKind.API_KEY if parent.kind is SessionKind.API_KEY else SessionKind.ATTENDED,
                originating_login_id=parent.originating_login_id,
                state=SessionState.ACTIVE,
                scope=intersect_scopes((scope, parent.scope, grant.scope, recipient.profile.scope)),
                parent_session_id=parent.session_id,
                grant_id=grant.grant_id,
                grant_generation=grant.generation,
                key_id=parent.key_id,
                key_generation=parent.key_generation,
                issued_at=recipient.context.now,
                issued_monotonic=recipient.context.monotonic_now,
                expires_at=expires,
            )
            decision = self._evaluate(child, recipient, grant, key)
            if isinstance(decision, AccessDenied):
                return decision
            with self._activation(child.session_id):
                self.owner.share(child, parent)
            self._sessions[child.session_id] = child
            return child

    def disconnect(self, connection_id: UUID) -> None:
        """Irreversibly retire this connection and all of its dependent leases."""
        with self.owner.admission_guard():
            retired = {item.session_id for item in self._sessions.values() if item.connection_id == connection_id}
            self._retire(retired)

    def revalidate_sessions(self) -> tuple[UUID, ...]:
        """Fence expired or newly ineligible leases during host lifecycle polling.

        The host calls this even when no frontend asks for output. Loss of the
        optional automation store retires automation custody while leaving
        independently valid password sessions available.
        """
        with self.owner.admission_guard():
            return self._revalidate_sessions_locked()

    def _revalidate_sessions_locked(self) -> tuple[UUID, ...]:
        """Run the one canonical lease sweep while the admission fence is held."""
        before = set(self._sessions)
        for connection_id in {session.connection_id for session in self._sessions.values()}:
            connected = {item.session_id for item in self._sessions.values() if item.connection_id == connection_id}
            try:
                facts = self._facts(connection_id)
            except AutomationCustodyError:
                self._retire(connected)
                continue
            if isinstance(facts, AccessDenied):
                self._retire(connected)
                continue
            current = tuple(item for item in self._sessions.values() if item.connection_id == connection_id)
            snapshot = None
            if any(item.kind is not SessionKind.HUMAN for item in current):
                try:
                    observed = self._snapshot(facts)
                    if not isinstance(observed, AccessDenied):
                        snapshot = observed
                except AutomationCustodyError:
                    pass
            for session in current:
                if session.session_id not in self._sessions:
                    continue
                if session.kind is SessionKind.HUMAN:
                    self._evaluate(session, facts, None, None)
                elif snapshot is None:
                    self._retire({session.session_id})
                else:
                    grant, key = self._records(snapshot, key_id=session.key_id, grant_id=session.grant_id)
                    self._evaluate(session, facts, grant, key)
        if self._pending_retirements:
            self._retire(self._pending_retirements.copy())
        return tuple(sorted(before - self._sessions.keys()))

    def session_inventory(self, *, connection_id: UUID, session_id: UUID) -> tuple[PublicAccessSession, ...]:
        """Project all currently live leases only for the exact human owner.

        IDs in this result are observation identities, never authority. The
        lifecycle sweep and final caller check share one admission fence.
        """
        with self.owner.admission_guard():
            self._human_administration_facts_locked(connection_id, session_id)
            self._revalidate_sessions_locked()
            self._human_administration_facts_locked(connection_id, session_id)
            return tuple(
                project_access_session(session)
                for session in sorted(self._sessions.values(), key=lambda item: item.session_id)
            )

    def _current_operation_authority(
        self, connection_id: UUID, session_id: UUID
    ) -> tuple[SessionAuthorityFacts, AccessSession, AutomationGrant | None, ApiKeyRecord | None]:
        """Reobserve authority only while the caller holds the admission guard."""
        facts = self._facts(connection_id)
        if isinstance(facts, AccessDenied):
            raise ProfileAccessRefusedError(facts.code)
        session = self._sessions.get(session_id)
        if session is None:
            raise ProfileAccessRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED)
        grant, key = None, None
        if session.kind is not SessionKind.HUMAN:
            snapshot = self._snapshot(facts)
            if isinstance(snapshot, AccessDenied):
                self._retire({session_id})
                raise ProfileAccessRefusedError(snapshot.code)
            grant, key = self._records(snapshot, key_id=session.key_id, grant_id=session.grant_id)
        current = self._evaluate(session, facts, grant, key)
        if isinstance(current, AccessDenied):
            raise ProfileAccessRefusedError(current.code)
        return facts, session, grant, key

    def automation_request_session(self, *, connection_id: UUID, session_id: UUID) -> AccessSession:
        """Resolve an exact root-key lease for an inactive grant-change request.

        This grants no administrative authority. The caller holds the same
        admission fence through request creation and rechecks before delivery.
        Human consent and fresh password proof still own every activation.
        """
        with self.owner.admission_guard():
            _facts, session, grant, key = self._current_operation_authority(connection_id, session_id)
            if session.kind is not SessionKind.API_KEY or session.parent_session_id is not None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            if grant is None or key is None:
                raise ProfileAccessRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED)
            return session

    def human_administration_facts(self, *, connection_id: UUID, session_id: UUID) -> AdministrationFacts:
        """Resolve fresh human facts from live leases, never from frontend identities.

        Administration owners hold this same admission guard through their
        complete read or publication. A returned snapshot alone is no permit.
        """
        with self.owner.admission_guard():
            return self._human_administration_facts_locked(connection_id, session_id)

    def _human_administration_facts_locked(self, connection_id: UUID, session_id: UUID) -> AdministrationFacts:
        """Check exact human authority under the caller's existing guard."""
        facts, session, _, _ = self._current_operation_authority(connection_id, session_id)
        if session.kind is not SessionKind.HUMAN or session.originating_login_id is None:
            raise ProfileAccessRefusedError(AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
        return AdministrationFacts(
            profile=facts.profile,
            context=facts.context,
            originating_login_id=session.originating_login_id,
            session=session,
        )

    @contextmanager
    def operation_guard(
        self,
        *,
        connection_id: UUID,
        session_id: UUID,
        request: OperationAccessRequest,
        policy: OperationAccessPolicy,
        registry: OperationRegistry,
    ) -> Generator[AccessAllowed]:
        """Revalidate and hold the denial fence through one private output or effect.

        Coordinates and policy come from the registered operation owner. This
        context is synchronous and thread-affine: an async host must hold it on
        a dedicated thread through its bounded cross-process effect handshake,
        never carry the RLock across interleaved event-loop tasks.
        """
        with self.owner.admission_guard():
            facts, session, grant, key = self._current_operation_authority(connection_id, session_id)
            allowed = evaluate_operation_access(
                request=request,
                policy=policy,
                registry=registry,
                session=session,
                ancestors=self._ancestors(session),
                grant=grant,
                key=key,
                profile=facts.profile,
                context=facts.context,
            )
            if isinstance(allowed, AccessDenied):
                raise ProfileAccessRefusedError(allowed.code)
            yield allowed

    @contextmanager
    def response_scope_guard(
        self,
        *,
        connection_id: UUID,
        session_id: UUID,
        request: OperationAccessRequest,
        policy: OperationAccessPolicy,
        registry: OperationRegistry,
    ) -> Generator[OperationResponseScopeAllowed]:
        """Hold current profile response permissions, without issuing a transaction proof."""
        with self.owner.admission_guard():
            facts, session, grant, key = self._current_operation_authority(connection_id, session_id)
            allowed = evaluate_response_scope(
                request=request,
                policy=policy,
                registry=registry,
                session=session,
                ancestors=self._ancestors(session),
                grant=grant,
                key=key,
                profile=facts.profile,
                context=facts.context,
            )
            if isinstance(allowed, AccessDenied):
                raise ProfileAccessRefusedError(allowed.code)
            yield allowed

    def lock_session(
        self, *, connection_id: UUID, session_id: UUID, target_session_id: UUID
    ) -> tuple[UUID, ...] | AccessDenied:
        """Allow own-session lock, or a human owner's selected-session revocation."""
        with self.owner.admission_guard():
            facts = self._facts(connection_id)
            if isinstance(facts, AccessDenied):
                return facts
            session = self._sessions.get(session_id)
            grant, key = None, None
            if session is not None and session.kind is not SessionKind.HUMAN:
                snapshot = self._snapshot(facts)
                if isinstance(snapshot, AccessDenied):
                    return snapshot
                grant, key = self._records(snapshot, key_id=session.key_id, grant_id=session.grant_id)
            request = AccessAdministrationRequest(
                request_id=uuid4(),
                profile_id=self.binding.profile_id,
                action=AccessAdministrationAction.LOCK_SESSION,
                target_session_id=target_session_id,
                request_digest=sha256_hex(canonical_json_bytes({"session": str(target_session_id)})),
            )
            decision = evaluate_access_administration(
                request=request,
                session=session,
                ancestors=() if session is None else self._ancestors(session),
                grant=grant,
                key=key,
                profile=facts.profile,
                context=facts.context,
            )
            if isinstance(decision, AccessDenied):
                return decision
            before = set(self._sessions)
            self._retire({target_session_id} & before)
            return tuple(sorted(before - self._sessions.keys()))

    def invalidate_automation(self, change: AutomationDenial) -> None:
        """Trusted lifecycle hook: fence matching leases before durable denial.

        The lifecycle service owns authorization and holds the same guard through
        persistence. Client-supplied denial records cannot invoke this capability.
        """
        with self.owner.admission_guard():
            if change.binding != self.binding:
                raise ValueError("denial does not name this session authority")
            retired = {
                session.session_id
                for session in self._sessions.values()
                if change.kind is AutomationDenialKind.PROFILE_LOCK
                or (change.kind is AutomationDenialKind.ALL and session.kind is not SessionKind.HUMAN)
                or (change.kind is AutomationDenialKind.KEY and session.key_id == change.target_id)
                or (change.kind is AutomationDenialKind.GRANT and session.grant_id == change.target_id)
            }
            self._retire(retired)

    async def close(self) -> None:
        """Retire all live leases through the existing async cleanup protocol.

        The owner supplies bounded worker cleanup. Cancelling this wait does not
        stop the cleanup thread or restore any authority already removed.
        """
        await asyncio.to_thread(self._close)

    def _close(self) -> None:
        with self.owner.admission_guard():
            self._closed = True
            self._retire(set(self._sessions) | self._pending_retirements)

    def invalidate_login(self, login_id: str) -> None:
        """Fence observed human/attended logout or lock without revoking API grants."""
        with self.owner.admission_guard():
            self._retire({s.session_id for s in self._sessions.values() if s.originating_login_id == login_id})

    def _retire(self, retired: set[UUID]) -> None:
        while True:
            dependents = {s.session_id for s in self._sessions.values() if s.parent_session_id in retired}
            if dependents <= retired:
                break
            retired |= dependents
        # Remove authority for the entire cascade before fallible physical cleanup.
        for session_id in retired:
            self._sessions.pop(session_id, None)
        self._pending_retirements.update(retired)
        failures: list[Exception] = []
        for session_id in retired:
            try:
                self.owner.retire(session_id)
            except Exception as error:
                failures.append(error)
            else:
                self._pending_retirements.discard(session_id)
        if failures:
            raise ExceptionGroup("session custody retirement failed", failures)

    def status(
        self,
        *,
        connection_id: UUID,
        session_id: UUID,
        published_authority: Availability,
        provider: Availability,
    ) -> ProfileAccessStatus | AccessDenied:
        """Reevaluate the caller's own lease and use the existing safe projection."""
        with self.owner.admission_guard():
            facts = self._facts(connection_id)
            if isinstance(facts, AccessDenied):
                return facts
            session = self._sessions.get(session_id)
            if session is not None and session.connection_id != connection_id:
                return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
            if session is not None and session.client_id != facts.context.authenticated_client_id:
                return AccessDenied(code=AccessDenialCode.CLIENT_MISMATCH)
            grant, key = None, None
            if session is not None and session.kind is not SessionKind.HUMAN:
                snapshot = self._snapshot(facts)
                if isinstance(snapshot, AccessDenied):
                    self._retire({session_id})
                    return snapshot
                grant, key = self._records(snapshot, key_id=session.key_id, grant_id=session.grant_id)
            if session is not None:
                self._evaluate(session, facts, grant, key)
            return project_access_status(
                session=session,
                ancestors=() if session is None else self._ancestors(session),
                grant=grant,
                key=key,
                profile=facts.profile,
                context=facts.context,
                published_authority=published_authority,
                provider=provider,
            )
