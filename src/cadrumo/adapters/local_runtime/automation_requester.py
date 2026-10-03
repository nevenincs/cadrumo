"""Bounded requester journey over one already prepared native enrollment client.

The caller owns the originating runtime connection. Human approval happens on
another connection; this module only submits and serves the exact requester's
protected delivery, then observes its canonical terminal receipt.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import remaining_budget
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    EnrollmentKind,
    EnrollmentProposal,
    EnrollmentStage,
)
from ...core.errors.hierarchy import CadrumoError
from ..persistence.storage.custody.automation_client_credentials import ClientCredentialMetadata
from .enrollment_client import NativeEnrollmentClient
from .frontend_client_contracts import RuntimeFrontendRefusedError


class AutomationReconcile(Protocol):
    """Fresh-root runtime reconciliation; its receipt conveys no login authority."""

    def __call__(self, submitted: AutomationReceiptProjection, /, *, timeout: float) -> AutomationReceiptProjection:
        """Observe one exact terminal result within the caller's remaining budget."""
        ...


class AutomationRequesterUncertainError(CadrumoError):
    """A request may have published, but no canonical terminal receipt was proved."""

    def __init__(self, request_id: UUID, reason: str) -> None:
        """Retain only safe recovery identity and an allowlisted refusal token."""
        self.request_id = request_id
        self.reason = reason
        super().__init__(
            "automation_requester_uncertain",
            context={"request_id": str(request_id), "completion": "unknown", "reason": reason},
        )


@dataclass(frozen=True, slots=True)
class AutomationRequesterCompletion:
    """Canonical terminal receipt and optional verified nonsecret key metadata."""

    submitted: AutomationReceiptProjection
    terminal: AutomationReceiptProjection
    credential: ClientCredentialMetadata | None


def _reason(error: Exception) -> str:
    if isinstance(error, (RuntimeRefusalError, AutomationCustodyError, ProfileAccessRefusedError)):
        return error.reason.value
    if isinstance(error, RuntimeFrontendRefusedError):
        allowed = {
            item.value for group in (AccessDenialCode, AutomationCustodyCode, RuntimeRefusalCode) for item in group
        }
        return error.reason if error.reason in allowed else AutomationCustodyCode.UNAVAILABLE.value
    return AutomationCustodyCode.UNAVAILABLE.value


