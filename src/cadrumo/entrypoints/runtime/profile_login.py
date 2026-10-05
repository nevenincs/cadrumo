"""Nonselecting human-proof candidates for an immutable profile worker."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import timedelta
from threading import RLock
from uuid import UUID, uuid4

from ...adapters.persistence.storage.custody.sign_in_generation import SignInGeneration
from ...adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from ...application.user_profile.access_contracts import AccessDenialCode, AccessSession, SessionKind
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.authentication import ProfileAuthenticationRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.login_session import (
    ProfileHumanLoginReceipt,
    ProfileLoginCandidate,
    ProfileLoginOutcome,
    ProfileLoginThrottledError,
    ProfileReceiptRefusedError,
    authenticate_profile_candidate,
    resume_profile_candidate,
)
from ...core.profile_session import ProfileSessionRefusalReason
from ...core.time.clock import now
from ...core.time.utc import UtcInstant
from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext


@dataclass(slots=True)
class _PendingReceipt:
    """A bound session's password proof, kept only until the runtime publishes it."""

    lease: AccessSession
    login_id: str
    candidate: ProfileLoginCandidate
    acknowledgement: ProfileHumanLoginReceipt
    deadline: UtcInstant
    monotonic_deadline: float
    lifetime: ExitStack = field(repr=False)


