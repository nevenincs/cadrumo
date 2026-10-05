"""Connection-bound access leases over existing custody and authorization policy.

The authority retains non-secret live leases only. Its owner supplies verified
transport/login observations, the shared lifecycle fence and profile-bound key
custody. None of these ports accepts facts deserialized from a client request.
Durable grants remain in the existing automation control store.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import timedelta
from math import isfinite
from uuid import UUID, uuid4

from pydantic import SecretBytes

from ...core.async_cleanup import AsyncResourceCleanupError
from .access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessDenialCode,
    AccessDenied,
    AccessScope,
    AccessSession,
    ApiKeyRecord,
    AutomationGrant,
    ProfileAccessBinding,
    SessionKind,
    SessionState,
)
from .access_policy import intersect_scopes
from .automation_custody_port import AutomationCustodySnapshot
from .login_session import ProfileLoginOutcome
from .session_authority_contracts import SessionAuthorityFacts, SessionAuthorityOwner
from .session_authority_core import SessionAuthorityCore


class _ProspectiveSessionRetirement:
    """Retain one prospective lease whose original physical retirement failed."""

    def __init__(self, owner: SessionAuthorityOwner, release: Callable[[], None]) -> None:
        self.owner, self._release = owner, release
        self._released = False
        self.binding_attempted = False
        self.committed = False

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

    def close_if_uncommitted(self, primary: BaseException | None, *, retry_task_name: str) -> None:
        if not self.binding_attempted or self.committed:
            return
        try:
            self.close_now()
        except BaseException as failure:
            cleanup = AsyncResourceCleanupError((self,), (failure,), retry_task_name=retry_task_name, close_attempts=1)
            if primary is not None:
                self.retain_failure(primary, cleanup)
            else:
                raise cleanup from failure


@dataclass(frozen=True)
class _ApiKeyAdmissionCandidate:
    connection_id: UUID
    facts: SessionAuthorityFacts
    snapshot: AutomationCustodySnapshot
    grant: AutomationGrant
    key: ApiKeyRecord
    session: AccessSession


@dataclass(frozen=True)
class _HumanAdmissionCandidate:
    deadline: float
    session: AccessSession


class SessionAuthorityAdmission(SessionAuthorityCore):
    """Authenticate and publish human or API-key session leases."""

    def _revalidate_admission(
        self: SessionAuthorityAdmission,
        connection_id: UUID,
        *,
        deadline: float,
        snapshot: AutomationCustodySnapshot,
        session: AccessSession,
        grant: AutomationGrant,
        key: ApiKeyRecord,
    ) -> SessionAuthorityFacts | AccessDenied:
        """Re-prove the original admission bound, custody snapshot and authority."""
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
        return current

    def admit_api_key(
        self: SessionAuthorityAdmission,
        *,
        connection_id: UUID,
        target: ProfileAccessBinding,
        credential: SecretBytes,
        scope: AccessScope,
    ) -> AccessSession | AccessDenied:
        """Prove key possession and admit a fresh lease without any human session.

        The transport verifies the native peer before providing this credential.
        A parsed key identifier is routing only; unwrap must prove possession.
        Both durable state and trusted lifecycle facts are checked again after it.
        """
        candidate = self._prepare_api_key_candidate(connection_id, target, credential, scope, uuid4())
        if isinstance(candidate, AccessDenied):
            return candidate
        return self._publish_api_key_candidate(candidate, credential)

    def _prepare_api_key_candidate(
        self: SessionAuthorityAdmission,
        connection_id: UUID,
        target: ProfileAccessBinding,
        credential: SecretBytes,
        scope: AccessScope,
        identity: UUID,
    ) -> _ApiKeyAdmissionCandidate | AccessDenied:
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
            return _ApiKeyAdmissionCandidate(connection_id, facts, snapshot, grant, key, session)

    def _publish_api_key_candidate(
        self: SessionAuthorityAdmission, candidate: _ApiKeyAdmissionCandidate, credential: SecretBytes
    ) -> AccessSession | AccessDenied:
        retirement = _ProspectiveSessionRetirement(self.owner, lambda: self._retire({candidate.session.session_id}))
        primary: BaseException | None = None
        try:
            with ExitStack() as preparation:
                deadline = preparation.enter_context(self.owner.prepare_api_admission(candidate.connection_id))
                refusal = self._activate_api_key_candidate(candidate, credential, deadline, preparation, retirement)
                if isinstance(refusal, AccessDenied):
                    return refusal
                self._sessions[candidate.session.session_id] = candidate.session
                retirement.committed = True
                return candidate.session
        except BaseException as error:
            primary = error
            raise
        finally:
            retirement.close_if_uncommitted(primary, retry_task_name="api-session-retirement")

    def _activate_api_key_candidate(
        self: SessionAuthorityAdmission,
        candidate: _ApiKeyAdmissionCandidate,
        credential: SecretBytes,
        deadline: float,
        preparation: ExitStack,
        retirement: _ProspectiveSessionRetirement,
    ) -> AccessDenied | None:
        with self.owner.admission_guard():
            current = self._facts(candidate.connection_id)
            if isinstance(current, AccessDenied):
                return current
            refusal = self._api_key_preparation_denial(candidate, current, deadline)
            if refusal is not None:
                return refusal
            with self.custody.unlocked(credential=credential, now=current.context.now) as dek:
                current = self._revalidate_admission(
                    candidate.connection_id,
                    deadline=deadline,
                    snapshot=candidate.snapshot,
                    session=candidate.session,
                    grant=candidate.grant,
                    key=candidate.key,
                )
                if isinstance(current, AccessDenied):
                    return current
                retirement.binding_attempted = True
                self.owner.activate(candidate.session, dek)
            preparation.close()
            revalidated = self._revalidate_admission(
                candidate.connection_id,
                deadline=deadline,
                snapshot=candidate.snapshot,
                session=candidate.session,
                grant=candidate.grant,
                key=candidate.key,
            )
            return revalidated if isinstance(revalidated, AccessDenied) else None

    def _api_key_preparation_denial(
        self: SessionAuthorityAdmission,
        candidate: _ApiKeyAdmissionCandidate,
        current: SessionAuthorityFacts,
        deadline: float,
    ) -> AccessDenied | None:
        if not isfinite(deadline) or current.context.monotonic_now >= deadline:
            return AccessDenied(code=AccessDenialCode.SESSION_EXPIRED)
        if current.profile.lock_generation != candidate.facts.profile.lock_generation:
            return AccessDenied(code=AccessDenialCode.PROFILE_LOCKED)
        latest = self._snapshot(current)
        if isinstance(latest, AccessDenied):
            return latest
        if latest != candidate.snapshot:
            return AccessDenied(code=AccessDenialCode.CUSTODY_CHANGED)
        decision = self._evaluate(candidate.session, current, candidate.grant, candidate.key)
        return decision if isinstance(decision, AccessDenied) else None

    def admit_human(self: SessionAuthorityAdmission, *, connection_id: UUID) -> AccessSession | AccessDenied:
        """Bind existing password admission without consulting automation custody."""
        with self.owner.admission_guard():
            facts = self._facts(connection_id)
            if isinstance(facts, AccessDenied):
                return facts
        identity = uuid4()
        retirement = _ProspectiveSessionRetirement(self.owner, lambda: self._retire({identity}))
        primary: BaseException | None = None
        try:
            candidate = self._authenticate_human_candidate(connection_id, identity, facts, retirement)
            if isinstance(candidate, AccessDenied):
                return candidate
            return self._publish_human_candidate(connection_id, candidate, retirement)
        except BaseException as error:
            primary = error
            raise
        finally:
            retirement.close_if_uncommitted(primary, retry_task_name="human-session-retirement")

    def _authenticate_human_candidate(
        self: SessionAuthorityAdmission,
        connection_id: UUID,
        identity: UUID,
        baseline: SessionAuthorityFacts,
        retirement: _ProspectiveSessionRetirement,
    ) -> _HumanAdmissionCandidate | AccessDenied:
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
                refusal = self._human_admission_denial(baseline, current, deadline, outcome)
                if refusal is not None:
                    return refusal
                session = self._human_admission_session(connection_id, identity, current, outcome, login_id)
                decision = self._evaluate(session, current, None, None)
                if isinstance(decision, AccessDenied):
                    return decision
                retirement.binding_attempted = True
                self.owner.bind_human(session)
                return _HumanAdmissionCandidate(deadline, session)

    def _human_admission_denial(
        self: SessionAuthorityAdmission,
        baseline: SessionAuthorityFacts,
        current: SessionAuthorityFacts,
        deadline: float,
        outcome: ProfileLoginOutcome,
    ) -> AccessDenied | None:
        if not isfinite(deadline) or current.context.monotonic_now >= deadline:
            return AccessDenied(code=AccessDenialCode.SESSION_EXPIRED)
        if current.profile.lock_generation != baseline.profile.lock_generation:
            return AccessDenied(code=AccessDenialCode.PROFILE_LOCKED)
        if current.context.authenticated_client_id != baseline.context.authenticated_client_id:
            return AccessDenied(code=AccessDenialCode.CLIENT_MISMATCH)
        expires = min(outcome.idle_deadline, outcome.absolute_deadline)
        if expires <= current.context.now or outcome.authenticated_at > current.context.now:
            return AccessDenied(code=AccessDenialCode.SESSION_EXPIRED)
        return None

    def _human_admission_session(
        self: SessionAuthorityAdmission,
        connection_id: UUID,
        identity: UUID,
        facts: SessionAuthorityFacts,
        outcome: ProfileLoginOutcome,
        login_id: str,
    ) -> AccessSession:
        return AccessSession(
            session_id=identity,
            binding=self.binding,
            profile_lock_generation=facts.profile.lock_generation,
            runtime_boot_id=self.runtime_boot_id,
            connection_id=connection_id,
            client_id=facts.context.authenticated_client_id,
            kind=SessionKind.HUMAN,
            originating_login_id=login_id,
            state=SessionState.ACTIVE,
            scope=facts.profile.scope,
            issued_at=facts.context.now,
            expires_at=min(outcome.idle_deadline, outcome.absolute_deadline),
            issued_monotonic=facts.context.monotonic_now,
        )

    def _publish_human_candidate(
        self: SessionAuthorityAdmission,
        connection_id: UUID,
        candidate: _HumanAdmissionCandidate,
        retirement: _ProspectiveSessionRetirement,
    ) -> AccessSession | AccessDenied:
        with self.owner.admission_guard():
            current = self._facts(connection_id)
            if isinstance(current, AccessDenied):
                return current
            if not isfinite(candidate.deadline) or current.context.monotonic_now >= candidate.deadline:
                return AccessDenied(code=AccessDenialCode.SESSION_EXPIRED)
            decision = self._evaluate(candidate.session, current, None, None)
            if isinstance(decision, AccessDenied):
                return decision
            self._sessions[candidate.session.session_id] = candidate.session
            refusal = self._mint_published_human_receipt(connection_id, candidate.session)
            if refusal is not None:
                return refusal
            retirement.committed = True
            return candidate.session

    def _mint_published_human_receipt(
        self: SessionAuthorityAdmission, connection_id: UUID, session: AccessSession
    ) -> AccessDenied | None:
        """Mint a requested receipt only after publication, for the lease still published.

        The caller holds the admission guard across publication, capture and
        mint, so a sign-out cannot interleave. The owner captures the sign-in
        generation at publication and the mint stamps exactly that capture,
        refusing to write if another writer advanced it since. A lease the
        re-observation retires is refused uncommitted; its retirement discards
        the pending receipt, so none exists.
        """
        if not self.owner.capture_human_sign_in(session.session_id):
            return None
        current = self._facts(connection_id)
        if isinstance(current, AccessDenied):
            return current
        decision = self._evaluate(session, current, None, None)
        if isinstance(decision, AccessDenied):
            return decision
        if self._sessions.get(session.session_id) != session:
            return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
        self.owner.mint_human_receipt(session.session_id)
        return None

    def refresh_api_key(
        self: SessionAuthorityAdmission, *, connection_id: UUID, session_id: UUID
    ) -> AccessSession | AccessDenied:
        """Refresh a live root API lease; expired or disconnected leases require login."""
        with self.owner.admission_guard():
            current = self._api_key_refresh_context(connection_id, session_id)
            if isinstance(current, AccessDenied):
                return current
            session, facts, grant, key = current
            refreshed = self._refreshed_api_key(session, facts, grant, key)
            # Descendants were clipped to the previous monotonic budget. They
            # must be freshly delegated, never silently inherit the new budget.
            self._retire({s.session_id for s in self._sessions.values() if s.parent_session_id == session_id})
            with self._activation(session_id):
                self.owner.refresh(refreshed)
            self._sessions[session_id] = refreshed
            return refreshed

    def _api_key_refresh_context(
        self: SessionAuthorityAdmission, connection_id: UUID, session_id: UUID
    ) -> tuple[AccessSession, SessionAuthorityFacts, AutomationGrant, ApiKeyRecord] | AccessDenied:
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
        return session, facts, grant, key

    @staticmethod
    def _refreshed_api_key(
        session: AccessSession, facts: SessionAuthorityFacts, grant: AutomationGrant, key: ApiKeyRecord
    ) -> AccessSession:
        return AccessSession.model_validate(
            {
                **{name: getattr(session, name) for name in AccessSession.model_fields},
                "issued_at": facts.context.now,
                "issued_monotonic": facts.context.monotonic_now,
                "expires_at": min(facts.context.now + ACCESS_LEASE_MAXIMUM, grant.expires_at, key.expires_at),
            }
        )

    def delegate(
        self: SessionAuthorityAdmission,
        *,
        connection_id: UUID,
        parent_session_id: UUID,
        recipient_connection_id: UUID,
        grant_id: UUID,
        scope: AccessScope,
    ) -> AccessSession | AccessDenied:
        """Issue a narrowed child to a separately verified recipient connection."""
        with self.owner.admission_guard():
            authority = self._delegation_authority(connection_id, recipient_connection_id, parent_session_id, grant_id)
            if isinstance(authority, AccessDenied):
                return authority
            parent, recipient, grant, key = authority
            child = self._delegated_session(parent, recipient, grant, scope, recipient_connection_id)
            if isinstance(child, AccessDenied):
                return child
            decision = self._evaluate(child, recipient, grant, key)
            if isinstance(decision, AccessDenied):
                return decision
            with self._activation(child.session_id):
                self.owner.share(child, parent)
            self._sessions[child.session_id] = child
            return child

    def _delegation_authority(
        self: SessionAuthorityAdmission,
        connection_id: UUID,
        recipient_connection_id: UUID,
        parent_session_id: UUID,
        grant_id: UUID,
    ) -> tuple[AccessSession, SessionAuthorityFacts, AutomationGrant, ApiKeyRecord | None] | AccessDenied:
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
        return parent, recipient, grant, key

    def _delegated_session(
        self: SessionAuthorityAdmission,
        parent: AccessSession,
        recipient: SessionAuthorityFacts,
        grant: AutomationGrant,
        scope: AccessScope,
        recipient_connection_id: UUID,
    ) -> AccessSession | AccessDenied:
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
        return AccessSession(
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
