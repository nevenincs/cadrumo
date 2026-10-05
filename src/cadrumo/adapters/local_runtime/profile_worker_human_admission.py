"""ProfileWorkerHumanAdmission for runtime-owned profile worker custody."""

from __future__ import annotations

import time
from collections.abc import Generator
from contextlib import contextmanager
from uuid import UUID, uuid4

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.profile_access import RuntimeHumanProofMethod
from ...application.runtime.profile_worker import (
    ProfileWorkerControlRequest,
    ProfileWorkerHumanBindingRequest,
    ProfileWorkerHumanBound,
    ProfileWorkerHumanOutcome,
    ProfileWorkerHumanReceiptRequest,
    ProfileWorkerRequest,
    ProfileWorkerStatus,
)
from ...application.user_profile.access_contracts import AccessSession
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.login_session import ProfileHumanLoginReceipt, ProfileLoginOutcome
from ...application.user_profile.login_session_port import ProfileSignInGenerationPort
from ...core.async_cleanup import AsyncResourceCleanupError
from .profile_worker_operation_client import ProfileWorkerOperationClient
from .worker_admission_budget import WORKER_ADMISSION_PREPARE_TIMEOUT_SECONDS
from .worker_resource_cleanup import WorkerResourceCleanup, release_worker_resources


class ProfileWorkerHumanAdmission(ProfileWorkerOperationClient):
    """Own the worker capability while retaining native custody and deadlines."""

    @contextmanager
    def authenticate_human(
        self,
        secret: bytearray,
        *,
        method: RuntimeHumanProofMethod = "password",
        originating_login_id: str | None = None,
    ) -> Generator[ProfileLoginOutcome]:
        """Borrow a proven human outcome while the runtime admits its human lease.

        A receipt proof must travel with ``originating_login_id``, the native
        login captured for the presenting connection, so the worker verifies
        the receipt against it before any unwrap. A password proof carries none.
        """
        with self._human_lock:
            started = time.monotonic()
            transaction_deadline = started + WORKER_ADMISSION_PREPARE_TIMEOUT_SECONDS + 10
            primary: BaseException | None = None
            try:
                self._human_deadline = transaction_deadline
                request = ProfileWorkerControlRequest(
                    action=method,
                    request_id=uuid4(),
                    originating_login_id=originating_login_id if method == "receipt" else None,
                )
                result = self._exchange(
                    ProfileWorkerRequest(request),
                    ProfileWorkerHumanOutcome,
                    secret,
                    deadline=started + WORKER_ADMISSION_PREPARE_TIMEOUT_SECONDS,
                )
                self._human_candidate = result.candidate_id
                yield result.login
            except BaseException as error:
                primary = error
                raise
            finally:
                self._human_candidate = None
                self._human_deadline = None
                secret[:] = bytes(len(secret))
                if self._channel is not None and not self._stopping.is_set():
                    try:
                        self._exchange(
                            ProfileWorkerRequest(
                                ProfileWorkerControlRequest(action="cancel_human", request_id=uuid4())
                            ),
                            ProfileWorkerStatus,
                            deadline=time.monotonic() + 10,
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
            if time.monotonic() >= transaction_deadline:
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)

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
        deadline = min(time.monotonic() + 10, self._human_deadline)
        if deadline <= time.monotonic():
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        result = self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerHumanBindingRequest(
                    request_id=uuid4(),
                    candidate_id=self._human_candidate,
                    lease=lease,
                    persist_receipt=persist_receipt,
                )
            ),
            ProfileWorkerHumanBound,
            deadline=deadline,
        )
        if result.session_id != lease.session_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._human_candidate = None
        return result

    def mint_human_receipt(self, session_id: UUID, sign_in: ProfileSignInGenerationPort) -> ProfileHumanLoginReceipt:
        """Mint a bound session's pending receipt, stamped with ``sign_in`` exactly."""
        result = self._exchange(
            ProfileWorkerRequest(
                ProfileWorkerHumanReceiptRequest(
                    request_id=uuid4(),
                    session_id=session_id,
                    sign_in_lineage=sign_in.lineage,
                    sign_in_generation=sign_in.generation,
                )
            ),
            ProfileWorkerHumanBound,
        )
        if result.session_id != session_id or result.receipt_pending:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
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
