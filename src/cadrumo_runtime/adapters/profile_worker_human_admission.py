"""ProfileWorkerHumanAdmission for runtime-owned profile worker custody."""

from __future__ import annotations

import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from uuid import UUID, uuid4

from cadrumo.application.user_profile.access_contracts import AccessSession
from cadrumo.application.user_profile.login_session_port import ProfileSignInGenerationPort
from cadrumo.application.user_profile.proof_cancellation import ProfileProofCancellation
from cadrumo.core.async_cleanup import AsyncResourceCleanupError
from cadrumo.core.profile_session import ProfileHumanLoginReceipt
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import DEFAULT_TIMEOUT_POLICY
from cadrumo_client.contracts.profile_access import HumanProofMethod
from cadrumo_client.contracts.sign_in_outcomes import ProfileLoginOutcome
from cadrumo_runtime.contracts.profile_worker import (
    ProfileWorkerControlRequest,
    ProfileWorkerHumanBindingRequest,
    ProfileWorkerHumanBound,
    ProfileWorkerHumanOutcome,
    ProfileWorkerHumanReceiptRequest,
    ProfileWorkerRequest,
    ProfileWorkerStatus,
)

from .worker_proof_control import ProfileWorkerProofControl
from .worker_resource_cleanup import WorkerResourceCleanup, release_worker_resources


