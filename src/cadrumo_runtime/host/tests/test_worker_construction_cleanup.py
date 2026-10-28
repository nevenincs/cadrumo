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

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AccessEvaluationContext,
    ProfileAccessBinding,
    ProfileAccessState,
)
from cadrumo.application.user_profile.proof_cancellation import ProfileProofCancellation
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_vocabulary import AccessScope, Availability
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.contracts import ChannelWake, Peer, RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import TimeoutDeadline
from cadrumo_client.contracts.profile_access import AccessRefusal, HumanProof, ProfileLogin
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.tests.test_windows_process_cleanup import native  # noqa: F401
from cadrumo_client.transport.windows_process import unreturned_windows_process_scope

from ...adapters import profile_worker
from ...adapters.profile_worker import ProfileWorkerProcess
from ...application.session_authority_contracts import SessionAuthorityFacts
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
    primary = RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
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
    peer = Peer(os_owner_id="synthetic-owner", process_id=1)
    context = ConnectionContext(uuid4(), owner.identity.runtime_boot_id, peer)

    class Channel:
        def __init__(self) -> None:
            self.peer = peer

        def read_exact(self, count: int, *, deadline: float) -> bytes:
            raise AssertionError("failed construction must not read a secret")

        def read_ready(self) -> bool:
            return False

        def wait_readable(self, *wakes: ChannelWake) -> bool:
            while not self.read_ready():
                if any(wake.is_set() for wake in wakes):
                    return False
                time.sleep(0.01)
            return True

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
        ProfileLogin(
            request_id=uuid4(),
            profile_id=owner.identity.binding.profile_id,
            method="password",
            frontend=OperationFrontendProjection.CLI,
        ),
    )
    assert isinstance(reply, AccessRefusal) and reply.code is RefusalCode.CONTAINMENT_UNAVAILABLE
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
    guard = RLock()
    owner = _owner(tmp_path, guard)
    candidate = _Candidate(owner.identity, guard, failures=0)
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


