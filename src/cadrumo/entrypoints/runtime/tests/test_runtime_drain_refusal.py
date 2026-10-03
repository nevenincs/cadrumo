"""Absent worker receipts remain explicit after native containment attempts."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path
from threading import Event, Thread, current_thread
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.local_runtime.server import RuntimeListener, RuntimeTransportServer
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.application.runtime.approval_binding import RuntimeApprovalBinding
from cadrumo.application.runtime.approval_sessions import RuntimeApprovalSessions
from cadrumo.application.runtime.contracts import (
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeShutdownIncompleteError,
)
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.user_profile.automation_administration_service import AutomationAdministrationService
from cadrumo.application.user_profile.automation_approval_session import ApprovalSession
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.core.identity.digest import ContentDigest

from ..profile_connections import RuntimeProfileConnections
from ..profile_host import RuntimeProfileHost

pytestmark = [pytest.mark.hex_entrypoint]


class _FailedWorker:
    def __init__(self) -> None:
        self.contained = False
        self.settled = False

    def drain(self, *, deadline: float) -> None:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)

    def close(self, *, deadline: float) -> None:
        self.contained = True

    def settle(self, *, deadline: float) -> None:
        self.settled = True


class _EmptyApprovals:
    """Explicit absent approval phases for the worker/containment fault ports."""

    def close(self) -> int:
        return 0


class _Owner:
    def __init__(self, worker: _FailedWorker | None, *, construction_settled: bool = True) -> None:
        self.worker: _FailedWorker | None = worker
        self.construction_settled = construction_settled

    def begin_drain(self) -> _FailedWorker | None:
        return self.worker

    def settle(self, *, deadline: float) -> None:
        if self.worker is not None:
            self.worker.settle(deadline=deadline)

    def wait_construction(self, *, deadline: float) -> bool:
        if not self.construction_settled:
            Event().wait(timeout=max(0.0, deadline - time.monotonic()))
        return self.construction_settled


@pytest.mark.unit
def test_missing_receipt_is_reported_after_containment(tmp_path: Path) -> None:
    stop, profile_id = Event(), uuid4()
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="test-storage",
        runtime_boot_id=uuid4(),
        stop=stop,
    )
    worker = _FailedWorker()
    profiles._profiles[profile_id] = cast(
        "RuntimeProfileHost",
        SimpleNamespace(
            store=SimpleNamespace(binding=SimpleNamespace(profile_id=profile_id)),
            owner=_Owner(worker),
            approvals=_EmptyApprovals(),
        ),
    )

    result = profiles.drain(deadline=time.monotonic() + 1)

    assert stop.is_set()
    assert result.receipts == ()
    assert result.missing_receipts == (profile_id,)
    assert result.uncontained == result.unsettled == ()
    assert worker.contained and worker.settled


@pytest.mark.unit
def test_stalled_constructor_keeps_profile_owned_without_waiting_past_deadline(tmp_path: Path) -> None:
    profile_id = uuid4()
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="test-storage",
        runtime_boot_id=uuid4(),
        stop=Event(),
    )
    profiles._profiles[profile_id] = cast(
        "RuntimeProfileHost",
        SimpleNamespace(
            store=SimpleNamespace(binding=SimpleNamespace(profile_id=profile_id)),
            owner=_Owner(None, construction_settled=False),
            approvals=_EmptyApprovals(),
        ),
    )

    deadline = time.monotonic() + 0.05
    result = profiles.drain(deadline=deadline)

    assert time.monotonic() < deadline + 0.5
    assert result.uncontained == (profile_id,)
    assert profiles._profiles[profile_id].owner is not None


class _RetiringOwner(_Owner):
    """An explicit worker port preserves the real begin-drain transfer contract."""

    def __init__(self, worker: _FailedWorker) -> None:
        super().__init__(worker)
        self.retiring = worker
        self.begin_calls = 0

    @override
    def begin_drain(self) -> _FailedWorker | None:
        self.begin_calls += 1
        worker = self.worker
        self.worker = None
        return worker

    @override
    def settle(self, *, deadline: float) -> None:
        self.retiring.close(deadline=deadline)
        self.retiring.settle(deadline=deadline)


def _retained_profiles(
    tmp_path: Path, worker: _FailedWorker, *, approvals: _EmptyApprovals | None = None
) -> tuple[RuntimeProfileConnections, UUID, _RetiringOwner]:
    profile_id = uuid4()
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path, storage_identity="test-storage", runtime_boot_id=uuid4(), stop=Event()
    )
    owner = _RetiringOwner(worker)
    profiles._profiles[profile_id] = cast(
        "RuntimeProfileHost",
        SimpleNamespace(
            store=SimpleNamespace(binding=SimpleNamespace(profile_id=profile_id)),
            owner=owner,
            approvals=approvals if approvals is not None else _EmptyApprovals(),
        ),
    )
    return profiles, profile_id, owner


@pytest.mark.unit
@pytest.mark.parametrize("blocked", ["drain", "containment"])
def test_retry_keeps_original_worker_and_live_shutdown_thread(tmp_path: Path, blocked: str) -> None:
    entered, release = Event(), Event()
    attempts: list[Thread] = []
    request_attempts: list[Thread] = []

    class HeldWorker(_FailedWorker):
        @override
        def drain(self, *, deadline: float) -> None:
            request_attempts.append(current_thread())
            if blocked == "drain":
                attempts.append(current_thread())
                entered.set()
                assert release.wait(5)
            super().drain(deadline=deadline)

        @override
        def close(self, *, deadline: float) -> None:
            if blocked == "containment" and current_thread().name == "profile-worker-contain":
                attempts.append(current_thread())
                entered.set()
                assert release.wait(5)
            super().close(deadline=deadline)

    worker = HeldWorker()
    profiles, profile_id, owner = _retained_profiles(tmp_path, worker)
    try:
        first = profiles.drain(deadline=time.monotonic() + 0.05)
        assert entered.wait(2)
        assert profile_id in first.uncontained + first.unsettled
        assert not worker.settled
        original_thread = attempts[0]
        with pytest.raises(RuntimeShutdownIncompleteError):
            profiles.close()
        assert profile_id in profiles._profiles
        second = profiles.drain(deadline=time.monotonic() + 0.05)
        assert second.unsettled == (profile_id,)
        assert second.missing_receipts == (profile_id,)
        assert profile_id in profiles._profiles
        assert attempts == [original_thread]
        assert len(request_attempts) == 1
        assert not worker.settled
        assert owner.begin_calls == 1
    finally:
        release.set()
        for thread in attempts:
            thread.join(timeout=5)
            assert not thread.is_alive()
    completed = profiles.drain(deadline=time.monotonic() + 1)
    assert completed.uncontained == completed.unsettled == ()
    assert completed.missing_receipts == (profile_id,)
    assert profiles._profiles == {}
    assert profiles.drain(deadline=time.monotonic() + 1) == completed


@pytest.mark.unit
def test_retry_failed_terminal_containment_keeps_original_receipt_expectation(tmp_path: Path) -> None:
    class FailedCloseWorker(_FailedWorker):
        def __init__(self) -> None:
            super().__init__()
            self.drain_calls = 0
            self.close_calls = 0

        @override
        def drain(self, *, deadline: float) -> None:
            self.drain_calls += 1
            super().drain(deadline=deadline)

        @override
        def close(self, *, deadline: float) -> None:
            if self.contained:
                return
            self.close_calls += 1
            if self.close_calls <= 2:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
            super().close(deadline=deadline)

    worker = FailedCloseWorker()
    profiles, profile_id, owner = _retained_profiles(tmp_path, worker)
    first = profiles.drain(deadline=time.monotonic() + 1)
    assert profile_id in first.uncontained + first.unsettled
    result = profiles.drain(deadline=time.monotonic() + 1)
    if result.uncontained or result.unsettled:
        result = profiles.drain(deadline=time.monotonic() + 1)
    assert result.uncontained == result.unsettled == ()
    assert result.missing_receipts == (profile_id,)
    assert worker.drain_calls == owner.begin_calls == 1
    assert worker.contained and worker.settled
    assert profiles._profiles == {}


@pytest.mark.unit
def test_server_retry_retains_listener_until_original_profile_thread_settles(tmp_path: Path) -> None:
    """Actual host/handler retries preserve containment and original receipt truth."""
    entered, release = Event(), Event()
    requests: list[Thread] = []

    class HeldWorker(_FailedWorker):
        @override
        def drain(self, *, deadline: float) -> None:
            requests.append(current_thread())
            entered.set()
            assert release.wait(5)
            super().drain(deadline=deadline)

    class Listener:
        storage_identity = "a" * 64

        def __init__(self) -> None:
            self.claimed = False
            self.close_calls = 0

        def listen(self) -> None:
            self.claimed = True

        def close(self) -> None:
            self.close_calls += 1
            self.claimed = False

    worker = HeldWorker()
    profiles, profile_id, owner = _retained_profiles(tmp_path, worker)
    profiles.stop.set()
    listener = Listener()
    # The stopped host needs only real listener claim/release ports; no native
    # connection is fabricated or admitted by this portable ownership detector.
    server = RuntimeTransportServer(
        cast(RuntimeListener, listener), product_version="profile-drain-retry", stop=profiles.stop, profiles=profiles
    )
    server.DRAIN_SECONDS = 0.05
    try:
        with pytest.raises(RuntimeShutdownIncompleteError):
            server.serve()
        assert entered.wait(2)
        assert listener.claimed and listener.close_calls == 0
        assert not server.ready.is_set()
        original_thread = requests[0]
        with pytest.raises(RuntimeShutdownIncompleteError):
            server.retry_drain(deadline=time.monotonic() + 0.05)
        assert listener.claimed and listener.close_calls == 0
        assert profile_id in profiles._profiles and not worker.settled
        assert requests == [original_thread] and owner.begin_calls == 1

        release.set()
        original_thread.join(timeout=5)
        assert not original_thread.is_alive()
        with pytest.raises(RuntimeRefusalError) as missing_receipt:
            server.retry_drain(deadline=time.monotonic() + 1)
        assert missing_receipt.value.reason is RuntimeRefusalCode.UNAVAILABLE
        assert not listener.claimed and listener.close_calls == 1
        assert worker.contained and worker.settled and profiles._profiles == {}
        result = profiles.drain(deadline=time.monotonic() + 1)
        assert result.receipts == () and result.missing_receipts == (profile_id,)
        assert result.uncontained == result.unsettled == ()
        with pytest.raises(RuntimeRefusalError) as cached_refusal:
            server.retry_drain(deadline=time.monotonic() + 1)
        assert cached_refusal.value.reason is RuntimeRefusalCode.UNAVAILABLE
        assert listener.close_calls == 1 and requests == [original_thread] and owner.begin_calls == 1
        assert profiles.drain(deadline=time.monotonic() + 1) == result
    finally:
        release.set()
        for thread in requests:
            thread.join(timeout=5)
            assert not thread.is_alive()
        # This listener is an explicit close-only fault port with no native
        # ownership. Keep failed assertions from leaving its test state claimed.
        if listener.claimed:
            listener.close()


@pytest.mark.unit
def test_concurrent_drain_attempt_uses_its_remaining_deadline(tmp_path: Path) -> None:
    entered, release = Event(), Event()

    class HeldWorker(_FailedWorker):
        @override
        def drain(self, *, deadline: float) -> None:
            entered.set()
            assert release.wait(5)
            super().drain(deadline=deadline)

    profiles, profile_id, owner = _retained_profiles(tmp_path, HeldWorker())
    with ThreadPoolExecutor(max_workers=1) as executor:
        original = executor.submit(profiles.drain, deadline=time.monotonic() + 2)
        try:
            assert entered.wait(2)
            with pytest.raises(RuntimeShutdownIncompleteError):
                profiles.close()
            deadline = time.monotonic() + 0.05
            with pytest.raises(RuntimeShutdownIncompleteError):
                profiles.drain(deadline=deadline)
            assert time.monotonic() < deadline + 0.5
            assert profile_id in profiles._profiles and owner.begin_calls == 1
        finally:
            release.set()
            result = original.result(timeout=5)
    assert result.uncontained == result.unsettled == ()
    assert result.missing_receipts == (profile_id,)


@pytest.mark.unit
@pytest.mark.parametrize("failed_attempts", [1, 2])
def test_close_keeps_failed_host_owned_until_successful_retry(tmp_path: Path, failed_attempts: int) -> None:
    failure = RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)

    class ClosingHost:
        def __init__(self, failures: int) -> None:
            self.failures = failures
            self.attempts = 0

        def close(self) -> None:
            self.attempts += 1
            if self.attempts <= self.failures:
                raise failure

    profiles = RuntimeProfileConnections(
        storage_root=tmp_path, storage_identity="test-storage", runtime_boot_id=uuid4(), stop=Event()
    )
    failed_id, successful_id = uuid4(), uuid4()
    failed_host, successful_host = ClosingHost(failed_attempts), ClosingHost(0)
    profiles._profiles[failed_id] = cast(RuntimeProfileHost, failed_host)
    profiles._profiles[successful_id] = cast(RuntimeProfileHost, successful_host)

    for attempt in range(1, failed_attempts + 1):
        with pytest.raises(ExceptionGroup) as refused:
            profiles.close()
        assert refused.value.message == "runtime profile cleanup failed"
        assert refused.value.exceptions == (failure,)
        assert refused.value.exceptions[0] is failure
        assert profiles._profiles == {failed_id: failed_host}
        assert failed_host.attempts == attempt and successful_host.attempts == 1
        assert not profiles._admitting()
        assert profiles._connections == {} and profiles._logins == {}
        with pytest.raises(RuntimeRefusalError) as fenced:
            profiles.prepare_registry()
        assert fenced.value.reason is RuntimeRefusalCode.DRAINING

    profiles.close()
    assert profiles._profiles == {}
    assert failed_host.attempts == failed_attempts + 1
    assert successful_host.attempts == 1 and not profiles._admitting()
    profiles.close()
    assert failed_host.attempts == failed_attempts + 1 and successful_host.attempts == 1


@pytest.mark.integration
@pytest.mark.usefixtures("authority_operation")
@pytest.mark.parametrize("preparing", [False, True], ids=["idle", "callback"])
def test_drain_releases_real_prepared_approval_password_proof(tmp_path: Path, *, preparing: bool) -> None:
    """A canonical Argon2 preparation cannot outlive its drained profile host."""
    actual: list[ApprovalSession] = []
    entered, release = Event(), Event()
    failures: list[BaseException] = []
    callback: Thread | None = None

    class ObservedApproval(ApprovalSession):
        @override
        def prepare(self, password: SecretBytes) -> None:
            super().prepare(password)
            if preparing:
                entered.set()
                assert release.wait(10)

    class ObservedService(AutomationAdministrationService):
        @override
        def approval(self, request_id: UUID, *, review_digest: ContentDigest) -> ApprovalSession:
            session = ObservedApproval(self, request_id=request_id, review_digest=review_digest)
            actual.append(session)
            return session

    with administration_subject(tmp_path) as subject:
        receipt = subject.service.request(uuid4(), subject.proposal).receipt
        requester = subject.owner.requesting
        human = subject.owner.current.session
        assert human is not None
        identity = ProfileWorkerIdentity(
            worker_id=uuid4(), runtime_boot_id=requester.runtime_boot_id, binding=subject.store.binding
        )
        binding = RuntimeApprovalBinding(
            worker_id=identity.worker_id,
            runtime_boot_id=identity.runtime_boot_id,
            profile_binding=identity.binding,
            connection_id=requester.connection_id,
            session_id=human.session_id,
            operation_id="a" * 64,
            enrollment_request_id=receipt.request_id,
            review_digest=receipt.review_digest,
        )
        service = ObservedService(
            custody=subject.store, owner=subject.owner, issuer=subject.service.issuer, storage_root=subject.store.root
        )
        approvals = RuntimeApprovalSessions(worker=identity, service=lambda _binding: service, clock=lambda: 0.0)
        profiles = RuntimeProfileConnections(
            storage_root=subject.store.root,
            storage_identity="test-storage",
            runtime_boot_id=identity.runtime_boot_id,
            stop=Event(),
        )

        class CallbackOwner(_Owner):
            @override
            def settle(self, *, deadline: float) -> None:
                if callback is not None:
                    # The real preparing phase is still busy here. A close must
                    # fence later phases before waiting for callback settlement.
                    with pytest.raises(AutomationCustodyError) as refused:
                        approvals.commit_review(binding)
                    assert refused.value.reason is AutomationCustodyCode.CREDENTIAL_REJECTED
                    release.set()
                    callback.join(timeout=max(0.0, deadline - time.monotonic()))
                    assert not callback.is_alive()
                super().settle(deadline=deadline)

        owner = CallbackOwner(None)
        profiles._profiles[identity.binding.profile_id] = cast(
            RuntimeProfileHost, SimpleNamespace(store=subject.store, owner=owner, approvals=approvals)
        )
        try:
            if preparing:

                def prepare() -> None:
                    try:
                        approvals.prepare(binding, SecretBytes(PROFILE_INPUT.encode()))
                    except BaseException as error:
                        failures.append(error)

                context = copy_context()
                callback = Thread(target=lambda: context.run(prepare))
                callback.start()
                assert entered.wait(10)
            else:
                approvals.prepare(binding, SecretBytes(PROFILE_INPUT.encode()))
            session = actual[0]
            # Inspect real preparation output, without constructing or assigning
            # the password authorization/DEK that the owning service creates.
            assert session._proof is not None and session._dek is not None
            result = profiles.drain(deadline=time.monotonic() + 1)
            assert result.uncontained == result.unsettled == ()
            assert profiles._profiles == {}
            assert session._proof is None and session._dek is None
            with pytest.raises(ValueError, match="closed"):
                session.commit_review()
            assert failures == []
        finally:
            release.set()
            if callback is not None:
                callback.join(timeout=10)
                assert not callback.is_alive()
            approvals.close()


@pytest.mark.unit
@pytest.mark.parametrize("failed_phase", [1, 2], ids=["before-worker-drain", "after-callback-settlement"])
def test_approval_release_failure_retains_original_host_for_retry(tmp_path: Path, failed_phase: int) -> None:
    class FailedApprovals(_EmptyApprovals):
        def __init__(self) -> None:
            self.attempts = 0

        @override
        def close(self) -> int:
            self.attempts += 1
            if self.attempts == failed_phase:
                raise RuntimeError("approval release failed")
            return super().close()

    approvals, worker = FailedApprovals(), _FailedWorker()
    profiles, profile_id, owner = _retained_profiles(tmp_path, worker, approvals=approvals)
    host = profiles._profiles[profile_id]
    failed = profiles.drain(deadline=time.monotonic() + 1)
    assert failed.unsettled == (profile_id,)
    assert failed.uncontained == () and failed.missing_receipts == (profile_id,)
    assert profiles._profiles[profile_id] is host
    assert worker.contained and worker.settled
    completed = profiles.drain(deadline=time.monotonic() + 1)
    assert completed.uncontained == completed.unsettled == ()
    assert completed.missing_receipts == (profile_id,)
    assert profiles._profiles == {} and owner.begin_calls == 1
    attempts = approvals.attempts
    assert profiles.drain(deadline=time.monotonic() + 1) == completed
    assert approvals.attempts == attempts
