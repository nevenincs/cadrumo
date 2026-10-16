"""Nonselecting human-proof candidates for an immutable profile worker."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import timedelta
from threading import RLock
from typing import Final
from uuid import UUID, uuid4

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import refresh_profile_session_with_key
from cadrumo.adapters.persistence.storage.custody.errors import ProfileCustodyRefusal, ProfileCustodyRefusedError
from cadrumo.adapters.persistence.storage.custody.kdf_supervision import ProfileKdfPrewarm
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGeneration, SignInGenerationCustody
from cadrumo.adapters.persistence.storage.errors import PersistenceError
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, AccessSession, SessionKind
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.authentication import ProfileAuthenticationRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.login_session import (
    ProfileLoginCandidate,
    ProfileLoginOutcome,
    ProfileLoginThrottledError,
    ProfileReceiptRefusedError,
    authenticate_profile_candidate,
)
from cadrumo.application.user_profile.sign_in_refusals import SignInRefusal
from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.logging import get_logger
from cadrumo.core.profile_session import ProfileHumanLoginReceipt, ProfileSessionRefusalReason
from cadrumo.core.time.clock import now
from cadrumo.core.time.utc import UtcInstant
from cadrumo.domain.calculations.registry.authority_artifact import ProfileDecodeContext

from .profile_receipt import resume_profile_candidate

_log = get_logger(__name__)

_RECEIPT_DENIAL: Final = AccessDenialCode.AUTHENTICATION_REQUIRED
"""A refused receipt no longer signs this login in; a fresh proof is required."""

_RECEIPT_DENIALS: Final[dict[ProfileSessionRefusalReason, AccessDenialCode]] = {
    ProfileSessionRefusalReason.EXPIRED_IDLE: AccessDenialCode.SESSION_EXPIRED,
    ProfileSessionRefusalReason.EXPIRED_ABSOLUTE: AccessDenialCode.SESSION_EXPIRED,
    ProfileSessionRefusalReason.CUSTODY_CHANGED: AccessDenialCode.CUSTODY_CHANGED,
}


_KDF_UNAVAILABLE: Final = frozenset(
    {ProfileCustodyRefusal.KDF_RESOURCE_LIMIT, ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE}
)
"""Derivation refusals that say nothing about the password: the permit or the child was not available in time."""


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
        self._resumed_login: str | None = None
        self._candidate_sealing_key: bytearray | None = None
        self._sealing_keys: dict[UUID, bytearray] = {}
        self._lifetime = ExitStack()
        self._pending: dict[UUID, _PendingReceipt] = {}
        # A password proof's key derivation runs in a fresh contained child;
        # launching the next one now keeps its interpreter start-up off the
        # person's sign-in.
        self._kdf_prewarm = ProfileKdfPrewarm()
        self._kdf_prewarm.refill()

    def authenticate(self, password: bytearray) -> tuple[UUID, ProfileLoginOutcome]:
        """Prove the exact password without disturbing another admitted lease."""
        with self._lock:
            self.cancel()
            try:
                with self._kdf_prewarm.bound():
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
            except ProfileLoginThrottledError as error:
                self.cancel()
                raise ProfileAccessRefusedError(
                    AccessDenialCode.AUTHENTICATION_REQUIRED,
                    sign_in=SignInRefusal(reason="throttled", remaining_seconds=error.remaining_seconds),
                ) from None
            except (UnicodeError, ProfileAuthenticationRefusedError):
                self.cancel()
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED) from None
            except ProfileCustodyRefusedError as error:
                self.cancel()
                if error.refusal not in _KDF_UNAVAILABLE:
                    raise
                # The installation's one KDF permit stayed taken, or no derivation child attested: this
                # sign-in is refused as unavailable for now, and the worker keeps serving its other sessions.
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
            except BaseException:
                self.cancel()
                raise

    def resume(self, receipt_key: bytearray, *, login_id: str | None) -> tuple[UUID, ProfileLoginOutcome]:
        """Verify supplied human receipt proof without looking up a secret for the caller.

        ``login_id`` is the originating OS login the runtime captured for the
        presenting connection. The receipt must name it and the current
        sign-in generation; a receipt refused for its generation or its own
        metadata is deleted by this worker before the refusal returns. A
        receipt refused only for the login is deleted likewise, but only when
        the supplied proof unwraps it; a wrong proof deletes nothing.
        """
        with self._lock:
            self.cancel()
            try:
                if len(receipt_key) != 32 or not (login_id is not None and login_id):
                    raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
                candidate = self._lifetime.enter_context(
                    resume_profile_candidate(
                        bucket_id=self.custody.identity.binding.profile_id,
                        receipt_key=receipt_key,
                        profile_decode_context=self.decode(),
                        login_id=login_id,
                        sign_in_binding=self.custody.identity.binding,
                    )
                )
                identity = uuid4()
                self._candidate = identity, candidate, now() + timedelta(minutes=5), time.monotonic() + 300
                self._resumed_login = login_id
                self._candidate_sealing_key = bytearray(receipt_key)
                return identity, candidate.outcome
            except ProfileReceiptRefusedError as error:
                self.cancel()
                raise ProfileAccessRefusedError(
                    _RECEIPT_DENIALS.get(error.reason, _RECEIPT_DENIAL),
                    sign_in=SignInRefusal(reason=error.reason, binding=error.binding),
                ) from None
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
                or (self._resumed_login is not None and login_id != self._resumed_login)
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
                if self._candidate_sealing_key is not None:
                    self._sealing_keys[lease.session_id] = self._candidate_sealing_key
                    self._candidate_sealing_key = None
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
                self.discard(lease.session_id)
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
                        login_id=pending.login_id,
                        binding=pending.lease.binding,
                        sign_in=sign_in,
                        retain_sealing_key=lambda key: self._retain_sealing_key(session_id, key),
                    )
                )
                return pending.acknowledgement.model_copy(update={"session_persisted": persisted})
            finally:
                pending.lifetime.close()

    def _retain_sealing_key(self, session_id: UUID, key: bytearray) -> None:
        previous = self._sealing_keys.pop(session_id, None)
        if previous is not None:
            previous[:] = bytes(len(previous))
        self._sealing_keys[session_id] = bytearray(key)

    def refresh(self, lease: AccessSession) -> None:
        """Renew live custody and reseal its existing receipt using worker-held proof."""
        with self._lock:
            self.expire()
            self.custody.refresh(lease)
            key = self._sealing_keys.get(lease.session_id)
            if key is not None and lease.originating_login_id is not None:
                try:
                    refresh_profile_session_with_key(
                        sign_in=SignInGenerationCustody(root=self.custody.root, binding=lease.binding),
                        receipt_key=key,
                        login_id=lease.originating_login_id,
                        now=lease.issued_at,
                        deadline=lease.expires_at,
                    )
                except (PersistenceError, OSError) as error:
                    # Durable acceleration is optional; its I/O cannot retire already
                    # admitted live human custody or undo the activity deadline.
                    diagnostic_event(
                        _log,
                        "profile_receipt_refresh_failed",
                        fields={"error_type": type(error).__name__},
                        level=30,
                    )

    def discard(self, session_id: UUID) -> None:
        """Release a retired session's pending receipt proof without minting."""
        with self._lock:
            key = self._sealing_keys.pop(session_id, None)
            if key is not None:
                key[:] = bytes(len(key))
            pending = self._pending.pop(session_id, None)
            if pending is not None:
                pending.lifetime.close()

    def expire(self) -> None:
        """Release abandoned candidate keys even when the command stream is idle."""
        with self._lock:
            live = self.custody.live_sessions()
            for session_id in tuple(self._sealing_keys):
                if session_id not in live:
                    self.discard(session_id)
            if self._candidate is not None:
                _, candidate, deadline, monotonic_deadline = self._candidate
                if _abandoned(candidate, deadline, monotonic_deadline):
                    self.cancel()
            for session_id, pending in tuple(self._pending.items()):
                if _abandoned(pending.candidate, pending.deadline, pending.monotonic_deadline):
                    self.discard(session_id)

    def seconds_until_expiry(self) -> float | None:
        """Seconds until the earliest candidate or pending receipt is abandoned, or ``None``."""
        with self._lock:
            held = [
                (pending.candidate, pending.deadline, pending.monotonic_deadline) for pending in self._pending.values()
            ]
            if self._candidate is not None:
                held.append(self._candidate[1:])
        if not held:
            return None
        instant, elapsed = now(), time.monotonic()
        return max(
            0.0,
            min(
                min(
                    (
                        min(deadline, candidate.outcome.idle_deadline, candidate.outcome.absolute_deadline) - instant
                    ).total_seconds(),
                    monotonic_deadline - elapsed,
                )
                for candidate, deadline, monotonic_deadline in held
            ),
        )

    def cancel(self) -> None:
        """Release the unbound candidate; pending receipts of bound sessions stay."""
        with self._lock:
            self._candidate = None
            self._resumed_login = None
            if self._candidate_sealing_key is not None:
                self._candidate_sealing_key[:] = bytes(len(self._candidate_sealing_key))
                self._candidate_sealing_key = None
            self._lifetime.close()

    def close(self) -> None:
        """Release all candidate and pending-receipt proof without closing admitted leases."""
        with self._lock:
            for session_id in tuple(self._sealing_keys):
                self.discard(session_id)
            pending, self._pending = tuple(self._pending.values()), {}
            with ExitStack() as release:
                for item in pending:
                    release.push(item.lifetime)
                release.callback(self.cancel)
                release.callback(self._kdf_prewarm.close)


def _abandoned(candidate: ProfileLoginCandidate, deadline: UtcInstant, monotonic_deadline: float) -> bool:
    instant = now()
    return (
        instant < candidate.outcome.authenticated_at
        or instant >= min(deadline, candidate.outcome.idle_deadline, candidate.outcome.absolute_deadline)
        or time.monotonic() >= monotonic_deadline
    )
