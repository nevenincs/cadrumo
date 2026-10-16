"""Renew live human authority only after the host admits a person's input."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from cadrumo.application.user_profile.access_contracts import AccessDenialCode, AccessDenied, AccessSession, SessionKind

from .session_authority_core import SessionAuthorityCore


class SessionAuthorityActivity(SessionAuthorityCore):
    """Keep one login's existing human leases alive without reviving expired ones."""

    def note_human_activity(
        self, *, connection_id: UUID, session_id: UUID, idle_window: timedelta
    ) -> AccessSession | AccessDenied:
        """Reauthorize input and advance only expiry, preserving lineage issuance."""
        if idle_window <= timedelta(0):
            raise ValueError("human activity requires a positive idle window")
        with self.owner.admission_guard():
            session = self._sessions.get(session_id)
            if session is None:
                return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
            if session.kind is not SessionKind.HUMAN or session.parent_session_id is not None:
                return AccessDenied(code=AccessDenialCode.PERSON_ACT_REQUIRED)
            facts = self._facts(connection_id)
            if isinstance(facts, AccessDenied):
                return facts
            decision = self._evaluate(session, facts, None, None)
            if isinstance(decision, AccessDenied):
                return decision
            deadline = facts.context.now + idle_window
            # Bound writes even if an admitted frontend sends every keystroke.
            if deadline - session.expires_at < min(timedelta(seconds=15), idle_window / 2):
                return session
            for current in tuple(self._sessions.values()):
                if (
                    current.kind is not SessionKind.HUMAN
                    or current.originating_login_id != session.originating_login_id
                ):
                    continue
                observed = self._facts(current.connection_id)
                if isinstance(observed, AccessDenied) or isinstance(
                    self._evaluate(current, observed, None, None), AccessDenied
                ):
                    continue
                if current.expires_at >= deadline:
                    continue
                renewed = AccessSession.model_validate(
                    {
                        **{name: getattr(current, name) for name in AccessSession.model_fields},
                        "expires_at": deadline,
                    }
                )
                with self._activation(current.session_id):
                    self.owner.refresh(renewed)
                self._sessions[current.session_id] = renewed
            return self._sessions.get(session_id) or AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
