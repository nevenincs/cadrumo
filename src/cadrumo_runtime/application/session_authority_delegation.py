"""Delegate narrowed session authority to a verified recipient."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from cadrumo.application.user_profile.access_contracts import (
    ACCESS_LEASE_MAXIMUM,
    AccessSession,
    ApiKeyRecord,
    AutomationGrant,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.access_policy import intersect_scopes
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied
from cadrumo_client.contracts.access_vocabulary import AccessScope

from .session_authority_contracts import SessionAuthorityFacts
from .session_authority_rebind import SessionAuthorityRebind


def _recipient_has_session(sessions: dict[UUID, AccessSession], connection_id: UUID) -> bool:
    """Prevent a recipient connection from adopting another session."""
    return any(item.connection_id == connection_id for item in sessions.values())


def _valid_attendance_parent(parent: AccessSession, connection_id: UUID, delegated_parent: bool) -> bool:
    """Require the exact held human root or explicitly permitted attended parent."""
    kinds = {SessionKind.HUMAN, SessionKind.ATTENDED} if delegated_parent else {SessionKind.HUMAN}
    return parent.kind in kinds and parent.connection_id == connection_id


class SessionAuthorityDelegation(SessionAuthorityRebind):
    """Issue attended and delegated children under the existing admission fence."""

    def delegate(
        self: SessionAuthorityDelegation,
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

    def attend(
        self: SessionAuthorityDelegation,
        *,
        connection_id: UUID,
        parent_session_id: UUID,
        recipient_connection_id: UUID,
        scope: AccessScope,
        delegated_parent: bool = False,
    ) -> AccessSession | AccessDenied:
        """Issue an attended child of a person's own session to a separately verified recipient connection.

        Only the live human session held on ``connection_id`` may parent it.
        A person's session carries no grant, so the child is bounded by that
        session's scope and the recipient's profile ceiling, and it expires no
        later than the parent. Retiring the parent retires the child.
        """
        with self.owner.admission_guard():
            # Observe first: this very observation may be the one that suspends the parent.
            facts = self._facts(connection_id)
            if isinstance(facts, AccessDenied):
                return facts
            recovering = self._recovering(parent_session_id)
            if recovering is not None:
                return recovering
            parent = self._sessions.get(parent_session_id)
            if parent is None or not _valid_attendance_parent(parent, connection_id, delegated_parent):
                return AccessDenied(code=AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
            decision = self._evaluate(parent, facts, None, None)
            if isinstance(decision, AccessDenied):
                return decision
            recipient = self._facts(recipient_connection_id)
            if isinstance(recipient, AccessDenied):
                return recipient
            if _recipient_has_session(self._sessions, recipient_connection_id):
                return AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
            child = self._attended_session(parent, recipient, recipient_connection_id, scope)
            if isinstance(child, AccessDenied):
                return child
            decision = self._evaluate(child, recipient, None, None)
            if isinstance(decision, AccessDenied):
                return decision
            with self._activation(child.session_id):
                self.owner.share(child, parent)
            self._sessions[child.session_id] = child
            return child

    def _attended_session(
        self: SessionAuthorityDelegation,
        parent: AccessSession,
        recipient: SessionAuthorityFacts,
        recipient_connection_id: UUID,
        scope: AccessScope,
    ) -> AccessSession | AccessDenied:
        remaining = (parent.expires_at - parent.issued_at).total_seconds() - (
            recipient.context.monotonic_now - parent.issued_monotonic
        )
        expires = min(
            recipient.context.now + ACCESS_LEASE_MAXIMUM,
            recipient.context.now + timedelta(seconds=max(0, remaining)),
            parent.expires_at,
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
            kind=SessionKind.ATTENDED,
            originating_login_id=parent.originating_login_id,
            state=SessionState.ACTIVE,
            scope=intersect_scopes(
                (
                    scope.model_copy(
                        update={
                            "disclosures": parent.scope.disclosures,
                            "disclosure_categories": parent.scope.disclosure_categories,
                        }
                    ),
                    parent.scope,
                    recipient.profile.scope,
                )
            ),
            parent_session_id=parent.session_id,
            issued_at=recipient.context.now,
            issued_monotonic=recipient.context.monotonic_now,
            expires_at=expires,
        )

    def _delegation_authority(
        self: SessionAuthorityDelegation,
        connection_id: UUID,
        recipient_connection_id: UUID,
        parent_session_id: UUID,
        grant_id: UUID,
    ) -> tuple[AccessSession, SessionAuthorityFacts, AutomationGrant, ApiKeyRecord | None] | AccessDenied:
        facts = self._facts(connection_id)
        recipient = self._facts(recipient_connection_id)
        if isinstance(facts, AccessDenied):
            return facts
        if isinstance(recipient, AccessDenied):
            return recipient
        # Looked up after the observations: either may be the one that suspends it.
        parent = self._sessions.get(parent_session_id)
        if parent is None:
            return self._absent_session(parent_session_id, AccessDenialCode.AUTHENTICATION_REQUIRED)
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
        self: SessionAuthorityDelegation,
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
