"""Connection-bound access leases over existing custody and authorization policy.

The authority retains non-secret live leases only. Its owner supplies verified
transport/login observations, the shared lifecycle fence and profile-bound key
custody. None of these ports accepts facts deserialized from a client request.
Durable grants remain in the existing automation control store.
"""

from __future__ import annotations

from contextlib import ExitStack
from math import isfinite
from uuid import UUID, uuid4

from pydantic import SecretBytes

from cadrumo.application.user_profile.access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessSession,
    ApiKeyRecord,
    AutomationGrant,
    ProfileAccessBinding,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.access_policy import intersect_scopes
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodySnapshot
from cadrumo.core.profile_session import ProfileSessionRefusalReason, ReceiptBindingRefusal
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied
from cadrumo_client.contracts.access_vocabulary import AccessScope
from cadrumo_client.contracts.sign_in_outcomes import ProfileLoginOutcome, SignInRefusal

from .session_admission_candidates import (
    ApiKeyAdmissionCandidate,
    HumanAdmissionCandidate,
    ProspectiveSessionRetirement,
)
from .session_authority_contracts import HumanAdmissionControl, SessionAuthorityFacts
from .session_authority_delegation import SessionAuthorityDelegation


def _human_candidate_expired(deadline: float, monotonic_now: float) -> bool:
    """Reject a nonfinite or elapsed proof ownership deadline."""
    return not isfinite(deadline) or monotonic_now >= deadline


def _human_candidate_denial(
    control: HumanAdmissionControl | None, generation: int, current_generation: int
) -> AccessDenied | None:
    """Refuse cancellation or a changed sign-in generation before publication."""
    if control is not None and control.cancelled:
        return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
    if generation != current_generation:
        return AccessDenied(
            code=AccessDenialCode.AUTHENTICATION_REQUIRED,
            sign_in=SignInRefusal(
                reason=ProfileSessionRefusalReason.ABSENT, binding=ReceiptBindingRefusal.GENERATION_CHANGED
            ),
        )
    return None


