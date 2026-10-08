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
    AccessDenialCode,
    SessionKind,
)
from .automation_lifecycle import AutomationDenial, AutomationDenialKind
from .session_authority_core import SessionAuthorityCore
from .session_retirement import SessionRetirementKind


class SessionAuthorityLifecycle(SessionAuthorityCore):
    """Own trusted lifecycle invalidation and retirement entry points."""

    def human_login_ids(self) -> frozenset[str]:
        """Identify login observations relevant to this profile's live human leases."""
        with self.owner.admission_guard():
            return frozenset(
                session.originating_login_id
                for session in self._sessions.values()
                if session.kind is not SessionKind.API_KEY and session.originating_login_id is not None
            )

    def retire_human_sessions(
        self,
        *,
        reason: AccessDenialCode = AccessDenialCode.AUTHENTICATION_REQUIRED,
        kind: SessionRetirementKind = SessionRetirementKind.SIGNED_OUT,
    ) -> tuple[UUID, ...]:
        """Fence pending human admissions and retire human/attended access only.

        The runtime lifecycle owner first commits its durable sign-in fence,
        under this same guard. API-key grants and sessions retain their policy.
        """
        with self.owner.admission_guard():
            self._human_admission_generation += 1
            retired = {
                session.session_id for session in self._sessions.values() if session.kind is not SessionKind.API_KEY
            }
            self._retire(retired, reason=reason, kind=kind)
            return tuple(sorted(retired))

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
            self._retire(
                retired,
                reason=(
                    AccessDenialCode.PROFILE_LOCKED
                    if change.kind is AutomationDenialKind.PROFILE_LOCK
                    else AccessDenialCode.GRANT_INACTIVE
                ),
            )

    async def close(
        self: SessionAuthorityLifecycle, *, reason: AccessDenialCode = AccessDenialCode.RUNTIME_CHANGED
    ) -> None:
        """Retire all live leases through the existing async cleanup protocol.

        The owner supplies bounded worker cleanup. Cancelling this wait does not
        stop the cleanup thread or restore any authority already removed.
        """
        await asyncio.to_thread(self._close, reason=reason)

    def _close(self: SessionAuthorityLifecycle, *, reason: AccessDenialCode = AccessDenialCode.RUNTIME_CHANGED) -> None:
        with self.owner.admission_guard():
            self._closed = True
            self._retire(set(self._sessions) | self._pending_retirements, reason=reason)
