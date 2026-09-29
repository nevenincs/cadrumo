"""Compose application session admission with real immutable worker custody."""

from __future__ import annotations

import time
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from threading import Event, RLock
from uuid import UUID

from ...adapters.local_runtime.profile_worker import ProfileWorkerProcess
from ...application.runtime.contracts import RuntimeRefusalError
from ...application.runtime.profile_access import RuntimeHumanProof
from ...application.runtime.profile_worker import ProfileWorkerIdentity
from ...application.runtime.worker_authorization import WorkerAuthorizationOwner
from ...application.user_profile.access_contracts import AccessSession
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.login_session import ProfileHumanLoginReceipt, ProfileLoginOutcome
from ...application.user_profile.session_authority import SessionAuthorityFacts


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
    ) -> None:
        """Share the profile denial guard with the existing authority and administration."""
        self.identity, self.root = identity, storage_root
        self._observe, self._human_secret, self._guard = observe, human_secret, guard
        self._worker: ProfileWorkerProcess | None = None
        self._lost = False
        self._authorization = authorization
        self._retiring: list[ProfileWorkerProcess] = []
        self._lifecycle_guard = RLock()
        self._stopping = Event()
        self._construction_done = Event()
        self._construction_done.set()
        self._construction_failure = False
        self._persist_human_receipt = False
        self._human_receipts: dict[UUID, ProfileHumanLoginReceipt] = {}

    @contextmanager
    def admission_guard(self) -> Generator[None]:
        """Serialize admission, worker changes and durable denial under one owner."""
        with self._guard:
            yield

    def facts(self, connection_id: UUID) -> SessionAuthorityFacts:
        """Reobserve native facts without allowing an old lease to survive worker loss."""
        if self._lost:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        if self._worker is not None:
            try:
                self._worker.require_alive()
            except RuntimeRefusalError:
                self.close()
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE) from None
        facts = self._observe(connection_id)
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

    @contextmanager
    def _custody(self) -> Generator[ProfileWorkerProcess]:
        constructing = False
        try:
            with self._lifecycle_guard:
                if self._lost or self._stopping.is_set():
                    raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
                worker = self._worker
                if worker is None:
                    self._construction_done.clear()
                    constructing = True
            if constructing:
                candidate = ProfileWorkerProcess(
                    self.identity, storage_root=self.root, authorization=self._authorization
                )
                with self._lifecycle_guard:
                    if self._stopping.is_set():
                        self._retiring.append(candidate)
                        stopped = True
                    else:
                        self._worker = candidate
                        worker = candidate
                        stopped = False
                if stopped:
                    candidate.close()
                    raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
            if worker is None:
                raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
            yield worker
        except RuntimeRefusalError:
            if constructing and self._stopping.is_set():
                self._construction_failure = True
            self.close()
            raise
        except BaseException:
            if constructing and self._stopping.is_set():
                self._construction_failure = True
            raise
        finally:
            if constructing:
                self._construction_done.set()

    def activate(self, session: AccessSession, dek: bytearray) -> None:
        """Deliver authenticated API custody without selecting a human profile."""
        with self._custody() as worker:
            worker.install(session, dek)

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
        with self._human_secret(connection_id) as proof:
            try:
                self._persist_human_receipt = proof.persist_receipt
                with self._custody() as worker, worker.authenticate_human(proof.secret, method=proof.method) as outcome:
                    yield outcome, proof.originating_login_id
            finally:
                self._persist_human_receipt = False
                proof.secret[:] = bytes(len(proof.secret))

    def bind_human(self, session: AccessSession) -> None:
        """Commit the exact human candidate only after application admission."""
        with self._custody() as worker:
            self._human_receipts[session.session_id] = worker.bind_human(
                session, persist_receipt=self._persist_human_receipt
            )

    def take_human_login_receipt(self, session_id: UUID) -> ProfileHumanLoginReceipt | None:
        """Consume the nonsecret acknowledgement after exact-session admission."""
        return self._human_receipts.pop(session_id, None)

    def retire(self, session_id: UUID) -> None:
        """Release an admitted lineage; retirement never starts a replacement worker."""
        self._human_receipts.pop(session_id, None)
        if self._worker is not None:
            with self._custody() as worker:
                worker.retire(session_id)

    def close(self) -> None:
        """Fence old leases before terminating all owned profile processes."""
        with self._lifecycle_guard:
            self._stopping.set()
            self._lost = True
            self._human_receipts.clear()
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
