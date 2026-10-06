"""Connection-bound access leases over existing custody and authorization policy.

The authority retains non-secret live leases only. Its owner supplies verified
transport/login observations, the shared lifecycle fence and profile-bound key
custody. None of these ports accepts facts deserialized from a client request.
Durable grants remain in the existing automation control store.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from uuid import UUID

from ...core.time.utc import UtcInstant
from .access_contracts import (
    AccessDecision,
    AccessDenialCode,
    AccessDenied,
    AccessSession,
    ApiKeyRecord,
    AutomationGrant,
    ProfileAccessBinding,
    SessionKind,
)
from .automation_custody_port import AutomationCustodyError, AutomationCustodyPort, AutomationCustodySnapshot
from .automation_enrollment import AutomationKeyIssuer
from .session_authority_contracts import SessionAuthorityFacts, SessionAuthorityOwner
from .session_authority_policy import evaluate_session_authority
from .session_retirement import SessionRetirement, SessionRetirementKind


class SessionAuthorityCore:
    """One profile's ephemeral leases for one runtime boot, serialized by its owner."""

    def __init__(
        self,
        *,
        binding: ProfileAccessBinding,
        runtime_boot_id: UUID,
        owner: SessionAuthorityOwner,
        custody: AutomationCustodyPort,
        issuer: AutomationKeyIssuer,
        retired: Callable[[SessionRetirement], None] | None = None,
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
        self._human_admission_generation = 0
        self._retired = retired

    def _facts(self, connection_id: UUID) -> SessionAuthorityFacts | AccessDenied:
        if self._closed:
            return AccessDenied(code=AccessDenialCode.RUNTIME_CHANGED)
        facts = self.owner.facts(connection_id)
        mismatch = self._facts_binding_denial(facts, connection_id)
        if mismatch is not None:
            return mismatch
        if self._clock_rollback_detected(facts):
            self._retire(set(self._sessions), reason=AccessDenialCode.CLOCK_INVALID)
            return AccessDenied(code=AccessDenialCode.CLOCK_INVALID)
        self._retire_sessions_without_live_login(facts)
        return facts

    def _facts_binding_denial(self, facts: SessionAuthorityFacts, connection_id: UUID) -> AccessDenied | None:
        if facts.context.connection_id != connection_id:
            return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
        if facts.context.runtime_boot_id != self.runtime_boot_id:
            return AccessDenied(code=AccessDenialCode.RUNTIME_CHANGED)
        if facts.profile.binding != self.binding:
            return AccessDenied(code=AccessDenialCode.CUSTODY_CHANGED)
        return None

    def _clock_rollback_detected(self, facts: SessionAuthorityFacts) -> bool:
        observed = (facts.context.now, facts.context.monotonic_now)
        previous = self._last_observation
        self._last_observation = observed
        return facts.context.clock_rollback_detected or (
            previous is not None and (observed[0] < previous[0] or observed[1] < previous[1])
        )

    def _retire_sessions_without_live_login(self, facts: SessionAuthorityFacts) -> None:
        live_logins = {
            login.login_id
            for login in facts.context.login_contexts
            if login.active and login.unlocked and login.os_owner_id == self.binding.os_owner_id
        }
        self._retire(
            {
                session.session_id
                for session in self._sessions.values()
                if session.originating_login_id is not None and session.originating_login_id not in live_logins
            },
            reason=AccessDenialCode.OS_SESSION_UNAVAILABLE,
        )

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
            self._retire({session.session_id}, reason=decision.code)
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

    def _automation_snapshot_for_sweep(
        self: SessionAuthorityCore,
        facts: SessionAuthorityFacts,
        sessions: tuple[AccessSession, ...],
    ) -> AutomationCustodySnapshot | None:
        if not any(item.kind is not SessionKind.HUMAN for item in sessions):
            return None
        try:
            snapshot = self._snapshot(facts)
        except AutomationCustodyError:
            return None
        return None if isinstance(snapshot, AccessDenied) else snapshot

    def _retire(
        self: SessionAuthorityCore,
        retired: set[UUID],
        *,
        reason: AccessDenialCode = AccessDenialCode.SESSION_INACTIVE,
        kind: SessionRetirementKind = SessionRetirementKind.REVOKED,
    ) -> None:
        while True:
            dependents = {s.session_id for s in self._sessions.values() if s.parent_session_id in retired}
            if dependents <= retired:
                break
            retired |= dependents
        # Remove authority for the entire cascade before fallible physical cleanup.
        published = tuple(self._sessions.pop(identity) for identity in retired if identity in self._sessions)
        self._pending_retirements.update(retired)
        failures: list[Exception] = []
        if kind is SessionRetirementKind.REVOKED:
            if reason is AccessDenialCode.PROFILE_LOCKED:
                kind = SessionRetirementKind.PROFILE_LOCKED
            elif reason is AccessDenialCode.CUSTODY_CHANGED:
                kind = SessionRetirementKind.CUSTODY_CHANGED
        # Delivery is a nonblocking owner queue. Only actually published leases
        # emit; retries of failed physical cleanup never emit a second event.
        if self._retired is not None:
            for session in published:
                try:
                    self._retired(
                        SessionRetirement(
                            profile_id=self.binding.profile_id,
                            connection_id=session.connection_id,
                            session_id=session.session_id,
                            reason=reason,
                            kind=kind,
                        )
                    )
                except Exception as error:
                    failures.append(error)
        for session_id in retired:
            try:
                self.owner.retire(session_id)
            except Exception as error:
                failures.append(error)
            else:
                self._pending_retirements.discard(session_id)
        if failures:
            raise ExceptionGroup("session custody retirement failed", failures)

    def _retire_pending_sessions(self: SessionAuthorityCore) -> None:
        if self._pending_retirements:
            self._retire(self._pending_retirements.copy())

    def _revalidate_connection_sessions(self: SessionAuthorityCore, connection_id: UUID) -> None:
        connected = {item.session_id for item in self._sessions.values() if item.connection_id == connection_id}
        try:
            facts = self._facts(connection_id)
        except AutomationCustodyError:
            self._retire(connected, reason=AccessDenialCode.CUSTODY_UNAVAILABLE)
            return
        if isinstance(facts, AccessDenied):
            self._retire(connected, reason=facts.code)
            return
        current = tuple(item for item in self._sessions.values() if item.connection_id == connection_id)
        snapshot = self._automation_snapshot_for_sweep(facts, current)
        for session in current:
            self._revalidate_one_session(session, facts, snapshot)

    def _revalidate_one_session(
        self: SessionAuthorityCore,
        session: AccessSession,
        facts: SessionAuthorityFacts,
        snapshot: AutomationCustodySnapshot | None,
    ) -> None:
        if session.session_id not in self._sessions:
            return
        if session.kind is SessionKind.HUMAN:
            self._evaluate(session, facts, None, None)
            return
        if snapshot is None:
            self._retire({session.session_id}, reason=AccessDenialCode.CUSTODY_UNAVAILABLE)
            return
        grant, key = self._records(snapshot, key_id=session.key_id, grant_id=session.grant_id)
        self._evaluate(session, facts, grant, key)

    def _revalidate_sessions_locked(self: SessionAuthorityCore) -> tuple[UUID, ...]:
        """Run the one canonical lease sweep while the admission fence is held."""
        before = set(self._sessions)
        for connection_id in {session.connection_id for session in self._sessions.values()}:
            self._revalidate_connection_sessions(connection_id)
        self._retire_pending_sessions()
        return tuple(sorted(before - self._sessions.keys()))