class ProfileWorkerHumanAdmission(ProfileWorkerProofControl):
    """Own the worker capability while retaining native custody and deadlines."""

    @contextmanager
    def authenticate_human(
        self,
        secret: bytearray,
        *,
        method: HumanProofMethod = "password",
        originating_login_id: str | None = None,
        timeout_deadline: float | None = None,
        attempt_id: UUID | None = None,
        cancellation: ProfileProofCancellation | None = None,
    ) -> Generator[ProfileLoginOutcome]:
        """Borrow a proven human outcome while the runtime admits its human lease.

        A receipt proof must travel with ``originating_login_id``, the native
        login captured for the presenting connection, so the worker verifies
        the receipt against it before any unwrap. A password proof carries none.
        """
        transaction_deadline = timeout_deadline or DEFAULT_TIMEOUT_POLICY.deadline().instant
        attempt_id = attempt_id or uuid4()
        with self._human_lock, self._proof_attempt(attempt_id, secret, cancellation, transaction_deadline):
            primary: BaseException | None = None
            try:
                self._human_deadline = transaction_deadline
                self._human_transaction_deadline = transaction_deadline
                request = ProfileWorkerControlRequest(
                    action=method,
                    request_id=uuid4(),
                    originating_login_id=originating_login_id if method == "receipt" else None,
                    timeout_deadline=transaction_deadline,
                    proof_attempt_id=attempt_id,
                )
                result = self._exchange(
                    ProfileWorkerRequest(request),
                    ProfileWorkerHumanOutcome,
                    secret,
                    deadline=transaction_deadline,
                )
                self._human_candidate = result.candidate_id
                # Unbound proof custody expires after five minutes; this is
                # independent of how long startup or scheduling took.
                self._human_deadline = min(transaction_deadline, time.monotonic() + 300)
                yield result.login
            except BaseException as error:
                primary = error
                raise
            finally:
                self._human_candidate = None
                self._human_deadline = None
                self._human_transaction_deadline = None
                secret[:] = bytes(len(secret))
                self._cancel_human_candidate(primary, transaction_deadline)
            if time.monotonic() >= transaction_deadline:
                raise RefusalError(RefusalCode.TIMEOUT)

    def _cancel_human_candidate(self, primary: BaseException | None, deadline: float) -> None:
        """Retire only this candidate and retain any cleanup failure."""
        if self._channel is not None and not self._stopping.is_set():
            try:
                self._exchange(
                    ProfileWorkerRequest(ProfileWorkerControlRequest(action="cancel_human", request_id=uuid4())),
                    ProfileWorkerStatus,
                    deadline=deadline,
                )
            except BaseException as failure:
                # Protocol failures already retain their original native
                # close owner. A typed refusal also fences this worker;
                # never retry a bare cancel against a later candidate.
                if not self._stopping.is_set():
                    release_worker_resources(WorkerResourceCleanup(self.close), primary_error=failure)
                if primary is None:
                    raise
                _attach_human_cleanup_failure(primary, failure)

    @contextmanager
    def _proof_attempt(
        self, attempt_id: UUID, secret: bytearray, cancellation: ProfileProofCancellation | None, deadline: float
    ) -> Generator[None]:
        """Register before dispatch and retire only this proof's cancellation token."""
        cancellation = cancellation or ProfileProofCancellation()
        try:
            self._proof_command("register", attempt_id, deadline=deadline)
        except BaseException:
            secret[:] = bytes(len(secret))
            raise
        try:
            with cancellation.watch(lambda: self._cancel_proof_attempt(attempt_id, deadline=deadline)):
                self._human_cancellation = cancellation
                yield
        finally:
            self._human_cancellation = None
            secret[:] = bytes(len(secret))
            if not self._stopping.is_set():
                release_worker_resources(
                    WorkerResourceCleanup(lambda: self._proof_command("finish", attempt_id, deadline=deadline)),
                    primary_error=sys.exception(),
                )

    @property
    def human_admission_deadline(self) -> float:
        """Expose the trusted original bound only while a candidate is borrowed."""
        if self._human_deadline is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return self._human_deadline

    def bind_human(self, lease: AccessSession, *, persist_receipt: bool = False) -> ProfileWorkerHumanBound:
        """Promote only the human candidate held by this admission context.

        A requested receipt is not minted here: the worker keeps its proof
        pending until :meth:`mint_human_receipt` or the lease's retirement.
        """
        if self._human_candidate is None or self._human_deadline is None:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        if self._human_deadline <= time.monotonic():
            raise RefusalError(RefusalCode.TIMEOUT)
        deadline = self._human_transaction_deadline or self._human_deadline
        result = self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerHumanBindingRequest(
                    request_id=uuid4(),
                    candidate_id=self._human_candidate,
                    lease=lease,
                    persist_receipt=persist_receipt,
                    timeout_deadline=deadline,
                )
            ),
            ProfileWorkerHumanBound,
            deadline=deadline,
        )
        if result.session_id != lease.session_id:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._human_candidate = None
        return result

    def mint_human_receipt(
        self, session_id: UUID, sign_in: ProfileSignInGenerationPort, *, deadline: float | None = None
    ) -> ProfileHumanLoginReceipt:
        """Mint a bound session's pending receipt, stamped with ``sign_in`` exactly."""
        result = self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerHumanReceiptRequest(
                    request_id=uuid4(),
                    session_id=session_id,
                    sign_in_lineage=sign_in.lineage,
                    sign_in_generation=sign_in.generation,
                    timeout_deadline=deadline,
                )
            ),
            ProfileWorkerHumanBound,
            deadline=deadline,
        )
        if result.session_id != session_id or result.receipt_pending:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return result.receipt


def _attach_human_cleanup_failure(primary: BaseException, failure: BaseException) -> None:
    """Merge each original native cleanup owner once into the preserved admission failure."""
    cleanup = AsyncResourceCleanupError((), (failure,), retry_task_name="human-candidate-cleanup", close_attempts=1)
    seen: set[int] = set()
    for error in (failure, primary):
        for field in ("async_cleanup_error", "cleanup_error"):
            retained = error.__dict__.get(field)
            if isinstance(retained, AsyncResourceCleanupError) and id(retained) not in seen:
                seen.add(id(retained))
                cleanup = retained.merged_with(cleanup)
    primary.__dict__["async_cleanup_error"] = cleanup
    primary.__dict__["cleanup_error"] = cleanup
    primary.add_note("Human candidate cleanup failed; original native owner retained")
