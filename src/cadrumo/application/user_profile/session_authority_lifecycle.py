"""Connection-bound access leases over existing custody and authorization policy.

The authority retains non-secret live leases only. Its owner supplies verified
transport/login observations, the shared lifecycle fence and profile-bound key
custody. None of these ports accepts facts deserialized from a client request.
Durable grants remain in the existing automation control store.
"""

from __future__ import annotations

import asyncio
from .session_authority_core import SessionAuthorityCore
from uuid import UUID

from .access_contracts import (
    AccessDenied,
    AccessSession,
    SessionKind,
)
from .automation_custody_port import AutomationCustodyError, AutomationCustodySnapshot
from .automation_lifecycle import AutomationDenial, AutomationDenialKind
from .session_authority_contracts import SessionAuthorityFacts

class SessionAuthorityLifecycle(SessionAuthorityCore):
    def disconnect(self: SessionAuthorityCore, connection_id: UUID) -> None:
        """Irreversibly retire this connection and all of its dependent leases."""
        with self.owner.admission_guard():
            retired = {item.session_id for item in self._sessions.values() if item.connection_id == connection_id}
            self._retire(retired)

    def revalidate_sessions(self: SessionAuthorityCore) -> tuple[UUID, ...]:
        """Fence expired or newly ineligible leases during host lifecycle polling.

        The host calls this even when no frontend asks for output. Loss of the
        optional automation store retires automation custody while leaving
        independently valid password sessions available.
        """
        with self.owner.admission_guard():
            return self._revalidate_sessions_locked()

    def _revalidate_sessions_locked(self: SessionAuthorityCore) -> tuple[UUID, ...]:
        """Run the one canonical lease sweep while the admission fence is held."""
        before = set(self._sessions)
        for connection_id in {session.connection_id for session in self._sessions.values()}:
            self._revalidate_connection_sessions(connection_id)
        self._retire_pending_sessions()
        return tuple(sorted(before - self._sessions.keys()))

    def _revalidate_connection_sessions(self: SessionAuthorityCore, connection_id: UUID) -> None:
        connected = {item.session_id for item in self._sessions.values() if item.connection_id == connection_id}
        try:
            facts = self._facts(connection_id)
        except AutomationCustodyError:
            self._retire(connected)
            return
        if isinstance(facts, AccessDenied):
            self._retire(connected)
            return
        current = tuple(item for item in self._sessions.values() if item.connection_id == connection_id)
        snapshot = self._automation_snapshot_for_sweep(facts, current)
        for session in current:
            self._revalidate_one_session(session, facts, snapshot)

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
            self._retire({session.session_id})
            return
        grant, key = self._records(snapshot, key_id=session.key_id, grant_id=session.grant_id)
        self._evaluate(session, facts, grant, key)

    def _retire_pending_sessions(self: SessionAuthorityCore) -> None:
        if self._pending_retirements:
            self._retire(self._pending_retirements.copy())

    def invalidate_automation(self: SessionAuthorityCore, change: AutomationDenial) -> None:
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

    async def close(self: SessionAuthorityCore) -> None:
        """Retire all live leases through the existing async cleanup protocol.

        The owner supplies bounded worker cleanup. Cancelling this wait does not
        stop the cleanup thread or restore any authority already removed.
        """
        await asyncio.to_thread(self._close)

    def _close(self: SessionAuthorityCore) -> None:
        with self.owner.admission_guard():
            self._closed = True
            self._retire(set(self._sessions) | self._pending_retirements)

    def invalidate_login(self: SessionAuthorityCore, login_id: str) -> None:
        """Fence observed human/attended logout or lock without revoking API grants."""
        with self.owner.admission_guard():
            self._retire({s.session_id for s in self._sessions.values() if s.originating_login_id == login_id})

    def _retire(self: SessionAuthorityCore, retired: set[UUID]) -> None:
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
