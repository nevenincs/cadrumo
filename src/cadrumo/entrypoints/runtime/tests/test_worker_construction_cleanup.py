"""Retain an unreturned native owner before projecting a public refusal."""

from __future__ import annotations

import asyncio
import time
from collections import Counter
from collections.abc import Generator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager, suppress
from pathlib import Path
from threading import Event, RLock, Thread
from types import SimpleNamespace
from typing import Protocol, cast, override
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime import profile_worker
from cadrumo.adapters.local_runtime.profile_worker import ProfileWorkerProcess
from cadrumo.adapters.local_runtime.tests.test_windows_process_cleanup import native  # noqa: F401
from cadrumo.adapters.local_runtime.windows_process import unreturned_windows_process_scope
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimePeer, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeHumanProof, RuntimeProfileLogin
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.runtime.transport import RuntimeConnectionContext
from cadrumo.application.user_profile.access_contracts import (
    AccessEvaluationContext,
    AccessScope,
    Availability,
    ProfileAccessBinding,
    ProfileAccessState,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError
from cadrumo.application.user_profile.session_authority_contracts import SessionAuthorityFacts
from cadrumo.core.time.clock import now

from .. import session_owner
from ..profile_connections import RuntimeProfileConnections
from ..session_owner import ProfileWorkerSessionOwner

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _NativeScopeFaults(Protocol):
    setup_error: BaseException | None
    close_failures: dict[int, int]
    attempts: Counter[int]
    closed: Counter[int]
    terminations: int


def test_scope_constructor_owner_survives_public_refusal_and_failed_settlement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    port = cast(_NativeScopeFaults, request.getfixturevalue("native"))
    owner = _owner(tmp_path)
    primary = RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
    port.setup_error = primary
    port.close_failures = {7: 2}
    monkeypatch.setattr(profile_worker, "sys", SimpleNamespace(platform="win32"))
    endpoints: list[SimpleNamespace] = []

    def unopened_endpoint(**kwargs: object) -> SimpleNamespace:
        endpoint = SimpleNamespace(close=lambda: None)
        endpoints.append(endpoint)
        return endpoint

    monkeypatch.setattr(profile_worker, "worker_endpoint", unopened_endpoint)
    connections = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="a" * 64,
        runtime_boot_id=owner.identity.runtime_boot_id,
        stop=Event(),
    )
    peer = RuntimePeer(os_owner_id="synthetic-owner", process_id=1)
    context = RuntimeConnectionContext(uuid4(), owner.identity.runtime_boot_id, peer)

    class Channel:
        def __init__(self) -> None:
            self.peer = peer

        def read_exact(self, count: int, *, deadline: float) -> bytes:
            raise AssertionError("failed construction must not read a secret")

        def read_ready(self) -> bool:
            return False

        def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
            raise AssertionError("failed construction must not write a secret")

        def close(self) -> None:
            raise AssertionError("refusal mapping must not release the server owner")

    def failed_login(*args: object) -> None:
        # Exercise the real constructor and session owner before the existing
        # wire mapper reduces this private exception to a bounded refusal.
        with owner.admission_guard(), owner._custody():
            raise AssertionError("failed scope construction must not admit custody")

    monkeypatch.setattr(connections, "_login", failed_login)
    reply = connections.handle(
        context,
        Channel(),
        RuntimeProfileLogin(
            request_id=uuid4(),
            profile_id=owner.identity.binding.profile_id,
            method="password",
            frontend=OperationFrontendProjection.CLI,
        ),
    )
    assert isinstance(reply, RuntimeAccessRefusal) and reply.code is RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE
    scope = unreturned_windows_process_scope(primary)
    assert scope is not None
    assert owner.lost and owner._worker is None and len(owner._retiring) == 1
    candidate = owner._retiring[0]
    assert candidate._scope is scope and candidate.stopping
    assert port.terminations == port.attempts[7] == 1 and not port.closed
    assert owner.wait_construction(deadline=time.monotonic() + 1)
    with pytest.raises(ExceptionGroup):
        owner.settle()
    assert owner._retiring == [candidate] and port.attempts[7] == 2 and not port.closed
    owner.settle()
    assert not owner._retiring and port.closed == Counter({7: 1})
    assert port.terminations == 1 and port.attempts[7] == 3
    owner.close()
    owner.settle()
    assert port.attempts[7] == 3