class ProfileWorkerHumanLogin:
    """Retain at most one short-lived candidate under the runtime's admission guard.

    A bound session whose login asked for a receipt keeps its proof as a
    pending receipt. The receipt is minted only when the runtime, having
    published that session, asks for it with the sign-in generation captured
    at publication. Retirement, expiry or worker shutdown discards it unminted.
    """

    def __init__(self, custody: ProfileWorkerCustody, *, decode: Callable[[], ProfileDecodeContext]) -> None:
        """Bind an exact worker and its pinned authority; do not open custody."""
        self.custody, self.decode = custody, decode
        self._lock = RLock()
        self._candidate: tuple[UUID, ProfileLoginCandidate, UtcInstant, float] | None = None
        self._lifetime = ExitStack()
        self._pending: dict[UUID, _PendingReceipt] = {}

    def authenticate(self, password: bytearray) -> tuple[UUID, ProfileLoginOutcome]:
        """Prove the exact password without disturbing another admitted lease."""
        with self._lock:
            self.cancel()
            try:
                candidate = self._lifetime.enter_context(
                    authenticate_profile_candidate(
                        bucket_id=self.custody.identity.binding.profile_id,
                        passphrase_callback=lambda: password.decode("utf-8"),
                        profile_decode_context=self.decode(),
                    )
                )
                identity = uuid4()
                self._candidate = identity, candidate, now() + timedelta(minutes=5), time.monotonic() + 300
                return identity, candidate.outcome
            except (UnicodeError, ProfileAuthenticationRefusedError, ProfileLoginThrottledError):
                self.cancel()
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED) from None
            except BaseException:
                self.cancel()
                raise

    def resume(self, receipt_key: bytearray) -> tuple[UUID, ProfileLoginOutcome]:
        """Verify supplied human receipt proof without looking up a secret for the caller."""
        with self._lock:
            self.cancel()
            try:
                if len(receipt_key) != 32:
                    raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
                candidate = self._lifetime.enter_context(
                    resume_profile_candidate(
                        bucket_id=self.custody.identity.binding.profile_id,
                        receipt_key=receipt_key,
                        profile_decode_context=self.decode(),
                    )
                )
                identity = uuid4()
                self._candidate = identity, candidate, now() + timedelta(minutes=5), time.monotonic() + 300
                return identity, candidate.outcome
            except ProfileReceiptRefusedError as error:
                self.cancel()
                refusal = {
                    ProfileSessionRefusalReason.EXPIRED_IDLE: AccessDenialCode.SESSION_EXPIRED,
                    ProfileSessionRefusalReason.EXPIRED_ABSOLUTE: AccessDenialCode.SESSION_EXPIRED,
                    ProfileSessionRefusalReason.CUSTODY_CHANGED: AccessDenialCode.CUSTODY_CHANGED,
                }.get(error.reason, AccessDenialCode.AUTHENTICATION_REQUIRED)
                raise ProfileAccessRefusedError(refusal) from None
            except BaseException:
                self.cancel()
                raise

    def bind(
        self, candidate_id: UUID, lease: AccessSession, *, persist_receipt: bool = False
    ) -> tuple[ProfileHumanLoginReceipt, bool]:
        """Promote only the candidate and deadlines that the authority just admitted.

        Return the acknowledgement and whether a receipt is pending. Binding
        never mints: the session is not yet published, and a refusal before
        publication must leave no receipt behind.
        """
        with self._lock:
            self.expire()
            current = self._candidate
            if current is None or current[0] != candidate_id:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            _, candidate, deadline, monotonic_deadline = current
            outcome = candidate.outcome
            login_id = lease.originating_login_id
            if (
                lease.kind is not SessionKind.HUMAN
                or login_id is None
                or lease.binding != self.custody.identity.binding
                or lease.issued_at < outcome.authenticated_at
                or lease.expires_at > min(outcome.idle_deadline, outcome.absolute_deadline)
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            material = bytearray(candidate.session.dek)
            try:
                self.custody.install(lease, material)
                acknowledgement = ProfileHumanLoginReceipt(
                    authenticated_at=outcome.authenticated_at,
                    idle_deadline=outcome.idle_deadline,
                    absolute_deadline=outcome.absolute_deadline,
                    session_persisted=outcome.session_persisted,
                    resumed=outcome.already_authenticated,
                )
                if not (persist_receipt and candidate.mints_receipt):
                    return acknowledgement, False
                self._pending[lease.session_id] = _PendingReceipt(
                    lease=lease,
                    login_id=login_id,
                    candidate=candidate,
                    acknowledgement=acknowledgement,
                    deadline=deadline,
                    monotonic_deadline=monotonic_deadline,
                    lifetime=self._lifetime.pop_all(),
                )
                self._candidate = None
                return acknowledgement, True
            except BaseException:
                self.custody.retire(lease.session_id)
                raise
            finally:
                material[:] = bytes(len(material))
                self.cancel()

    def mint_receipt(self, session_id: UUID, sign_in: SignInGeneration) -> ProfileHumanLoginReceipt:
        """Mint the pending receipt of a published session, stamped with ``sign_in``.

        ``sign_in`` is the generation the runtime captured at publication. The
        mint writes nothing when that generation has moved since, and nothing
        for a lease this worker no longer holds. Either way the proof is
        released here.
        """
        with self._lock:
            self.expire()
            pending = self._pending.pop(session_id, None)
            if pending is None:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            try:
                persisted = session_id in self.custody.live_sessions() and (
                    pending.candidate.persist_acceleration_receipt(
                        login_id=pending.login_id, binding=pending.lease.binding, sign_in=sign_in
                    )
                )
                return pending.acknowledgement.model_copy(update={"session_persisted": persisted})
            finally:
                pending.lifetime.close()

    def discard(self, session_id: UUID) -> None:
        """Release a retired session's pending receipt proof without minting."""
        with self._lock:
            pending = self._pending.pop(session_id, None)
            if pending is not None:
                pending.lifetime.close()

    def expire(self) -> None:
        """Release abandoned candidate keys even when the command stream is idle."""
        with self._lock:
            if self._candidate is not None:
                _, candidate, deadline, monotonic_deadline = self._candidate
                if _abandoned(candidate, deadline, monotonic_deadline):
                    self.cancel()
            for session_id, pending in tuple(self._pending.items()):
                if _abandoned(pending.candidate, pending.deadline, pending.monotonic_deadline):
                    self.discard(session_id)

    def cancel(self) -> None:
        """Release the unbound candidate; pending receipts of bound sessions stay."""
        with self._lock:
            self._candidate = None
            self._lifetime.close()

    def close(self) -> None:
        """Release all candidate and pending-receipt proof without closing admitted leases."""
        with self._lock:
            pending, self._pending = tuple(self._pending.values()), {}
            with ExitStack() as release:
                for item in pending:
                    release.push(item.lifetime)
                release.callback(self.cancel)


def _abandoned(candidate: ProfileLoginCandidate, deadline: UtcInstant, monotonic_deadline: float) -> bool:
    instant = now()
    return (
        instant < candidate.outcome.authenticated_at
        or instant >= min(deadline, candidate.outcome.idle_deadline, candidate.outcome.absolute_deadline)
        or time.monotonic() >= monotonic_deadline
    )
