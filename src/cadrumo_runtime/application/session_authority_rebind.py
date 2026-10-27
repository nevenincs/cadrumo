"""Return a suspended lease to custody under its own identity after a fresh proof on its own connection.

A positive worker loss suspends every lease of the profile. Only the exact
native connection that held a root lease may rebind it, by presenting the proof
that lease was admitted with again. The lease keeps its identity and is never
renewed: its expiry is at most the original, and at most what the new proof
supports. Its attended descendants follow without proof while their own
connections remain.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from cadrumo.application.user_profile.access_contracts import AccessSession, SessionKind
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.access_policy import intersect_scopes
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied
from cadrumo_client.contracts.access_vocabulary import AccessScope
from cadrumo_client.contracts.automation_codes import AutomationCustodyError
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.session_policy import session_requires_grant

from .session_authority_contracts import SessionAuthorityFacts
from .session_authority_core import SessionAuthorityCore


class SessionAuthorityRebind(SessionAuthorityCore):
    """Rebind suspended leases; every other identity is admitted as before."""

    def _held_suspended(self, connection_id: UUID, kind: SessionKind) -> AccessSession | AccessDenied | None:
        """Return the suspended root lease of ``kind`` this connection holds, refuse while it holds another one.

        ``None`` means the connection holds no suspended lease, so the proof is
        an ordinary admission. A suspended child, or a lease of another kind,
        waits for its own proof or its parent: this proof cannot rebind it.
        """
        held = tuple(lease for lease in self._suspended.values() if lease.connection_id == connection_id)
        if not held:
            return None
        match = next((lease for lease in held if lease.kind is kind and lease.parent_session_id is None), None)
        return match or self._absent_session(held[0].session_id, AccessDenialCode.AUTHENTICATION_REQUIRED)

    def _release_rebind(self, session_id: UUID) -> Callable[[], None]:
        """Release a rebind that did not commit: its new custody, and the lease only if it was published."""

        def release() -> None:
            if session_id in self._sessions:
                self._retire({session_id})
            else:
                self.owner.retire(session_id)

        return release

    @staticmethod
    def _reissued(
        lease: AccessSession, facts: SessionAuthorityFacts, *, expires_at: datetime, scope: AccessScope
    ) -> AccessSession | AccessDenied:
        """Return ``lease`` issued again now under its own identity, never expiring later than before."""
        bounded = min(lease.expires_at, expires_at)
        if bounded <= facts.context.now:
            return AccessDenied(code=AccessDenialCode.SESSION_EXPIRED)
        return AccessSession.model_validate(
            {
                **{name: getattr(lease, name) for name in AccessSession.model_fields},
                "scope": scope,
                "issued_at": facts.context.now,
                "issued_monotonic": facts.context.monotonic_now,
                "expires_at": bounded,
            }
        )

    def _publish_rebound(self, session: AccessSession) -> AccessDenied | None:
        """Publish a rebound lease that is still suspended; the caller holds the admission guard."""
        if session.session_id not in self._suspended:
            # Sign-out, lock, revocation or the window's end retired it meanwhile; nothing rebinds that.
            return AccessDenied(code=AccessDenialCode.AUTHENTICATION_REQUIRED)
        del self._suspended[session.session_id]
        self._sessions[session.session_id] = session
        return None

    def _restore_suspended_descendants(self, root: AccessSession) -> None:
        """Re-admit each attended descendant of a rebound lease under its own id while its connection is open.

        Each is bounded by its rebound parent's scope and remaining expiry.
        Any other descendant presents no proof of its own and retires.
        """
        restored: list[AccessSession] = [root]
        parents = [root]
        while parents:
            parent = parents.pop()
            for child in tuple(
                lease for lease in self._suspended.values() if lease.parent_session_id == parent.session_id
            ):
                admitted = self._restore_child(child, parent)
                if admitted is not None:
                    restored.append(admitted)
                    parents.append(admitted)
        if not self._suspended:
            self._recovery_deadline = None
        if self._rebound_notice is not None:
            self._rebound_notice(tuple(restored))

    def _restore_child(self, child: AccessSession, parent: AccessSession) -> AccessSession | None:
        if child.kind is not SessionKind.ATTENDED:
            self._retire({child.session_id}, reason=AccessDenialCode.CUSTODY_UNAVAILABLE)
            return None
        try:
            facts = self._facts(child.connection_id)
        except AutomationCustodyError:
            self._retire({child.session_id}, reason=AccessDenialCode.CUSTODY_UNAVAILABLE)
            return None
        if child.session_id not in self._suspended or parent.session_id not in self._sessions:
            # The observation found a further loss, or the parent ended; nothing is restored.
            return None
        if isinstance(facts, AccessDenied):
            self._retire({child.session_id}, reason=facts.code)
            return None
        restored = self._reissued(
            child, facts, expires_at=parent.expires_at, scope=intersect_scopes((child.scope, parent.scope))
        )
        if isinstance(restored, AccessDenied):
            self._retire({child.session_id}, reason=restored.code)
            return None
        grant, key = None, None
        if session_requires_grant(restored):
            snapshot = self._snapshot(facts)
            if isinstance(snapshot, AccessDenied):
                self._retire({child.session_id}, reason=snapshot.code)
                return None
            grant, key = self._records(snapshot, key_id=restored.key_id, grant_id=restored.grant_id)
        # Evaluated against its rebound parent: the parent is published, the child not yet.
        decision = self._evaluate(restored, facts, grant, key)
        if isinstance(decision, AccessDenied):
            self._retire({child.session_id}, reason=decision.code)
            return None
        try:
            with self._activation(child.session_id):
                self.owner.share(restored, parent)
        except (AutomationCustodyError, RefusalError, ProfileAccessRefusedError):
            # Activation has already retired the child; its parent keeps its own custody.
            return None
        if self._suspended.pop(child.session_id, None) is None:
            self.owner.retire(child.session_id)
            return None
        self._sessions[child.session_id] = restored
        return restored