def test_concurrent_custody_cannot_construct_a_second_worker_while_first_launch_is_pending(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    owner = _owner(tmp_path)
    candidate = _Candidate(owner.identity, owner._guard, failures=0)
    entered, release = Event(), Event()
    constructed: list[ProfileWorkerIdentity] = []

    def paused_constructor(identity: ProfileWorkerIdentity, **kwargs: object) -> ProfileWorkerProcess:
        constructed.append(identity)
        entered.set()
        assert release.wait(10)
        return candidate

    def borrow() -> ProfileWorkerProcess:
        with owner._custody() as worker:
            return worker

    def conflicting_borrow() -> None:
        with owner.admission_guard(), pytest.raises(AutomationCustodyError), owner._custody():
            raise AssertionError("a pending constructor must not publish a second worker")

    monkeypatch.setattr(session_owner, "ProfileWorkerProcess", paused_constructor)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(borrow)
        pending: list[Future[None]] = []
        try:
            assert entered.wait(10)
            second = executor.submit(conflicting_borrow)
            pending.append(second)
            second.result(timeout=3)
            assert not release.is_set() and not first.done()
        finally:
            release.set()
            first.result(timeout=10)
            for future in pending:
                future.result(timeout=10)
    assert first.result(timeout=0) is candidate
    assert constructed == [owner.identity]
    assert owner._worker is candidate and not owner._retiring
    assert owner.wait_construction(deadline=time.monotonic() + 1)
    owner.close()
    owner.settle()


def test_busy_native_observation_does_not_retire_the_original_session_owner(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    connection_id = uuid4()
    facts = SessionAuthorityFacts(
        ProfileAccessState(
            binding=owner.identity.binding,
            lock_generation=0,
            globally_locked=False,
            automation_enabled=False,
            scope=AccessScope(
                operations=frozenset(),
                actions=frozenset(),
                disclosures=frozenset(),
                periods=frozenset(),
                allow_period_independent=False,
                allow_delegation=False,
            ),
            storage=Availability.AVAILABLE,
            automation_custody=Availability.UNAVAILABLE,
        ),
        AccessEvaluationContext(
            now=now(),
            monotonic_now=time.monotonic(),
            clock_rollback_detected=False,
            runtime_boot_id=owner.identity.runtime_boot_id,
            connection_id=connection_id,
            authenticated_client_id=uuid4(),
            login_contexts=(),
            private_work_available=True,
        ),
    )
    owner._observe = lambda connected: facts

    class ObservedWorker(_Candidate):
        busy = True

        @override
        def require_alive(self) -> None:
            if self.busy:
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)

    worker = ObservedWorker(owner.identity, owner._guard, failures=0)
    owner._worker = worker
    with pytest.raises(AutomationCustodyError):
        owner.facts(connection_id)
    assert not owner.lost and owner._worker is worker and not owner._retiring
    assert worker.close_calls == 0
    worker.busy = False
    assert owner.facts(connection_id) is facts
    assert worker.close_calls == 0
    owner.close()
    owner.settle()


class _Candidate(ProfileWorkerProcess):
    """Fault only the native owner's close and callback-settlement boundary."""

    def __init__(self, identity: ProfileWorkerIdentity, guard: RLock, *, failures: int) -> None:
        self.identity = identity
        self.guard = guard
        self.failures = failures
        self.close_calls = 0
        self.settle_calls = 0

    @override
    def close(self, *, deadline: float | None = None) -> None:
        self.close_calls += 1
        if self.close_calls <= self.failures:
            raise OSError("synthetic native containment failure")

    @override
    def settle(self, *, deadline: float | None = None) -> None:
        acquired = Event()

        def callback() -> None:
            if self.guard.acquire(timeout=0.05):
                try:
                    acquired.set()
                finally:
                    self.guard.release()

        thread = Thread(target=callback)
        thread.start()
        thread.join(timeout=0.2)
        assert not thread.is_alive() and acquired.is_set(), "callback settlement ran inside the admission guard"
        self.settle_calls += 1


@pytest.mark.parametrize("stopping", [False, True])
def test_api_preparation_queue_timeout_preserves_only_the_nonstopping_original_worker(
    tmp_path: Path, stopping: bool
) -> None:
    owner = _owner(tmp_path)
    connection_id = uuid4()
    primary = RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)

    class QueuedWorker(_Candidate):
        """Represent the adapter's exact pre-dispatch versus fenced timeout outcome."""

        queue_timeout = True

        @property
        @override
        def stopping(self) -> bool:
            return stopping

        @override
        def prepare_api_admission(self, *, deadline: float) -> None:
            assert deadline > time.monotonic()
            if self.queue_timeout:
                raise primary

        @override
        def require_alive(self) -> None:
            if self.stopping:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            assert self.close_calls == 0

    worker = QueuedWorker(owner.identity, owner._guard, failures=0)
    owner._worker = worker
    try:
        with pytest.raises(RuntimeRefusalError) as caught, owner.prepare_api_admission(connection_id):
            raise AssertionError("a queued or fenced preparation must not lend an admission candidate")
        assert caught.value is primary
        if stopping:
            assert owner.lost and owner._worker is None and owner._retiring == [worker]
            assert worker.close_calls == 1
            with pytest.raises(AutomationCustodyError), owner.prepare_api_admission(connection_id):
                raise AssertionError("a fenced worker must never become a fresh preparation candidate")
            assert worker.close_calls == 1
        else:
            assert not owner.lost and owner._worker is worker and not owner._retiring
            assert worker.close_calls == 0
            worker.require_alive()
            worker.queue_timeout = False
            with owner.prepare_api_admission(connection_id) as deadline:
                assert deadline > time.monotonic()
                assert owner._worker is worker and not owner.lost
                worker.require_alive()
            assert worker.close_calls == 0 and not owner._retiring
    finally:
        owner.close()
        owner.settle()


