"""Serialize human proof candidates without holding the profile fence."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from threading import Condition, RLock, get_ident

from cadrumo.application.user_profile.proof_cancellation import ProfileProofCancellation, ProfileProofCancelledError
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.deadline_budget import DEFAULT_TIMEOUT_POLICY, TimeoutDeadline
from cadrumo_client.contracts.profile_access import HumanProof
from cadrumo_client.transport.native_wake import NativeWake


class HumanProofQueue:
    """Keep the current proof owner while allowing queued proofs to cancel."""

    def __init__(self, stopping: NativeWake) -> None:
        """Bind the owner's shutdown wake and its reentrant proof slot."""
        self._stopping = stopping
        self._guard = Condition(RLock())
        self._owner: int | None = None
        self._depth = 0

    def notify(self) -> None:
        """Wake queued candidates to reobserve their cancellation or shutdown."""
        with self._guard:
            self._guard.notify_all()

    @contextmanager
    def admit(self, proof: HumanProof) -> Generator[None]:
        """Cancel a queued proof without releasing the current candidate owner."""
        cancellation = proof.cancellation or ProfileProofCancellation()
        timeout = (
            DEFAULT_TIMEOUT_POLICY.deadline()
            if proof.timeout_deadline is None
            else TimeoutDeadline(proof.timeout_deadline)
        )
        identity = get_ident()
        with cancellation.watch(self.notify):
            with self._guard:
                while True:
                    try:
                        cancellation.raise_if_cancelled()
                    except ProfileProofCancelledError:
                        raise AutomationCustodyError(AutomationCustodyCode.REQUESTER_DISCONNECTED) from None
                    if self._stopping.is_set():
                        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
                    if self._owner is None or self._owner == identity:
                        self._owner = identity
                        self._depth += 1
                        break
                    self._guard.wait(timeout=timeout.remaining_seconds())
            try:
                yield
            finally:
                with self._guard:
                    self._depth -= 1
                    if self._depth == 0:
                        self._owner = None
                        self._guard.notify_all()
