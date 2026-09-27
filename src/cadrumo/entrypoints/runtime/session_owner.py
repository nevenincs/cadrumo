"""Compose application session admission with real immutable worker custody."""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from threading import RLock
from uuid import UUID

from ...adapters.local_runtime.profile_worker import ProfileWorkerProcess
from ...application.runtime.contracts import RuntimeRefusalError
from ...application.runtime.profile_worker import ProfileWorkerIdentity
from ...application.runtime.worker_authorization import WorkerAuthorizationOwner
from ...application.user_profile.access_contracts import AccessSession
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.login_session import ProfileLoginOutcome
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
        human_secret: Callable[[UUID], AbstractContextManager[tuple[bytearray, str]]],
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
        if self._lost:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        try:
            if self._worker is None:
                self._worker = ProfileWorkerProcess(
                    self.identity, storage_root=self.root, authorization=self._authorization
                )
            yield self._worker
        except RuntimeRefusalError:
            self.close()
            raise

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
        """Borrow a protected password channel and native originating-login identity."""
        with self._human_secret(connection_id) as (password, login_id):
            try:
                with self._custody() as worker, worker.authenticate_human(password) as outcome:
                    yield outcome, login_id
            finally:
                password[:] = bytes(len(password))

    def bind_human(self, session: AccessSession) -> None:
        """Commit the exact password candidate only after application admission."""
        with self._custody() as worker:
            worker.bind_human(session)

    def retire(self, session_id: UUID) -> None:
        """Release an admitted lineage; retirement never starts a replacement worker."""
        if self._worker is not None:
            with self._custody() as worker:
                worker.retire(session_id)

    def close(self) -> None:
        """Fence old leases before terminating all owned profile processes."""
        with self._guard:
            self._lost = True
            worker, self._worker = self._worker, None
            if worker is not None:
                self._retiring.append(worker)
                worker.close()

    def settle(self) -> None:
        """Finish callback threads outside the guard those threads may be acquiring."""
        with self._guard:
            retiring, self._retiring = self._retiring, []
        failures: list[Exception] = []
        for worker in retiring:
            try:
                worker.settle()
            except Exception as error:
                failures.append(error)
        if failures:
            raise ExceptionGroup("worker authorization cleanup failed", failures)