def _owner(root: Path) -> ProfileWorkerSessionOwner:
    identity = ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )

    def unused_observe(connection_id: UUID) -> SessionAuthorityFacts:
        raise AssertionError("construction cleanup must not observe or admit a session")

    @contextmanager
    def unused_secret(connection_id: UUID) -> Generator[RuntimeHumanProof]:
        raise AssertionError("construction cleanup must not request a secret")
        yield

    return ProfileWorkerSessionOwner(
        identity, storage_root=root, observe=unused_observe, human_secret=unused_secret, guard=RLock()
    )


@pytest.mark.parametrize("kind", ["refusal", "unexpected", "cancellation"])
@pytest.mark.parametrize("failures", [0, 2])
def test_unreturned_candidate_survives_exact_primary_and_public_refusal_until_settled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kind: str, failures: int
) -> None:
    owner = _owner(tmp_path)
    candidate = _Candidate(owner.identity, owner._guard, failures=failures)
    primary = (
        RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        if kind == "refusal"
        else asyncio.CancelledError("synthetic interrupted construction")
        if kind == "cancellation"
        else OSError("synthetic interrupted construction")
    )

    def failed_native_constructor(*args: object, **kwargs: object) -> ProfileWorkerProcess:
        # Model the actual constructor's immediate containment attempt and its
        # native candidate handoff, without replacing the session owner logic.
        with suppress(OSError):
            candidate.close()
        primary.__dict__["_profile_worker_candidate"] = candidate
        raise primary

    monkeypatch.setattr(session_owner, "ProfileWorkerProcess", failed_native_constructor)
    with owner.admission_guard(), pytest.raises(type(primary)) as caught, owner._custody():
        raise AssertionError("a failed constructor must not yield")
    assert caught.value is primary
    assert owner.lost and owner._worker is None
    assert owner._retiring == [candidate]
    assert candidate.close_calls == 1 and candidate.settle_calls == 0
    assert owner.wait_construction(deadline=time.monotonic() + 1)
    if kind == "refusal":
        connections = RuntimeProfileConnections(
            storage_root=tmp_path,
            storage_identity="a" * 64,
            runtime_boot_id=owner.identity.runtime_boot_id,
            stop=Event(),
        )
        peer = RuntimePeer(os_owner_id="synthetic-owner", process_id=1)
        context = RuntimeConnectionContext(uuid4(), owner.identity.runtime_boot_id, peer)

        class Channel:
            def __init__(self) -> None:
                self.peer = peer

            def read_exact(self, count: int, *, deadline: float) -> bytes:
                raise AssertionError("refusal mapping must not read a secret")

            def read_ready(self) -> bool:
                return False

            def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
                raise AssertionError("refusal mapping must not write a secret")

            def close(self) -> None:
                raise AssertionError("refusal mapping must not release the profile owner")

        def refused_login(*args: object) -> None:
            raise primary

        monkeypatch.setattr(connections, "_login", refused_login)
        reply = connections.handle(
            context,
            Channel(),
            RuntimeProfileLogin(
                request_id=uuid4(),
                profile_id=owner.identity.binding.profile_id,
                method="password",
                frontend=OperationFrontendProjection.CLI,
            ),
        )
        assert isinstance(reply, RuntimeAccessRefusal) and reply.code == RuntimeRefusalCode.PEER_UNTRUSTED
        assert owner._retiring == [candidate]
    if failures:
        with pytest.raises(ExceptionGroup):
            owner.settle()
        assert owner._retiring == [candidate] and candidate.settle_calls == 0
    owner.settle()
    assert not owner._retiring and candidate.settle_calls == 1
    calls = candidate.close_calls
    owner.close()
    owner.settle()
    assert candidate.close_calls == calls and candidate.settle_calls == 1


