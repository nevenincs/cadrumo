"""Compose application session admission with real immutable worker custody."""

from __future__ import annotations

import time
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from datetime import datetime
from pathlib import Path
from threading import Event, Lock, RLock, Thread, get_ident
from uuid import UUID

from ...adapters.local_runtime.profile_worker import ProfileWorkerProcess, unreturned_profile_worker
from ...adapters.persistence.storage.custody.sign_in_generation import SignInGeneration, SignInGenerationCustody
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.profile_access import RuntimeHumanProof
from ...application.runtime.profile_worker import ProfileWorkerIdentity
from ...application.runtime.worker_authorization import WorkerAuthorizationOwner
from ...application.user_profile.access_contracts import AccessSession
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.login_session import ProfileHumanLoginReceipt, ProfileLoginOutcome
from ...application.user_profile.session_authority_contracts import SessionAuthorityFacts
from ...core.time.clock import now


class ProfileWorkerSessionOwner:
    """Trusted transport/lifecycle observations and profile-fixed custody delivery.

    Observation and human-secret callbacks belong to the native runtime host;
    they are not decoded from client documents. A failed worker fences this owner
    until its authority is discarded and the caller authenticates afresh.
    """

    def __init__(
        self,
        identity: ProfileWorkerIdentity,
        *,
        storage_root: Path,
        observe: Callable[[UUID], SessionAuthorityFacts],
        human_secret: Callable[[UUID], AbstractContextManager[RuntimeHumanProof]],
        guard: RLock,
        authorization: WorkerAuthorizationOwner | None = None,
        worker_script: Path | None = None,
        wall_clock: Callable[[], datetime] = now,
    ) -> None:
        """Share the profile denial guard with the existing authority and administration."""
        self.identity, self.root = identity, storage_root
        self._observe, self._human_secret, self._guard = observe, human_secret, guard
        self._worker: ProfileWorkerProcess | None = None
        self._lost = False
        self._authorization = authorization
        self._worker_script = worker_script
        self._wall_clock = wall_clock
        self._retiring: list[ProfileWorkerProcess] = []
        self._lifecycle_guard = RLock()
        self._activity_guard = Lock()
        self._stopping = Event()
        self._construction_done = Event()
        self._construction_done.set()
        self._construction_failure = False
        self._api_guard = Lock()
        self._prepared_api_worker: ProfileWorkerProcess | None = None
        self._api_thread: int | None = None
        self._api_connection: UUID | None = None
        self._api_deadline: float | None = None
        self._human_guard = RLock()
        self._prepared_human_worker: ProfileWorkerProcess | None = None
        self._human_thread: int | None = None
        self._human_connection: UUID | None = None
        self._persist_human_receipt = False
        self._human_receipts: dict[UUID, ProfileHumanLoginReceipt] = {}
        self._pending_human_receipts: dict[UUID, ProfileWorkerProcess] = {}
        self._human_sign_ins: dict[UUID, SignInGeneration] = {}

    @contextmanager
    def admission_guard(self) -> Generator[None]:
        """Serialize admission, worker changes and durable denial under one owner."""
        with self._guard:
            yield

    def facts(self, connection_id: UUID) -> SessionAuthorityFacts:
        """Reobserve native facts without allowing an old lease to survive worker loss."""
        with self._lifecycle_guard:
            if self._lost:
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
            worker = self._worker
        if worker is not None:
            try:
                worker.require_alive()
            except RuntimeRefusalError as error:
                if error.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED:
                    raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
                self.close()
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
        facts = self._observe(connection_id)
        with self._lifecycle_guard:
            if self._lost or self._stopping.is_set():
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        if (
            facts.profile.binding != self.identity.binding
            or facts.context.runtime_boot_id != self.identity.runtime_boot_id
            or facts.context.connection_id != connection_id
        ):
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        return facts

    @property
    def lost(self) -> bool:
        """Whether this worker incarnation has irreversibly lost its authority."""
        return self._lost

    def operation_worker(self) -> ProfileWorkerProcess:
        """Borrow an already admitted worker without holding the guard during callbacks."""
        with self._guard:
            if self._lost or self._worker is None:
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
            self._worker.require_alive()
            return self._worker

    def in_flight_operation_count(self, *, deadline: float) -> int | None:
        """Observe the exact worker count without constructing or renewing custody."""
        if not self._lifecycle_guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            return None
        try:
            if self._lost or self._stopping.is_set() or self._retiring or not self._construction_done.is_set():
                return None
            worker = self._worker
        finally:
            self._lifecycle_guard.release()
        if worker is None:
            return 0
        if time.monotonic() >= deadline or not self._activity_guard.acquire(blocking=False):
            return None
        finished = Event()
        result: list[int | None] = [None]

        def observe() -> None:
            try:
                # Preserve the worker's own control-exchange budget. A short
                # heartbeat timeout must not kill a healthy busy worker. Only
                # one observation may remain pending; its late answer is never
                # reused as proof that a subsequent admission fence was idle.
                result[0] = worker.status().in_flight_operations
            except (RuntimeRefusalError, AutomationCustodyError):
                pass
            finally:
                self._activity_guard.release()
                finished.set()

        Thread(target=observe, name="profile-worker-activity", daemon=True).start()
        if not finished.wait(max(0.0, deadline - time.monotonic())):
            return None
        return result[0]

    @contextmanager
    def _custody(self) -> Generator[ProfileWorkerProcess]:
        constructing, worker = self._select_worker_for_custody()
        candidate: ProfileWorkerProcess | None = None
        try:
            if constructing:
                candidate = ProfileWorkerProcess(
                    self.identity,
                    storage_root=self.root,
                    authorization=self._authorization,
                    worker_script=self._worker_script,
                    wall_clock=self._wall_clock,
                )
                with self._lifecycle_guard:
                    if self._stopping.is_set():
                        self._retiring.append(candidate)
                    else:
                        self._worker = candidate
                        worker = candidate
                        candidate = None
                if candidate is not None:
                    candidate.close()
                    raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
            if worker is None:
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
            yield worker
        except BaseException as error:
            candidate = self._retain_failed_candidate(error, constructing, candidate, worker)
            self._retire_failed_runtime(error, candidate, worker)
            raise
        finally:
            if constructing:
                self._construction_done.set()

    def _select_worker_for_custody(self) -> tuple[bool, ProfileWorkerProcess | None]:
        with self._lifecycle_guard:
            if self._lost or self._stopping.is_set():
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
            worker = self._worker
            if worker is not None:
                return False, worker
            if not self._construction_done.is_set():
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
            self._construction_done.clear()
            return True, None

    def _retain_failed_candidate(
        self,
        error: BaseException,
        constructing: bool,
        candidate: ProfileWorkerProcess | None,
        worker: ProfileWorkerProcess | None,
    ) -> ProfileWorkerProcess | None:
        candidate = (unreturned_profile_worker(error) or candidate) if constructing else None
        if candidate is not None:
            with self._lifecycle_guard:
                if all(candidate is not retained for retained in self._retiring):
                    self._retiring.append(candidate)
            # The constructor has attempted immediate containment. Keep failed
            # releases and callbacks owned even after a wire refusal.
            self.begin_drain()
        if constructing and self._stopping.is_set() and candidate is None and worker is None:
            self._construction_failure = True
        return candidate

    def _retire_failed_runtime(
        self,
        error: BaseException,
        candidate: ProfileWorkerProcess | None,
        worker: ProfileWorkerProcess | None,
    ) -> None:
        if candidate is not None or not isinstance(error, RuntimeRefusalError):
            return
        with self._lifecycle_guard:
            undispatched_timeout = (
                error.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
                and worker is not None
                and worker is self._worker
                and not worker.stopping
            )
        # A queue timeout leaves the exact healthy worker untouched; every
        # other failed dispatched exchange fences custody.
        if not undispatched_timeout:
            self.close()

    @contextmanager
    def prepare_api_admission(self, connection_id: UUID) -> Generator[float]:
        """Prepare one key-free candidate outside the profile denial fence."""
        if not self._api_guard.acquire(blocking=False):
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        try:
            with self._custody() as worker:
                # This is the existing 30-second preparation/install budget,
                # captured after bounded native construction and never renewed.
                deadline = time.monotonic() + 30
                worker.prepare_api_admission(deadline=deadline)
                self._prepared_api_worker = worker
                self._api_thread = get_ident()
                self._api_connection = connection_id
                self._api_deadline = deadline
                yield deadline
        finally:
            self._prepared_api_worker = None
            self._api_thread = None
            self._api_connection = None
            self._api_deadline = None
            self._api_guard.release()

    def activate(self, session: AccessSession, dek: bytearray) -> None:
        """Install only into the exact prepared API worker under the denial fence."""
        with self._lifecycle_guard:
            worker, deadline = self._prepared_api_worker, self._api_deadline
            if (
                self._lost
                or self._stopping.is_set()
                or worker is None
                or worker is not self._worker
                or self._api_thread != get_ident()
                or self._api_connection != session.connection_id
                or deadline is None
                or time.monotonic() >= deadline
            ):
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        worker.install(session, dek, deadline=deadline)

    def refresh(self, session: AccessSession) -> None:
        """Propagate the authority's current grant-bound deadline into custody."""
        with self._custody() as worker:
            worker.refresh(session)

    def share(self, session: AccessSession, parent: AccessSession) -> None:
        """Attach only a child naming the exact parent already admitted here."""
        if parent.session_id != session.parent_session_id or parent.binding != self.identity.binding:
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        with self._custody() as worker:
            worker.share(session)

    @contextmanager
    def authenticate_human(self, connection_id: UUID) -> Generator[tuple[ProfileLoginOutcome, str]]:
        """Borrow a protected human proof channel and native originating-login identity."""
        # Serialize candidates without holding the profile denial fence while
        # the existing worker constructs, authenticates or releases proof.
        with self._human_guard, self._human_secret(connection_id) as proof:
            try:
                self._persist_human_receipt = proof.persist_receipt
                with self._custody() as worker:
                    self._prepared_human_worker = worker
                    self._human_thread = get_ident()
                    self._human_connection = connection_id
                    with worker.authenticate_human(
                        proof.secret, originating_login_id=proof.originating_login_id, method=proof.method
                    ) as outcome:
                        yield outcome, proof.originating_login_id
            finally:
                self._prepared_human_worker = None
                self._human_thread = None
                self._human_connection = None
                self._persist_human_receipt = False
                proof.secret[:] = bytes(len(proof.secret))

    def human_admission_deadline(self, connection_id: UUID) -> float:
        """Capture the exact candidate's original bound before releasing its context."""
        worker = self._prepared_human_worker
        if worker is None or self._human_thread != get_ident() or self._human_connection != connection_id:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return worker.human_admission_deadline

    def bind_human(self, session: AccessSession) -> None:
        """Commit the exact human candidate only after application admission."""
        with self._lifecycle_guard:
            worker = self._prepared_human_worker
            if (
                self._lost
                or self._stopping.is_set()
                or worker is None
                or worker is not self._worker
                or self._human_thread != get_ident()
                or self._human_connection != session.connection_id
            ):
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        bound = worker.bind_human(session, persist_receipt=self._persist_human_receipt)
        self._human_receipts[session.session_id] = bound.receipt
        if bound.receipt_pending:
            self._pending_human_receipts[session.session_id] = worker

    def capture_human_sign_in(self, session_id: UUID) -> bool:
        """Capture, at publication, the sign-in generation a pending receipt will carry.

        The caller holds the admission guard and has just published the session.
        A missing or unusable generation record is created and fsynced here, so
        the record exists before any receipt can name it. Return ``False``,
        writing nothing, when the session's login asked for no receipt.
        """
        if session_id not in self._pending_human_receipts:
            return False
        sign_in = SignInGenerationCustody(root=self.root, binding=self.identity.binding)
        self._human_sign_ins[session_id] = sign_in.establish().current
        return True

    def mint_human_receipt(self, session_id: UUID) -> None:
        """Mint a still-published session's receipt with the generation captured at publication.

        The caller holds the admission guard. The worker refuses to write when
        the captured generation has moved since, and reports no persistence.
        """
        worker = self._pending_human_receipts.pop(session_id, None)
        sign_in = self._human_sign_ins.pop(session_id, None)
        with self._lifecycle_guard:
            if worker is None or sign_in is None or self._lost or worker is not self._worker:
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        self._human_receipts[session_id] = worker.mint_human_receipt(session_id, sign_in)

    def take_human_login_receipt(self, session_id: UUID) -> ProfileHumanLoginReceipt | None:
        """Consume the nonsecret acknowledgement after exact-session admission."""
        return self._human_receipts.pop(session_id, None)

    def retire(self, session_id: UUID) -> None:
        """Release an admitted lineage; retirement never starts a replacement worker.

        The worker discards a pending receipt with the lineage, so a session
        retired before its mint leaves no receipt.
        """
        self._human_receipts.pop(session_id, None)
        self._pending_human_receipts.pop(session_id, None)
        self._human_sign_ins.pop(session_id, None)
        if self._worker is not None:
            with self._custody() as worker:
                worker.retire(session_id)

    def close(self) -> None:
        """Fence old leases before terminating all owned profile processes."""
        with self._lifecycle_guard:
            self._stopping.set()
            self._lost = True
            self._human_receipts.clear()
            self._pending_human_receipts.clear()
            self._human_sign_ins.clear()
            worker, self._worker = self._worker, None
            if worker is not None:
                self._retiring.append(worker)
            retiring = tuple(self._retiring)
        failures: list[Exception] = []
        for owned in retiring:
            try:
                owned.close()
            except Exception as error:
                failures.append(error)
        if failures:
            raise ExceptionGroup("worker containment failed", failures)

    def begin_drain(self) -> ProfileWorkerProcess | None:
        """Fence construction and take the published worker without a profile guard."""
        with self._lifecycle_guard:
            self._stopping.set()
            self._lost = True
            worker, self._worker = self._worker, None
            if worker is not None:
                self._retiring.append(worker)
            return worker

    def wait_construction(self, *, deadline: float) -> bool:
        """Wait for a pre-fence launch to contain itself before owner release."""
        return (
            self._construction_done.wait(timeout=max(0.0, deadline - time.monotonic()))
            and not self._construction_failure
        )

    def settle(self, *, deadline: float | None = None) -> None:
        """Prove containment and finish callbacks before forgetting owned resources."""
        with self._lifecycle_guard:
            retiring = tuple(self._retiring)
        failures: list[Exception] = []
        for worker in retiring:
            try:
                # A previous drain/close may have failed before termination.
                # Callback completion alone cannot release that ownership.
                worker.close(deadline=deadline)
                worker.settle(deadline=deadline)
            except Exception as error:
                failures.append(error)
            else:
                with self._lifecycle_guard:
                    if worker in self._retiring:
                        self._retiring.remove(worker)
        if failures:
            raise ExceptionGroup("worker authorization cleanup failed", failures)
