"""Nonselecting human-proof candidates for an immutable profile worker."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import ExitStack
from datetime import timedelta
from threading import RLock
from uuid import UUID, uuid4

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


class ProfileWorkerHumanLogin:
    """Retain at most one short-lived candidate under the runtime's admission guard."""

    def __init__(self, custody: ProfileWorkerCustody, *, decode: Callable[[], ProfileDecodeContext]) -> None:
        """Bind an exact worker and its pinned authority; do not open custody."""
        self.custody, self.decode = custody, decode
        self._lock = RLock()
        self._candidate: tuple[UUID, ProfileLoginCandidate, UtcInstant, float] | None = None
        self._lifetime = ExitStack()

    def authenticate(self, password: bytearray) -> tuple[UUID, ProfileLoginOutcome]:
        """Prove the exact password without disturbing another admitted lease."""
        with self._lock:
            self.close()
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
                self.close()
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED) from None
            except BaseException:
                self.close()
                raise

    def resume(self, receipt_key: bytearray) -> tuple[UUID, ProfileLoginOutcome]:
        """Verify supplied human receipt proof without looking up a secret for the caller."""
        with self._lock:
            self.close()
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
                self.close()
                refusal = {
                    ProfileSessionRefusalReason.EXPIRED_IDLE: AccessDenialCode.SESSION_EXPIRED,
                    ProfileSessionRefusalReason.EXPIRED_ABSOLUTE: AccessDenialCode.SESSION_EXPIRED,
                    ProfileSessionRefusalReason.CUSTODY_CHANGED: AccessDenialCode.CUSTODY_CHANGED,
                }.get(error.reason, AccessDenialCode.AUTHENTICATION_REQUIRED)
                raise ProfileAccessRefusedError(refusal) from None
            except BaseException:
                self.close()
                raise

    def bind(
        self, candidate_id: UUID, lease: AccessSession, *, persist_receipt: bool = False
    ) -> ProfileHumanLoginReceipt:
        """Promote only the candidate and deadlines that the authority just admitted."""
        with self._lock:
            self.expire()
            current = self._candidate
            if current is None or current[0] != candidate_id:
                raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
            _, candidate, _, _ = current
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
                persisted = (
                    candidate.persist_acceleration_receipt(login_id=login_id, binding=lease.binding)
                    if persist_receipt
                    else outcome.session_persisted
                )
                return ProfileHumanLoginReceipt(
                    authenticated_at=outcome.authenticated_at,
                    idle_deadline=outcome.idle_deadline,
                    absolute_deadline=outcome.absolute_deadline,
                    session_persisted=persisted,
                    resumed=outcome.already_authenticated,
                )
            except BaseException:
                self.custody.retire(lease.session_id)
                raise
            finally:
                material[:] = bytes(len(material))
                self.close()

    def expire(self) -> None:
        """Release abandoned candidate keys even when the command stream is idle."""
        with self._lock:
            if self._candidate is not None:
                _, candidate, deadline, monotonic_deadline = self._candidate
                instant = now()
                if (
                    instant < candidate.outcome.authenticated_at
                    or instant >= min(deadline, candidate.outcome.idle_deadline, candidate.outcome.absolute_deadline)
                    or time.monotonic() >= monotonic_deadline
                ):
                    self.close()

    def close(self) -> None:
        """Release candidate custody without closing independently admitted leases."""
        with self._lock:
            self._candidate = None
            self._lifetime.close()