def test_a_sign_in_meeting_a_pending_construction_uses_the_worker_it_builds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A sign-in that arrives while its watch is starting the worker waits for that worker, never a second one."""
    guard = RLock()
    owner = _owner(tmp_path, guard)
    candidate = _Candidate(owner.identity, guard, failures=0)
    entered, release = Event(), Event()
    constructed: list[ProfileWorkerIdentity] = []

    def paused_constructor(identity: ProfileWorkerIdentity, **kwargs: object) -> ProfileWorkerProcess:
        constructed.append(identity)
        entered.set()
        assert release.wait(10)
        return candidate

    def sign_in() -> ProfileWorkerProcess:
        with owner._custody(await_construction=True) as worker:
            return worker

    monkeypatch.setattr(session_owner, "ProfileWorkerProcess", paused_constructor)
    with ThreadPoolExecutor(max_workers=2) as executor:
        prepared = executor.submit(owner.prepare)
        assert entered.wait(10)
        signed_in = executor.submit(sign_in)
        time.sleep(0.2)
        assert not signed_in.done(), "the sign-in must wait for the worker being built, not be refused"
        release.set()
        prepared.result(timeout=10)
        assert signed_in.result(timeout=10) is candidate
    assert constructed == [owner.identity]
    owner.close()
    owner.settle()


def test_cancelled_proof_leaves_shared_construction_and_its_next_joiner_untouched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    guard = RLock()
    owner = _owner(tmp_path, guard)
    candidate = _Candidate(owner.identity, guard, failures=0)
    entered, release, joined = Event(), Event(), Event()
    cancellation = ProfileProofCancellation()
    deadline = time.monotonic() + 100
    secret = bytearray(b"owned-pending-construction-proof")
    constructed = []
    wait = owner._construction_changed.wait

    def paused_constructor(identity: ProfileWorkerIdentity, **kwargs: object) -> ProfileWorkerProcess:
        constructed.append(identity)
        entered.set()
        assert release.wait(10), "test did not release the shared key-free constructor"
        return candidate

    @contextmanager
    def proof(connection_id: UUID) -> Generator[HumanProof]:
        yield HumanProof(
            method="password",
            secret=secret,
            originating_login_id="synthetic-login",
            timeout_deadline=deadline,
            attempt_id=uuid4(),
            cancellation=cancellation,
        )

    def waiting(*, timeout: float | None = None) -> bool:
        joined.set()
        return wait(timeout=timeout)

    def authenticate() -> None:
        with owner.authenticate_human(uuid4()):
            pytest.fail("a cancelled construction join must not dispatch a protected proof")

    def next_join() -> ProfileWorkerProcess:
        with owner._custody(await_construction=True, timeout=TimeoutDeadline(deadline)) as worker:
            return worker

    monkeypatch.setattr(session_owner, "ProfileWorkerProcess", paused_constructor)
    monkeypatch.setattr(owner, "_human_secret", proof)
    monkeypatch.setattr(owner._construction_changed, "wait", waiting)
    with ThreadPoolExecutor(max_workers=3) as pool:
        prepared = pool.submit(owner.prepare)
        try:
            assert entered.wait(3)
            # Any restarted orchestration policy would extend the owner's
            # original absolute deadline and is forbidden for this join.
            monkeypatch.setattr(
                session_owner,
                "DEFAULT_TIMEOUT_POLICY",
                SimpleNamespace(deadline=lambda: pytest.fail("construction join restarted the owner's timeout")),
            )
            pending = pool.submit(authenticate)
            assert joined.wait(3), "the proof did not join the shared constructor"
            cancellation.cancel()
            with pytest.raises(AutomationCustodyError) as refused:
                pending.result(timeout=3)
            assert refused.value.reason is AutomationCustodyCode.REQUESTER_DISCONNECTED
            assert secret == bytearray(len(secret))
            assert owner._human_slot_owner is None
            assert not owner.lost and not owner._stopping.is_set()
            assert not prepared.done() and not owner._construction_done.is_set()
            assert candidate.close_calls == 0 and not owner._retiring
            joined.clear()
            following = pool.submit(next_join)
            assert joined.wait(3), "the next attempt could not join the retained construction"
            assert not following.done()
            release.set()
            prepared.result(timeout=3)
            assert following.result(timeout=3) is candidate
            assert constructed == [owner.identity]
        finally:
            release.set()
            prepared.result(timeout=3)
    owner.close()
    owner.settle()


def test_busy_native_observation_does_not_retire_the_original_session_owner(tmp_path: Path) -> None:
    guard = RLock()
    owner = _owner(tmp_path, guard)
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
                raise RefusalError(RefusalCode.TIMEOUT)

    worker = ObservedWorker(owner.identity, guard, failures=0)
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
    guard = RLock()
    owner = _owner(tmp_path, guard)
    connection_id = uuid4()
    primary = RefusalError(RefusalCode.TIMEOUT)

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
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            assert self.close_calls == 0

    worker = QueuedWorker(owner.identity, guard, failures=0)
    owner._worker = worker
    try:
        with pytest.raises(RefusalError) as caught, owner.prepare_api_admission(connection_id):
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


@pytest.mark.parametrize("outcome", ["fenced", "containment_failure", "queue_timeout"])
def test_retiring_into_a_fenced_worker_completes_once_the_worker_is_contained(tmp_path: Path, outcome: str) -> None:
    guard = RLock()
    owner = _owner(tmp_path, guard)
    session_id = uuid4()

    class FencedWorker(_Candidate):
        """Answer retirement as the adapter does after an earlier exchange failed."""

        @property
        @override
        def stopping(self) -> bool:
            return outcome != "queue_timeout"

        @override
        def retire(self, session_id: UUID) -> None:
            if outcome == "queue_timeout":
                raise RefusalError(RefusalCode.TIMEOUT)
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)

    worker = FencedWorker(owner.identity, guard, failures=1 if outcome == "containment_failure" else 0)
    owner._worker = worker
    try:
        if outcome == "fenced":
            owner.retire(session_id)
            assert owner.lost and owner._worker is None and owner._retiring == [worker]
            assert worker.close_calls == 1
            # Later lineages of the contained worker retire without a new worker.
            owner.retire(uuid4())
            assert worker.close_calls == 1
        elif outcome == "containment_failure":
            with pytest.raises(ExceptionGroup, match="worker containment failed"):
                owner.retire(session_id)
            assert owner.lost and owner._retiring == [worker]
        else:
            with pytest.raises(RefusalError) as caught:
                owner.retire(session_id)
            assert caught.value.reason is RefusalCode.TIMEOUT
            assert not owner.lost and owner._worker is worker and worker.close_calls == 0
    finally:
        owner.close()
        owner.settle()


def _owner(root: Path, guard: RLock | None = None) -> ProfileWorkerSessionOwner:
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
    def unused_secret(connection_id: UUID) -> Generator[HumanProof]:
        raise AssertionError("construction cleanup must not request a secret")
        yield

    return ProfileWorkerSessionOwner(
        identity, storage_root=root, observe=unused_observe, human_secret=unused_secret, guard=guard or RLock()
    )


@pytest.mark.parametrize("kind", ["refusal", "unexpected", "cancellation"])
@pytest.mark.parametrize("failures", [0, 2])
def test_unreturned_candidate_survives_exact_primary_and_public_refusal_until_settled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kind: str, failures: int
) -> None:
    guard = RLock()
    owner = _owner(tmp_path, guard)
    candidate = _Candidate(owner.identity, guard, failures=failures)
    primary = (
        RefusalError(RefusalCode.PEER_UNTRUSTED)
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
        peer = Peer(os_owner_id="synthetic-owner", process_id=1)
        context = ConnectionContext(uuid4(), owner.identity.runtime_boot_id, peer)

        class Channel:
            def __init__(self) -> None:
                self.peer = peer

            def read_exact(self, count: int, *, deadline: float) -> bytes:
                raise AssertionError("refusal mapping must not read a secret")

            def read_ready(self) -> bool:
                return False

            def wait_readable(self, *wakes: ChannelWake) -> bool:
                while not self.read_ready():
                    if any(wake.is_set() for wake in wakes):
                        return False
                    time.sleep(0.01)
                return True

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
            ProfileLogin(
                request_id=uuid4(),
                profile_id=owner.identity.binding.profile_id,
                method="password",
                frontend=OperationFrontendProjection.CLI,
            ),
        )
        assert isinstance(reply, AccessRefusal) and reply.code == RefusalCode.PEER_UNTRUSTED
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
    guard = RLock()
    owner = _owner(tmp_path, guard)
    candidate = _Candidate(owner.identity, guard, failures=failures)

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
    guard = RLock()
    owner = _owner(tmp_path, guard)
    candidate = _Candidate(owner.identity, guard, failures=0)
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
    def unused_secret(connection_id: UUID) -> Generator[HumanProof]:
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
