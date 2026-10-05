"""Connection-bound access leases over existing custody and authorization policy.

The authority retains non-secret live leases only. Its owner supplies verified
transport/login observations, the shared lifecycle fence and profile-bound key
custody. None of these ports accepts facts deserialized from a client request.
Durable grants remain in the existing automation control store.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from .access_contracts import (
    SessionKind,
)
from .automation_lifecycle import AutomationDenial, AutomationDenialKind
from .session_authority_core import SessionAuthorityCore


class SessionAuthorityLifecycle(SessionAuthorityCore):
    """Own trusted lifecycle invalidation and retirement entry points."""

    def disconnect(self: SessionAuthorityLifecycle, connection_id: UUID) -> None:
        """Irreversibly retire this connection and all of its dependent leases."""
        with self.owner.admission_guard():
            retired = {item.session_id for item in self._sessions.values() if item.connection_id == connection_id}
            self._retire(retired)

    def revalidate_sessions(self: SessionAuthorityLifecycle) -> tuple[UUID, ...]:
        """Fence expired or newly ineligible leases during host lifecycle polling.

        The host calls this even when no frontend asks for output. Loss of the
        optional automation store retires automation custody while leaving
        independently valid password sessions available.
        """
        with self.owner.admission_guard():
            return self._revalidate_sessions_locked()

    def invalidate_automation(self: SessionAuthorityLifecycle, change: AutomationDenial) -> None:
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

    async def close(self: SessionAuthorityLifecycle) -> None:
        """Retire all live leases through the existing async cleanup protocol.

        The owner supplies bounded worker cleanup. Cancelling this wait does not
        stop the cleanup thread or restore any authority already removed.
        """
        await asyncio.to_thread(self._close)

    def _close(self: SessionAuthorityLifecycle) -> None:
        with self.owner.admission_guard():
            self._closed = True
            self._retire(set(self._sessions) | self._pending_retirements)