class AutomationRequesterJourney:
    """Submit once, expose the review, and incrementally serve bounded delivery.

    The prepared client borrows its frontend connection. Neither this object nor
    a timed-out step closes that connection or cancels a native write. The caller
    keeps it alive until terminal observation or explicit uncertain recovery.
    """

    def __init__(
        self,
        client: NativeEnrollmentClient,
        *,
        timeout: float,
        reconcile: AutomationReconcile | None = None,
    ) -> None:
        """Bind one offer and a finite total budget before publication."""
        if not math.isfinite(timeout) or timeout <= 0 or timeout > 300:
            raise ValueError("requester timeout must be finite and at most five minutes")
        self._client = client
        self._timeout = timeout
        self._reconcile = reconcile
        self._deadline: float | None = None
        self._attempted = False
        self._kind: EnrollmentKind | None = None
        self._submitted: AutomationReceiptProjection | None = None
        self._terminal: AutomationRequesterCompletion | None = None

    @property
    def submitted(self) -> AutomationReceiptProjection | None:
        """Expose the safe review identity as soon as submission is acknowledged."""
        return self._submitted

    @property
    def completion(self) -> AutomationRequesterCompletion | None:
        """Expose a terminal outcome only after exact validation and custody checks."""
        return self._terminal

    def _remaining(self) -> float:
        deadline = self._deadline
        if deadline is None:
            raise ValueError("requester proposal has not been submitted")
        return remaining_budget(deadline)

    def _wire_timeout(self) -> float:
        return min(self._remaining(), 10.0)

    def _uncertain(self, error: Exception) -> AutomationRequesterUncertainError:
        return AutomationRequesterUncertainError(self._client.prepared.enrollment_request_id, _reason(error))

    def submit(self, proposal: EnrollmentProposal) -> AutomationReceiptProjection:
        """Publish at most once, retaining the request identity on an uncertain ACK."""
        if self._attempted:
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        self._attempted = True
        self._kind = proposal.kind
        self._deadline = time.monotonic() + self._timeout
        try:
            submitted = self._client.submit(proposal, timeout=self._wire_timeout())
            if submitted.stage is not EnrollmentStage.REQUESTED:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        except (
            AutomationCustodyError,
            ProfileAccessRefusedError,
            RuntimeRefusalError,
            RuntimeFrontendRefusedError,
        ) as error:
            raise self._uncertain(error) from error
        self._submitted = submitted
        return submitted

    def _finish(self, receipt: AutomationReceiptProjection) -> AutomationReceiptProjection:
        if receipt.stage not in {EnrollmentStage.COMPLETE, EnrollmentStage.DECLINED}:
            return receipt
        submitted = self._submitted
        if submitted is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if receipt.stage is EnrollmentStage.COMPLETE and (
            (receipt.key_id is not None) != (self._kind in {EnrollmentKind.ENROLL, EnrollmentKind.ROTATE})
        ):
            raise self._uncertain(RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME))
        try:
            credential = self._client.verified_terminal()
        except (AutomationCustodyError, RuntimeRefusalError) as error:
            raise self._uncertain(error) from error
        self._terminal = AutomationRequesterCompletion(submitted, receipt, credential)
        return receipt

    def _recover(self, original: Exception) -> AutomationReceiptProjection:
        """Use fresh-root reconciliation only after the old connection refuses."""
        callback = self._reconcile
        if callback is None:
            raise self._uncertain(original) from original
        submitted = self._submitted
        if submitted is None:
            raise self._uncertain(original) from original
        try:
            receipt = callback(submitted, timeout=self._remaining())
            if receipt.stage not in {EnrollmentStage.COMPLETE, EnrollmentStage.DECLINED}:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            self._client.accept_reconciled_terminal(receipt)
            return self._finish(receipt)
        except (
            AutomationCustodyError,
            ProfileAccessRefusedError,
            RuntimeRefusalError,
            RuntimeFrontendRefusedError,
        ) as error:
            raise self._uncertain(error) from error

    def step(self) -> AutomationReceiptProjection:
        """Inspect once, serve one protected command, and return current safe state.

        A caller may render the submitted review while invoking this method off
        the UI loop. An idle poll is progress-neutral, never terminal success.
        """
        if self._terminal is not None:
            return self._terminal.terminal
        submitted = self._submitted
        if submitted is None:
            raise ValueError("requester proposal has not been submitted")
        try:
            observed = self._client.inspect(timeout=self._wire_timeout())
        except (AutomationCustodyError, ProfileAccessRefusedError, RuntimeRefusalError) as error:
            return self._recover(error)
        if observed is None:
            raise self._uncertain(RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME))
        if observed.stage in {EnrollmentStage.COMPLETE, EnrollmentStage.DECLINED}:
            return self._finish(observed)
        try:
            self._client.poll(timeout=self._wire_timeout())
        except (AutomationCustodyError, ProfileAccessRefusedError, RuntimeRefusalError) as error:
            # Publication may retire the source API lease between a delivery
            # ACK and this poll's reply. Exact old-connection inspection is the
            # last local check; only fresh-root reconciliation can follow it.
            try:
                final = self._client.inspect(timeout=self._wire_timeout())
            except (AutomationCustodyError, ProfileAccessRefusedError, RuntimeRefusalError):
                return self._recover(error)
            if final is not None and final.stage in {EnrollmentStage.COMPLETE, EnrollmentStage.DECLINED}:
                return self._finish(final)
            raise self._uncertain(error) from error
        return observed

    def wait_for_terminal(self) -> AutomationRequesterCompletion:
        """Drive incremental steps within the original total budget."""
        while True:
            self.step()
            completion = self._terminal
            if completion is not None:
                return completion
            try:
                time.sleep(min(0.05, self._remaining()))
            except RuntimeRefusalError as error:
                raise self._uncertain(error) from error