class SessionAuthorityAdmission(SessionAuthorityDelegation):
    """Authenticate and publish human or API-key session leases, or rebind a suspended one."""

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
    ) -> ApiKeyAdmissionCandidate | AccessDenied:
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
            held = self._held_suspended(connection_id, SessionKind.API_KEY)
            if isinstance(held, AccessDenied):
                return held
            if held is not None:
                return self._api_key_rebind_candidate(held, connection_id, facts, snapshot, grant, key, scope)
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
            return ApiKeyAdmissionCandidate(connection_id, facts, snapshot, grant, key, session)

    def _api_key_rebind_candidate(
        self: SessionAuthorityAdmission,
        held: AccessSession,
        connection_id: UUID,
        facts: SessionAuthorityFacts,
        snapshot: AutomationCustodySnapshot,
        grant: AutomationGrant,
        key: ApiKeyRecord,
        scope: AccessScope,
    ) -> ApiKeyAdmissionCandidate | AccessDenied:
        """Rebind the connection's suspended key lease when the same key is presented again.

        The grant's validity, scope and unattended and lock policy are
        evaluated afresh; the lease keeps its identity and is not renewed.
        """
        if held.key_id != key.key_id:
            return self._absent_session(held.session_id, AccessDenialCode.AUTHENTICATION_REQUIRED)
        session = self._reissued(
            held,
            facts,
            expires_at=min(grant.expires_at, key.expires_at),
            scope=intersect_scopes((held.scope, scope, grant.scope, facts.profile.scope)),
        )
        if isinstance(session, AccessDenied):
            return session
        decision = self._evaluate(session, facts, grant, key)
        if isinstance(decision, AccessDenied):
            return decision
        return ApiKeyAdmissionCandidate(connection_id, facts, snapshot, grant, key, session, rebinding=True)

    def _publish_api_key_candidate(
        self: SessionAuthorityAdmission, candidate: ApiKeyAdmissionCandidate, credential: SecretBytes
    ) -> AccessSession | AccessDenied:
        identity = candidate.session.session_id
        retirement = ProspectiveSessionRetirement(
            self.owner, self._release_rebind(identity) if candidate.rebinding else lambda: self._retire({identity})
        )
        primary: BaseException | None = None
        try:
            with ExitStack() as preparation:
                deadline = preparation.enter_context(self.owner.prepare_api_admission(candidate.connection_id))
                refusal = self._activate_api_key_candidate(candidate, credential, deadline, preparation, retirement)
                if isinstance(refusal, AccessDenied):
                    return refusal
                if candidate.rebinding:
                    with self.owner.admission_guard():
                        refusal = self._publish_rebound(candidate.session)
                        if refusal is not None:
                            return refusal
                        retirement.committed = True
                        self._restore_suspended_descendants(candidate.session)
                        return candidate.session
                self._sessions[identity] = candidate.session
                retirement.committed = True
                return candidate.session
        except BaseException as error:
            primary = error
            raise
        finally:
            retirement.close_if_uncommitted(primary, retry_task_name="api-session-retirement")

    def _activate_api_key_candidate(
        self: SessionAuthorityAdmission,
        candidate: ApiKeyAdmissionCandidate,
        credential: SecretBytes,
        deadline: float,
        preparation: ExitStack,
        retirement: ProspectiveSessionRetirement,
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
        candidate: ApiKeyAdmissionCandidate,
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

    def admit_human(
        self: SessionAuthorityAdmission, *, connection_id: UUID, control: HumanAdmissionControl | None = None
    ) -> AccessSession | AccessDenied:
        """Bind existing password admission without consulting automation custody."""
        with self.owner.admission_guard():
            if control is not None and control.cancelled:
                return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
            facts = self._facts(connection_id)
            if isinstance(facts, AccessDenied):
                return facts
            generation = self._human_admission_generation
            held = self._held_suspended(connection_id, SessionKind.HUMAN)
            if isinstance(held, AccessDenied):
                return held
        identity = uuid4() if held is None else held.session_id
        retirement = ProspectiveSessionRetirement(
            self.owner, self._release_rebind(identity) if held is not None else lambda: self._retire({identity})
        )
        primary: BaseException | None = None
        try:
            candidate = self._authenticate_human_candidate(
                connection_id, identity, facts, retirement, generation, held, control
            )
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
        retirement: ProspectiveSessionRetirement,
        generation: int,
        held: AccessSession | None,
        control: HumanAdmissionControl | None,
    ) -> HumanAdmissionCandidate | AccessDenied:
        with self.owner.authenticate_human(connection_id) as authenticated:
            if authenticated is None:
                return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
            outcome, login_id = authenticated
            deadline = self.owner.human_admission_deadline(connection_id)
            if outcome.bucket_id != str(self.binding.profile_id):
                return AccessDenied(code=AccessDenialCode.PROFILE_MISMATCH)
            with self.owner.admission_guard():
                denial = _human_candidate_denial(control, generation, self._human_admission_generation)
                if denial is not None:
                    return denial
                current = self._facts(connection_id)
                if isinstance(current, AccessDenied):
                    return current
                refusal = self._human_admission_denial(baseline, current, deadline, outcome)
                if refusal is not None:
                    return refusal
                session = (
                    self._human_admission_session(connection_id, identity, current, outcome, login_id)
                    if held is None
                    else self._human_rebind_session(held, current, outcome, login_id)
                )
                if isinstance(session, AccessDenied):
                    return session
                decision = self._evaluate(session, current, None, None)
                if isinstance(decision, AccessDenied):
                    return decision
                retirement.binding_attempted = True
                self.owner.bind_human(session)
                return HumanAdmissionCandidate(
                    deadline, session, generation, rebinding=held is not None, control=control
                )

    def _human_rebind_session(
        self: SessionAuthorityAdmission,
        held: AccessSession,
        facts: SessionAuthorityFacts,
        outcome: ProfileLoginOutcome,
        login_id: str,
    ) -> AccessSession | AccessDenied:
        """Reissue the held person's lease under its identity, bounded by its own and the proof's deadlines."""
        if held.session_id not in self._suspended:
            return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
        if login_id != held.originating_login_id or facts.context.authenticated_client_id != held.client_id:
            return AccessDenied(code=AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
        return self._reissued(
            held, facts, expires_at=min(outcome.idle_deadline, outcome.absolute_deadline), scope=held.scope
        )

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
        candidate: HumanAdmissionCandidate,
        retirement: ProspectiveSessionRetirement,
    ) -> AccessSession | AccessDenied:
        with self.owner.admission_guard():
            denial = _human_candidate_denial(candidate.control, candidate.generation, self._human_admission_generation)
            if denial is not None:
                return denial
            current = self._facts(connection_id)
            if isinstance(current, AccessDenied):
                return current
            if _human_candidate_expired(candidate.deadline, current.context.monotonic_now):
                return AccessDenied(code=AccessDenialCode.SESSION_EXPIRED)
            decision = self._evaluate(candidate.session, current, None, None)
            if isinstance(decision, AccessDenied):
                return decision
            if candidate.rebinding:
                refusal = self._publish_rebound(candidate.session)
                if refusal is not None:
                    return refusal
            else:
                self._sessions[candidate.session.session_id] = candidate.session
            refusal = self._mint_published_human_receipt(connection_id, candidate.session)
            if refusal is not None:
                return refusal
            retirement.committed = True
            if candidate.control is not None:
                candidate.control.committed = True
            if candidate.rebinding:
                self._restore_suspended_descendants(candidate.session)
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
        # Observe first: this very observation may be the one that suspends the lease.
        facts = self._facts(connection_id)
        if isinstance(facts, AccessDenied):
            return facts
        session = self._sessions.get(session_id)
        if session is None:
            return self._absent_session(session_id, AccessDenialCode.AUTHENTICATION_REQUIRED)
        if session.kind is not SessionKind.API_KEY or session.parent_session_id is not None:
            return AccessDenied(code=AccessDenialCode.PARENT_INVALID)
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
