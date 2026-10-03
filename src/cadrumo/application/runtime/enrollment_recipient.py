"""Volatile protected enrollment handoff to one bound native client.

This broker neither opens native credential storage nor treats a server-side
write/read-back as client possession. Its borrowed work belongs to an already
verified transport channel, which must return an explicit bounded outcome.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from threading import Condition
from uuid import UUID, uuid4

from pydantic import SecretBytes

from ...core.identity.digest import ContentDigest
from ...core.time.clock import now
from ...core.time.utc import UtcInstant
from ..user_profile.access_contracts import ProfileAccessBinding
from ..user_profile.automation_administration import enrollment_review_digest
from ..user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ..user_profile.automation_enrollment import AutomationKeyIssuer, EnrollmentRecord, EnrollmentRequester
from .enrollment_access import EnrollmentCredentialBinding

_PRODUCER_MAX_SECONDS = 60.0
_POLL_MAX_SECONDS = 5.0
_CLOCK_RECHECK_SECONDS = 0.1


class EnrollmentWorkAction(StrEnum):
    """The only protected client actions this broker can request."""

    STORE = "store"
    POSSESSION = "possession"


@dataclass(frozen=True, slots=True)
class EnrollmentStored:
    """The bound client reports a completed protected native store write."""


@dataclass(frozen=True, slots=True)
class EnrollmentPresent:
    """The bound client returns its protected possession proof."""

    credential: SecretBytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class EnrollmentMissing:
    """The bound client confirms that the exact reference is absent."""


@dataclass(frozen=True, slots=True)
class EnrollmentRefused:
    """A bounded client attempt failed with only a typed safe reason."""

    reason: AutomationCustodyCode


type EnrollmentWorkResult = EnrollmentStored | EnrollmentPresent | EnrollmentMissing | EnrollmentRefused


@dataclass(slots=True, repr=False)
class EnrollmentWork:
    """A single borrowed command; candidate material is dropped on context exit."""

    command_id: UUID
    action: EnrollmentWorkAction
    credential_binding: EnrollmentCredentialBinding
    candidate: SecretBytes | None = field(repr=False)
    complete_callback: Callable[[EnrollmentWork, UUID, EnrollmentWorkResult], None] = field(repr=False)

    def complete(self, command_id: UUID, result: EnrollmentWorkResult) -> None:
        """Complete only the command borrowed by this transport call."""
        self.complete_callback(self, command_id, result)


@dataclass(slots=True, repr=False)
class _Pending:
    work: EnrollmentWork
    deadline: float
    record_expires_at: UtcInstant
    borrowed: bool = False
    result: EnrollmentWorkResult | None = field(default=None, repr=False)
    refusal: AutomationCustodyCode | None = None


class VolatileEnrollmentRecipient:
    """One immutable reviewed offer with at most one in-flight client exchange."""

    def __init__(
        self,
        *,
        requester: EnrollmentRequester,
        issuer: AutomationKeyIssuer,
        profile_binding: ProfileAccessBinding,
        enrollment_request_id: UUID,
        review_digest: ContentDigest,
        offer_expires_at: UtcInstant,
    ) -> None:
        """Pin the original consent independently of later record reloads."""
        self.requester = requester
        self._issuer = issuer
        self.profile_binding = profile_binding
        self.enrollment_request_id = enrollment_request_id
        self.review_digest = review_digest
        self.offer_expires_at = offer_expires_at
        self._offer_deadline = time.monotonic() + max(0.0, (offer_expires_at - now()).total_seconds())
        self._condition = Condition()
        self._pending: _Pending | None = None
        self._closed = False

    def _offer_remaining(self) -> float:
        return min(self._offer_deadline - time.monotonic(), (self.offer_expires_at - now()).total_seconds())

    def _binding(self, record: EnrollmentRecord) -> EnrollmentCredentialBinding:
        if (
            record.requester != self.requester
            or record.binding != self.profile_binding
            or record.request_id != self.enrollment_request_id
            or record.candidate_key_id is None
            or record.credential_reference is None
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        if not secrets.compare_digest(enrollment_review_digest(record), self.review_digest):
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        if self._offer_remaining() <= 0 or record.expires_at <= now():
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        return EnrollmentCredentialBinding(
            profile_binding=record.binding,
            client_id=record.requester.client_id,
            destination_id=record.requester.destination_id,
            credential_reference=record.credential_reference,
            grant_id=record.grant_id,
            key_id=record.candidate_key_id,
            review_digest=self.review_digest,
        )

    def _exchange(
        self, record: EnrollmentRecord, action: EnrollmentWorkAction, candidate: SecretBytes | None
    ) -> EnrollmentWorkResult:
        binding = self._binding(record)
        self._require_candidate_matches(binding, candidate)
        remaining = min(
            _PRODUCER_MAX_SECONDS,
            self._offer_remaining(),
            (record.expires_at - now()).total_seconds(),
        )
        if remaining <= 0:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        work = EnrollmentWork(uuid4(), action, binding, candidate, self._complete)
        pending = _Pending(work, time.monotonic() + remaining, record.expires_at)
        result, refusal = self._publish_and_wait(pending, record)
        return self._resolve_exchange_result(result, refusal)

    def _require_candidate_matches(self, binding: EnrollmentCredentialBinding, candidate: SecretBytes | None) -> None:
        if candidate is not None and self._issuer.verifier(candidate)[0] != binding.key_id:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)

    def _publish_and_wait(
        self, pending: _Pending, record: EnrollmentRecord
    ) -> tuple[EnrollmentWorkResult | None, AutomationCustodyCode | None]:
        with self._condition:
            if self._closed:
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
            if self._pending is not None:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            self._pending = pending
            self._condition.notify_all()
            self._wait_for_exchange(pending, record)
            result, refusal = pending.result, pending.refusal
            if self._pending is pending:
                self._pending = None
            self._condition.notify_all()
        return result, refusal

    def _wait_for_exchange(self, pending: _Pending, record: EnrollmentRecord) -> None:
        while pending.refusal is None and (pending.result is None or pending.borrowed):
            left = min(
                pending.deadline - time.monotonic(),
                self._offer_remaining(),
                (record.expires_at - now()).total_seconds(),
            )
            if left <= 0:
                self._fail_locked(AutomationCustodyCode.UNAVAILABLE)
                break
            self._condition.wait(min(left, _CLOCK_RECHECK_SECONDS))

    @staticmethod
    def _resolve_exchange_result(
        result: EnrollmentWorkResult | None, refusal: AutomationCustodyCode | None
    ) -> EnrollmentWorkResult:
        if refusal is not None:
            raise AutomationCustodyError(refusal)
        if result is None:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        return result

    def deliver(self, request: EnrollmentRecord, secret: SecretBytes) -> None:
        """Wait for one explicit client store acknowledgement, never local read-back."""
        result = self._exchange(request, EnrollmentWorkAction.STORE, secret)
        if not isinstance(result, EnrollmentStored):
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)

    def possession(self, request: EnrollmentRecord) -> SecretBytes | None:
        """Return only the bound client's explicit present or missing answer."""
        result = self._exchange(request, EnrollmentWorkAction.POSSESSION, None)
        if isinstance(result, EnrollmentMissing):
            return None
        if isinstance(result, EnrollmentPresent):
            return result.credential
        raise AutomationCustodyError(AutomationCustodyCode.INVALID)

    @contextmanager
    def borrow(self) -> Generator[EnrollmentWork | None]:
        """Poll for at most five seconds; the borrower owns completion and cleanup."""
        work = self._borrow_available_work()
        try:
            yield work
        finally:
            self._release_borrow(work)

    def _borrow_available_work(self) -> EnrollmentWork | None:
        with self._condition:
            remaining = self._offer_remaining()
            if self._closed or remaining <= 0:
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
            deadline = time.monotonic() + min(_POLL_MAX_SECONDS, remaining)
            pending = self._pending
            while pending is None or pending.borrowed:
                self._require_open()
                left = min(deadline - time.monotonic(), self._offer_remaining())
                if left <= 0:
                    return None
                self._condition.wait(min(left, _CLOCK_RECHECK_SECONDS))
                pending = self._pending
            pending.borrowed = True
            return pending.work

    def _release_borrow(self, work: EnrollmentWork | None) -> None:
        if work is None:
            return
        with self._condition:
            current = self._pending
            if current is not None and current.work is work:
                if current.result is None and current.refusal is None:
                    self._fail_locked(AutomationCustodyCode.UNAVAILABLE)
                else:
                    current.borrowed = False
                    self._condition.notify_all()
            work.candidate = None

    def _require_open(self) -> None:
        if self._closed:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    def _require_current_completion(self, pending: _Pending | None, work: EnrollmentWork, command_id: UUID) -> _Pending:
        if self._closed:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        if pending is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        if not pending.borrowed:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        if pending.work is not work:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        if command_id != work.command_id:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        if pending.result is not None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        if pending.refusal is not None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return pending

    def _require_completion_deadline(self, pending: _Pending) -> None:
        if pending.deadline <= time.monotonic() or self._offer_remaining() <= 0 or pending.record_expires_at <= now():
            self._fail_locked(AutomationCustodyCode.UNAVAILABLE)
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    def _record_completion(self, pending: _Pending, work: EnrollmentWork, result: EnrollmentWorkResult) -> None:
        if isinstance(result, EnrollmentRefused):
            pending.refusal = result.reason
        elif self._is_store_acknowledgement(work, result) or self._is_missing_answer(work, result):
            pending.result = result
        elif work.action is EnrollmentWorkAction.POSSESSION and isinstance(result, EnrollmentPresent):
            self._record_present_credential(pending, work, result)
        else:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)

    @staticmethod
    def _is_store_acknowledgement(work: EnrollmentWork, result: EnrollmentWorkResult) -> bool:
        return work.action is EnrollmentWorkAction.STORE and isinstance(result, EnrollmentStored)

    @staticmethod
    def _is_missing_answer(work: EnrollmentWork, result: EnrollmentWorkResult) -> bool:
        return work.action is EnrollmentWorkAction.POSSESSION and isinstance(result, EnrollmentMissing)

    def _record_present_credential(self, pending: _Pending, work: EnrollmentWork, result: EnrollmentPresent) -> None:
        if self._issuer.verifier(result.credential)[0] != work.credential_binding.key_id:
            self._fail_locked(AutomationCustodyCode.CREDENTIAL_REJECTED)
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        pending.result = result

    def _complete(self, work: EnrollmentWork, command_id: UUID, result: EnrollmentWorkResult) -> None:
        with self._condition:
            pending = self._require_current_completion(self._pending, work, command_id)
            self._require_completion_deadline(pending)
            self._record_completion(pending, work, result)
            self._condition.notify_all()

    def _fail_locked(self, reason: AutomationCustodyCode) -> None:
        """Fence this entire offer after an ambiguous or lost protected exchange."""
        self._closed = True
        pending = self._pending
        self._pending = None
        if pending is not None:
            pending.refusal = reason
            pending.work.candidate = None
        self._condition.notify_all()

    def close(self) -> None:
        """Fail all waiters and prevent reuse after client disconnect or shutdown."""
        with self._condition:
            self._fail_locked(AutomationCustodyCode.UNAVAILABLE)
