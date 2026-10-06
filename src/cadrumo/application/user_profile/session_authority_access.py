"""Connection-bound access leases over existing custody and authorization policy.

The authority retains non-secret live leases only. Its owner supplies verified
transport/login observations, the shared lifecycle fence and profile-bound key
custody. None of these ports accepts facts deserialized from a client request.
Durable grants remain in the existing automation control store.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from uuid import UUID, uuid4

from ...core.hashing import canonical_json_bytes, sha256_hex
from ..operations.registry import OperationRegistry
from .access_administration import (
    AccessAdministrationAction,
    AccessAdministrationRequest,
    evaluate_access_administration,
)
from .access_contracts import (
    AccessAllowed,
    AccessDenialCode,
    AccessDenied,
    AccessSession,
    ApiKeyRecord,
    AutomationGrant,
    Availability,
    OperationAccessPolicy,
    OperationAccessRequest,
    OperationResponseScopeAllowed,
    ProfileAccessStatus,
    SessionKind,
)
from .access_errors import ProfileAccessRefusedError
from .access_projections import PublicAccessSession, project_access_session, project_access_status
from .automation_enrollment import AdministrationFacts
from .operation_access_policy import evaluate_operation_access, evaluate_response_scope
from .session_authority_contracts import SessionAuthorityFacts
from .session_authority_core import SessionAuthorityCore


class SessionAuthorityAccess(SessionAuthorityCore):
    """Resolve caller-bound access and publish safe authority projections."""

    def session_inventory(
        self: SessionAuthorityAccess, *, connection_id: UUID, session_id: UUID
    ) -> tuple[PublicAccessSession, ...]:
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
        self: SessionAuthorityAccess, connection_id: UUID, session_id: UUID
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
                self._retire({session_id}, reason=snapshot.code)
                raise ProfileAccessRefusedError(snapshot.code)
            grant, key = self._records(snapshot, key_id=session.key_id, grant_id=session.grant_id)
        current = self._evaluate(session, facts, grant, key)
        if isinstance(current, AccessDenied):
            raise ProfileAccessRefusedError(current.code)
        return facts, session, grant, key

    def automation_request_session(
        self: SessionAuthorityAccess, *, connection_id: UUID, session_id: UUID
    ) -> AccessSession:
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

    def human_administration_facts(
        self: SessionAuthorityAccess, *, connection_id: UUID, session_id: UUID
    ) -> AdministrationFacts:
        """Resolve fresh human facts from live leases, never from frontend identities.

        Administration owners hold this same admission guard through their
        complete read or publication. A returned snapshot alone is no permit.
        """
        with self.owner.admission_guard():
            return self._human_administration_facts_locked(connection_id, session_id)

    def _human_administration_facts_locked(
        self: SessionAuthorityAccess, connection_id: UUID, session_id: UUID
    ) -> AdministrationFacts:
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
        self: SessionAuthorityAccess,
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
        self: SessionAuthorityAccess,
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
        self: SessionAuthorityAccess, *, connection_id: UUID, session_id: UUID, target_session_id: UUID
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

    def status(
        self: SessionAuthorityAccess,
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
            context = self._status_context(facts, connection_id, session_id)
            if isinstance(context, AccessDenied):
                return context
            session, grant, key = context
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

    def _status_context(
        self: SessionAuthorityAccess, facts: SessionAuthorityFacts, connection_id: UUID, session_id: UUID
    ) -> tuple[AccessSession | None, AutomationGrant | None, ApiKeyRecord | None] | AccessDenied:
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
        return session, grant, key