@pytest.mark.parametrize("failures", [0, 2])
def test_stop_racing_returned_candidate_keeps_recoverable_construction_settlement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failures: int
) -> None:
    owner = _owner(tmp_path)
    candidate = _Candidate(owner.identity, owner._guard, failures=failures)

    def late_native_constructor(*args: object, **kwargs: object) -> ProfileWorkerProcess:
        owner._stopping.set()
        return candidate

    monkeypatch.setattr(session_owner, "ProfileWorkerProcess", late_native_constructor)
    with owner.admission_guard(), pytest.raises(OSError if failures else AutomationCustodyError), owner._custody():
        raise AssertionError("a candidate returned after the drain fence must not admit custody")
    assert owner.lost and owner._worker is None
    assert owner._retiring == [candidate]
    assert candidate.close_calls == 1 and candidate.settle_calls == 0
    assert owner.wait_construction(deadline=time.monotonic() + 1)
    if failures:
        with pytest.raises(ExceptionGroup):
            owner.settle()
        assert owner._retiring == [candidate]
    owner.settle()
    assert not owner._retiring and candidate.settle_calls == 1
    assert owner.wait_construction(deadline=time.monotonic() + 1)


def test_published_worker_drain_preserves_recoverable_construction_after_body_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    owner = _owner(tmp_path)
    candidate = _Candidate(owner.identity, owner._guard, failures=0)
    primary = OSError("synthetic failure after published worker drain")

    def native_constructor(*args: object, **kwargs: object) -> ProfileWorkerProcess:
        return candidate

    monkeypatch.setattr(session_owner, "ProfileWorkerProcess", native_constructor)
    with owner.admission_guard(), pytest.raises(OSError) as caught, owner._custody() as worker:
        assert worker is candidate
        assert owner.begin_drain() is candidate
        raise primary
    assert caught.value is primary
    assert owner.lost and owner._worker is None
    assert owner._retiring == [candidate]
    assert owner.wait_construction(deadline=time.monotonic() + 1)
    owner.settle()
    assert candidate.close_calls == candidate.settle_calls == 1
    assert not owner._retiring
    assert owner.wait_construction(deadline=time.monotonic() + 1)


class _RetryingWorker(ProfileWorkerProcess):
    """Only the close/settle boundary of an already published worker is used."""

    def __init__(self) -> None:
        self.close_calls = 0
        self.settle_calls = 0
        self.fail_close = True

    @override
    def close(self, *, deadline: float | None = None) -> None:
        self.close_calls += 1
        if self.fail_close:
            raise RuntimeError("synthetic containment failure")

    @override
    def settle(self, *, deadline: float | None = None) -> None:
        self.settle_calls += 1


def test_failed_worker_containment_is_retried_until_settled(tmp_path: Path) -> None:
    """A failed close keeps the exact worker owned across later close attempts."""
    identity = ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )

    def unused_observe(connection_id: UUID) -> SessionAuthorityFacts:
        raise AssertionError("close must not reobserve authority")

    @contextmanager
    def unused_secret(connection_id: UUID) -> Generator[RuntimeHumanProof]:
        raise AssertionError("close must not request a secret")
        yield  # pragma: no cover

    owner = ProfileWorkerSessionOwner(
        identity,
        storage_root=tmp_path,
        observe=unused_observe,
        human_secret=unused_secret,
        guard=RLock(),
    )
    worker = _RetryingWorker()
    owner._worker = worker

    with pytest.raises(ExceptionGroup, match="worker containment failed"):
        owner.close()
    assert worker.close_calls == 1 and owner.lost
    with pytest.raises(ExceptionGroup, match="worker authorization cleanup failed"):
        owner.settle()
    assert worker.close_calls == 2 and worker.settle_calls == 0
    with pytest.raises(ExceptionGroup, match="worker containment failed"):
        owner.close()
    assert worker.close_calls == 3
    worker.fail_close = False
    owner.settle()
    assert worker.close_calls == 4 and worker.settle_calls == 1
    owner.close()
    owner.settle()
    assert worker.close_calls == 4 and worker.settle_calls == 1
