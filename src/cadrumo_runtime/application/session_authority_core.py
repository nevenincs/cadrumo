"""Connection-bound access leases over existing custody and authorization policy.

The authority retains non-secret live leases only. Its owner supplies verified
transport/login observations, the shared lifecycle fence and profile-bound key
custody. None of these ports accepts facts deserialized from a client request.
Durable grants remain in the existing automation control store.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from cadrumo.application.user_profile.access_contracts import (
    AccessSession,
    ApiKeyRecord,
    AutomationGrant,
    LoginEligibility,
    OsLockState,
    ProfileAccessBinding,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyPort, AutomationCustodySnapshot
from cadrumo.application.user_profile.automation_enrollment import AutomationKeyIssuer
from cadrumo.application.user_profile.session_retirement import SessionRetirement, SessionRetirementKind
from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.logging import get_logger
from cadrumo.core.time.utc import UtcInstant
from cadrumo_client.contracts.access_refusals import AccessDecision, AccessDenialCode, AccessDenied
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.session_policy import (
    evaluate_session_authority,
    session_refusal,
    session_requires_grant,
)

from .session_authority_contracts import SessionAuthorityFacts, SessionAuthorityOwner

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CustodyRecoveryPolicy:
    """How long a profile's leases wait for a fresh proof after its worker is lost, and when none wait.

    ``monotonic`` measures only these two intervals; every lease keeps its own
    deadlines on the clocks its facts report.
    """

    window_seconds: float = 120.0
    """A positive worker loss suspends every lease this long from the moment the loss is established."""
    repeat_loss_seconds: float = 600.0
    """A loss this soon after the previous one retires every lease at once and opens no window."""
    monotonic: Callable[[], float] = time.monotonic


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
        replace_lost_owner: Callable[[], SessionAuthorityOwner] | None = None,
        suspended: Callable[[tuple[AccessSession, ...]], None] | None = None,
        rebound: Callable[[tuple[AccessSession, ...]], None] | None = None,
        recovery: CustodyRecoveryPolicy | None = None,
    ) -> None:
        """Bind trusted collaborators; construction grants no session authority.

        Without ``replace_lost_owner`` a positive worker loss retires every
        lease at once. With it the loss suspends them for the recovery window
        under a fresh owner; ``suspended`` hears which leases wait and
        ``rebound`` which returned to custody after a fresh proof.
        """
        self.binding = binding
        self.runtime_boot_id = runtime_boot_id
        self.owner = owner
        self.custody = custody
        self.issuer = issuer
        self._sessions: dict[UUID, AccessSession] = {}
        # Leases of a lost worker: they grant nothing until a fresh proof rebinds them.
        self._suspended: dict[UUID, AccessSession] = {}
        self._recovery_deadline: float | None = None
        self._last_worker_loss: float | None = None
        self._pending_retirements: set[UUID] = set()
        self._last_observation: tuple[UtcInstant, float] | None = None
        self._closed = False
        self._human_admission_generation = 0
        self._retired = retired
        self._replace_lost_owner = replace_lost_owner
        self._suspended_notice = suspended
        self._rebound_notice = rebound
        self._recovery = CustodyRecoveryPolicy() if recovery is None else recovery

    def _facts(self, connection_id: UUID) -> SessionAuthorityFacts | AccessDenied:
        if self._closed:
            return AccessDenied(code=AccessDenialCode.RUNTIME_CHANGED)
        self._observe_worker_loss()
        try:
            facts = self.owner.facts(connection_id)
        except AutomationCustodyError:
            # This very observation may be the one that found the worker gone.
            if not self._observe_worker_loss():
                raise
            facts = self.owner.facts(connection_id)
        mismatch = self._facts_binding_denial(facts, connection_id)
        if mismatch is not None:
            return mismatch
        if self._clock_rollback_detected(facts):
            self._retire(set(self._sessions) | set(self._suspended), reason=AccessDenialCode.CLOCK_INVALID)
            return AccessDenied(code=AccessDenialCode.CLOCK_INVALID)
        self._retire_sessions_without_live_login(facts)
        return facts

    def _leases(self) -> tuple[AccessSession, ...]:
        """Every lease this authority still answers for, live or suspended."""
        return (*self._sessions.values(), *self._suspended.values())

    def _observe_worker_loss(self) -> bool:
        """Turn a positive worker loss into suspension, or retirement, of every lease; say whether one was found.

        The caller holds the admission guard. The lost owner is replaced at
        once, so later observations read the fresh owner. A second loss within
        the repeat interval of the previous one opens no window.
        """
        if self._replace_lost_owner is None or self._closed or not self.owner.worker_lost:
            return False
        instant = self._recovery.monotonic()
        previous, self._last_worker_loss = self._last_worker_loss, instant
        self.owner = self._replace_lost_owner()
        if previous is not None and instant - previous < self._recovery.repeat_loss_seconds:
            self._retire(set(self._sessions) | set(self._suspended), reason=AccessDenialCode.CUSTODY_UNAVAILABLE)
            return True
        suspended = tuple(self._sessions.values())
        self._sessions.clear()
        if not suspended:
            return True
        self._suspended.update((lease.session_id, lease) for lease in suspended)
        self._recovery_deadline = instant + self._recovery.window_seconds
        diagnostic_event(
            _log,
            "runtime_sessions_suspended",
            fields={
                "session_kinds": ",".join(sorted(lease.kind.value for lease in suspended)),
                "window_seconds": self._recovery.window_seconds,
            },
            level=logging.INFO,
        )
        if self._suspended_notice is not None:
            self._suspended_notice(suspended)
        return True

    def _recovery_remaining_seconds(self) -> int:
        """Whole seconds, rounded up, until unrebound suspended leases retire."""
        if self._recovery_deadline is None:
            return 0
        return max(0, math.ceil(self._recovery_deadline - self._recovery.monotonic()))

    def _recovering(self, session_id: UUID) -> AccessDenied | None:
        """Refuse a suspended lease with the time left to rebind it; ``None`` for any other identity."""
        if session_id not in self._suspended:
            return None
        return AccessDenied(
            code=AccessDenialCode.CUSTODY_RECOVERING,
            recovery_remaining_seconds=self._recovery_remaining_seconds(),
        )

    def _absent_session(self, session_id: UUID, code: AccessDenialCode) -> AccessDenied:
        """Refuse an identity no live lease holds: recovering while it is suspended, else ``code``."""
        return self._recovering(session_id) or AccessDenied(code=code)

    def _expire_suspended_locked(self) -> None:
        """Retire suspended leases whose window, own time or profile custody has ended, or whose connection is gone."""
        if not self._suspended:
            return
        if self._recovery_deadline is None or self._recovery.monotonic() >= self._recovery_deadline:
            self._retire(set(self._suspended), reason=AccessDenialCode.CUSTODY_UNAVAILABLE)
            return
        for connection_id in {lease.connection_id for lease in self._suspended.values()}:
            waiting = {lease.session_id for lease in self._suspended.values() if lease.connection_id == connection_id}
            try:
                facts = self._facts(connection_id)
            except AutomationCustodyError as error:
                if error.reason is AutomationCustodyCode.UNAVAILABLE and not self.owner.lost:
                    continue
                self._retire(waiting & self._suspended.keys(), reason=AccessDenialCode.CUSTODY_UNAVAILABLE)
                continue
            if isinstance(facts, AccessDenied):
                self._retire(waiting & self._suspended.keys(), reason=facts.code)
                continue
            for session_id in waiting & self._suspended.keys():
                lapsed = session_refusal(self._suspended[session_id], facts.profile, facts.context)
                if lapsed is not None:
                    self._retire({session_id}, reason=lapsed)

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
        uncertain_logins = {
            login.login_id
            for login in facts.context.login_contexts
            if login.os_owner_id == self.binding.os_owner_id
            and login.lock_state is OsLockState.UNKNOWN
            and login.unattended is LoginEligibility.UNKNOWN
        }
        self._retire(
            {
                session.session_id
                for session in self._leases()
                if session.originating_login_id is not None
                and session.originating_login_id not in live_logins | uncertain_logins
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
            and not self._uncertain_login_denial(session, facts, decision)
        ):
            self._retire({session.session_id}, reason=decision.code)
        return decision

    @staticmethod
    def _uncertain_login_denial(session: AccessSession, facts: SessionAuthorityFacts, decision: AccessDenied) -> bool:
        """Observation failure denies work without turning uncertainty into logout."""
        return decision.code is AccessDenialCode.OS_SESSION_UNAVAILABLE and any(
            login.login_id == session.originating_login_id
            and login.os_owner_id == session.binding.os_owner_id
            and login.lock_state is OsLockState.UNKNOWN
            and login.unattended is LoginEligibility.UNKNOWN
            for login in facts.context.login_contexts
        )

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
        if not any(session_requires_grant(item) for item in sessions):
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
            dependents = {s.session_id for s in self._leases() if s.parent_session_id in retired}
            if dependents <= retired:
                break
            retired |= dependents
        # Remove authority for the entire cascade before fallible physical cleanup.
        # A suspended lease was published to its frontend, so its end is announced too.
        published = tuple(
            lease
            for identity in retired
            if (lease := self._sessions.pop(identity, None) or self._suspended.pop(identity, None)) is not None
        )
        if not self._suspended:
            self._recovery_deadline = None
        self._pending_retirements.update(retired)
        failures: list[Exception] = []
        if kind is SessionRetirementKind.REVOKED:
            if reason is AccessDenialCode.PROFILE_LOCKED:
                kind = SessionRetirementKind.PROFILE_LOCKED
            elif reason is AccessDenialCode.CUSTODY_CHANGED:
                kind = SessionRetirementKind.CUSTODY_CHANGED
        if published:
            # A frontend hears only that its session ended; the runtime log keeps why.
            # A connection's own end is routine, every other retirement ends a person's access.
            diagnostic_event(
                _log,
                "runtime_sessions_retired",
                fields={
                    "reason": reason.value,
                    "retirement_kind": kind.value,
                    "session_kinds": ",".join(sorted(session.kind.value for session in published)),
                },
                level=logging.DEBUG if reason is AccessDenialCode.SESSION_INACTIVE else logging.INFO,
            )
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
        except AutomationCustodyError as error:
            if error.reason is AutomationCustodyCode.UNAVAILABLE and not self.owner.lost:
                # A worker that could not be observed in time is busy, not lost. Every use
                # still refuses until it answers; the next sweep revalidates these leases.
                return
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
        if not session_requires_grant(session):
            # A person's session, and an attended child of one, answer to their lineage, not to automation custody.
            self._evaluate(session, facts, None, None)
            return
        if snapshot is None:
            self._retire({session.session_id}, reason=AccessDenialCode.CUSTODY_UNAVAILABLE)
            return
        grant, key = self._records(snapshot, key_id=session.key_id, grant_id=session.grant_id)
        self._evaluate(session, facts, grant, key)

    def _revalidate_sessions_locked(self: SessionAuthorityCore) -> tuple[UUID, ...]:
        """Run the one canonical lease sweep while the admission fence is held."""
        before = set(self._sessions) | set(self._suspended)
        self._observe_worker_loss()
        for connection_id in {session.connection_id for session in self._sessions.values()}:
            self._revalidate_connection_sessions(connection_id)
        self._expire_suspended_locked()
        self._retire_pending_sessions()
        return tuple(sorted(before - self._sessions.keys() - self._suspended.keys()))
