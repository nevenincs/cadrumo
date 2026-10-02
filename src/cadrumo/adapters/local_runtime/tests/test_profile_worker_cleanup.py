"""Worker transfer and shutdown over explicit native acquisition/release fault ports.

Actual construction, framing, peer binding and retry ownership execute. Native
process acquisition is an isolated fault seam, not platform acceptance evidence.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import override
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import (
    RuntimeClientHello,
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from cadrumo.application.runtime.profile_worker import (
    ProfileWorkerControlRequest,
    ProfileWorkerHumanOutcome,
    ProfileWorkerIdentity,
    ProfileWorkerLeaseRequest,
    ProfileWorkerLeaseTransferRequest,
    ProfileWorkerRequest,
    ProfileWorkerStatus,
)
from cadrumo.application.user_profile.access_contracts import (
    AccessScope,
    AccessSession,
    ProfileAccessBinding,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.login_session import ProfileLoginOutcome
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, await_cancellation_complete, close_async_resources

from .. import profile_worker
from ..framing import read_document, read_secret, write_document
from ..profile_worker import ProfileWorkerProcess
from ..windows import WindowsRuntimeChannel, WindowsRuntimeEndpoint
from ..windows_process import WindowsOwnedProcess, WindowsProcessScope
from ..worker_authorization import WorkerAuthorizationServer
from ..worker_lease_transfer import read_worker_lease

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _Release:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.calls = 0
        self.released = False
        self.failure = OSError("synthetic owned release failure")

    def __call__(self) -> None:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.failure
        self.released = True


class _Channel(WindowsRuntimeChannel):
    def __init__(self, identity: ProfileWorkerIdentity, *, foreign_version: bool = False) -> None:
        self.release = _Release()
        self.inbound = bytearray()
        self.writes: list[bytes] = []
        self.read_failure: BaseException | None = None
        self.before_read: Callable[[], None] | None = None
        for document in (
            RuntimeClientHello(
                product_version="foreign" if foreign_version else "worker-test", storage_identity="a" * 64
            ),
            identity,
        ):
            write_document(self, document, deadline=time.monotonic() + 5)
        self.inbound.extend(b"".join(self.writes))
        self.writes.clear()

    @property
    @override
    def peer(self) -> RuntimePeer:
        return RuntimePeer(os_owner_id="synthetic-owner", process_id=1234)

    @override
    def read_exact(self, count: int, *, deadline: float) -> bytes:
        assert deadline > time.monotonic()
        if self.before_read is not None:
            self.before_read()
        if self.read_failure is not None:
            raise self.read_failure
        assert len(self.inbound) >= count
        value = bytes(self.inbound[:count])
        del self.inbound[:count]
        return value

    @override
    def read_ready(self) -> bool:
        return bool(self.inbound)

    @override
    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        assert deadline > time.monotonic()
        self.writes.append(bytes(payload))

    @override
    def close(self) -> None:
        self.release()


class _Endpoint(WindowsRuntimeEndpoint):
    def __init__(self, channel: _Channel) -> None:
        self.channel = channel
        self.release = _Release()
        self.storage_identity = "a" * 64
        self.listen_failure: BaseException | None = None
        self.before_accept: Callable[[], None] | None = None

    @override
    def listen(self) -> None:
        if self.listen_failure is not None:
            raise self.listen_failure

    @override
    def accept(self, *, timeout: float = 5) -> WindowsRuntimeChannel:
        assert timeout > 0
        if self.before_accept is not None:
            self.before_accept()
        return self.channel

    @override
    def close(self) -> None:
        self.release()


class _Child(WindowsOwnedProcess):
    def __init__(self) -> None:
        self.exited = False
        self.wait_calls = 0

    @override
    def wait(self, *, timeout: float) -> int:
        self.wait_calls += 1
        if self.exited:
            return 1
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)


class _Scope(WindowsProcessScope):
    def __init__(self) -> None:
        self.release = _Release()
        self.launched = False
        self.timeouts: list[float] = []
        self.refuse_zero_timeout = False
        self.child = _Child()

    @override
    def launch(
        self, *, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
    ) -> WindowsOwnedProcess:
        assert executable == Path(sys.executable)
        assert arguments[:3] == ("-I", "-m", "cadrumo.entrypoints.runtime.worker")
        self.launched = True
        return self.child

    @override
    def active_process_ids(self) -> tuple[int, ...]:
        return (1234,) if self.launched and not self.release.released else ()

    @override
    def terminate(self, *, timeout: float = 2) -> None:
        assert timeout >= 0
        self.timeouts.append(timeout)
        if self.refuse_zero_timeout and timeout == 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        self.release()


class _Authorization(WorkerAuthorizationServer):
    def __init__(self) -> None:
        self.release = _Release()
        self.health_failure: RuntimeRefusalCode | None = None
        self.health_calls = 0

    @override
    def close(self) -> None:
        self.release()

    @override
    def require_healthy(self) -> None:
        self.health_calls += 1
        if self.health_failure is not None:
            raise RuntimeRefusalError(self.health_failure)
        assert not self.release.released


class _Fixture:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, root: Path, *, foreign_version: bool = False) -> None:
        self.root = root
        self.identity = ProfileWorkerIdentity(
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
        self.channels = (_Channel(self.identity, foreign_version=foreign_version), _Channel(self.identity))
        self.endpoints = tuple(_Endpoint(channel) for channel in self.channels)
        self.scope = _Scope()
        self.authorization = _Authorization()
        pending = iter(self.endpoints)
        monkeypatch.setattr(profile_worker, "sys", SimpleNamespace(platform="win32", executable=sys.executable))
        monkeypatch.setattr(profile_worker, "version", lambda _: "worker-test")
        monkeypatch.setattr(profile_worker, "worker_endpoint", lambda **_: next(pending))
        monkeypatch.setattr(profile_worker, "WindowsProcessScope", lambda: self.scope)
        monkeypatch.setattr(profile_worker, "WorkerAuthorizationServer", lambda **_: self.authorization)

    def open(self) -> ProfileWorkerProcess:
        return ProfileWorkerProcess(self.identity, storage_root=self.root)


def _retained(error: BaseException) -> AsyncResourceCleanupError:
    cleanup = error.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    return cleanup


def test_successful_construction_transfers_worker_after_both_listeners_retire(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = _Fixture(monkeypatch, tmp_path)
    worker = fixture.open()
    try:
        assert worker.identity == fixture.identity
        assert all(endpoint.release.released for endpoint in fixture.endpoints)
        assert fixture.scope.launched and not fixture.scope.release.released
        assert all(not channel.release.released for channel in fixture.channels)
    finally:
        worker.close()
    assert fixture.scope.release.released
    assert all(channel.release.released for channel in fixture.channels)


@pytest.mark.parametrize("failed_listener", [0, 1])
@pytest.mark.parametrize("persistent_listener", [False, True])
@pytest.mark.parametrize("failed_channel", [False, True])
def test_failed_listener_transfer_contains_unreturned_worker_and_retains_release_owners(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failed_listener: int,
    persistent_listener: bool,
    failed_channel: bool,
) -> None:
    fixture = _Fixture(monkeypatch, tmp_path)
    listener = fixture.endpoints[failed_listener].release
    listener.failures = 2 if persistent_listener else 1
    fixture.channels[0].release.failures = int(failed_channel)
    with pytest.raises(RuntimeRefusalError) as caught:
        fixture.open()
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
    assert isinstance(caught.value.__cause__, AsyncResourceCleanupError)
    assert fixture.scope.release.released and fixture.authorization.release.released
    assert all(endpoint.release.calls == 1 for endpoint in fixture.endpoints)
    assert all(channel.release.calls == 1 for channel in fixture.channels)
    cleanup = _retained(caught.value)
    if persistent_listener:
        with pytest.raises(AsyncResourceCleanupError) as retry_failed:
            asyncio.run(cleanup.retry_cleanup())
        cleanup = retry_failed.value
        assert not listener.released
        assert all(channel.release.released for channel in fixture.channels)
    asyncio.run(cleanup.retry_cleanup())
    asyncio.run(cleanup.retry_cleanup())
    assert all(endpoint.release.released for endpoint in fixture.endpoints)
    assert all(channel.release.released for channel in fixture.channels)
    assert listener.calls == listener.failures + 1
    assert fixture.endpoints[1 - failed_listener].release.calls == 1
    assert fixture.channels[0].release.calls == int(failed_channel) + 1
    assert fixture.channels[1].release.calls == 1


@pytest.mark.parametrize("cancellation", [False, True])
def test_failed_launch_preserves_exact_primary_and_retries_all_failed_listeners(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cancellation: bool
) -> None:
    fixture = _Fixture(monkeypatch, tmp_path)
    primary = (
        asyncio.CancelledError("synthetic interrupted launch") if cancellation else OSError("synthetic listen refusal")
    )
    fixture.endpoints[1].listen_failure = primary
    for endpoint in fixture.endpoints:
        endpoint.release.failures = 1
    fixture.scope.release.failures = 1
    with pytest.raises(type(primary)) as caught:
        fixture.open()
    assert caught.value is primary
    assert not fixture.scope.launched
    assert fixture.scope.release.calls == 1
    assert all(endpoint.release.calls == 1 for endpoint in fixture.endpoints)
    asyncio.run(_retained(primary).retry_cleanup())
    assert fixture.scope.release.released
    assert all(endpoint.release.released for endpoint in fixture.endpoints)


def test_shutdown_attempts_containment_and_both_channels_after_other_releases_fail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = _Fixture(monkeypatch, tmp_path)
    worker = fixture.open()
    fixture.authorization.release.failures = 1
    fixture.scope.release.failures = 1
    fixture.channels[0].release.failures = 1
    with pytest.raises(ExceptionGroup) as caught:
        worker.close()
    assert caught.value.exceptions == (
        fixture.authorization.release.failure,
        fixture.scope.release.failure,
        fixture.channels[0].release.failure,
    )
    assert fixture.scope.release.calls == 1
    assert fixture.channels[1].release.released
    assert worker._channel is fixture.channels[0] and worker._operation_channel is None
    worker.close()
    assert worker._channel is worker._operation_channel is None
    assert fixture.scope.release.released and fixture.authorization.release.released
    assert fixture.channels[0].release.calls == 2 and fixture.channels[1].release.calls == 1


def test_protocol_failure_preserves_primary_and_retains_failed_worker_containment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = _Fixture(monkeypatch, tmp_path)
    worker = fixture.open()
    primary = OSError("synthetic interrupted reply")
    fixture.channels[0].read_failure = primary
    fixture.scope.release.failures = 1
    with pytest.raises(OSError) as caught:
        worker.status()
    assert caught.value is primary
    assert fixture.scope.release.calls == 1
    assert all(channel.release.released for channel in fixture.channels)
    asyncio.run(_retained(primary).retry_cleanup())
    assert fixture.scope.release.released
    assert fixture.channels[1].release.calls == 1


def test_protocol_cleanup_retry_gets_fresh_bound_after_original_request_deadline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = _Fixture(monkeypatch, tmp_path)
    worker = fixture.open()
    primary = OSError("synthetic interrupted reply")
    fixture.channels[0].read_failure = primary
    fixture.scope.refuse_zero_timeout = True
    clock = SimpleNamespace(instant=time.monotonic())

    def finish_request_budget() -> None:
        clock.instant += 6

    fixture.channels[0].before_read = finish_request_budget
    monkeypatch.setattr(profile_worker, "time", SimpleNamespace(monotonic=lambda: clock.instant))
    with pytest.raises(OSError) as caught:
        worker._exchange(
            ProfileWorkerRequest(ProfileWorkerControlRequest(action="status", request_id=uuid4())),
            ProfileWorkerStatus,
            deadline=clock.instant + 5,
        )
    assert caught.value is primary
    assert fixture.scope.timeouts == [0]
    assert not fixture.scope.release.released
    asyncio.run(_retained(primary).retry_cleanup())
    assert fixture.scope.timeouts == [0, 2]
    assert fixture.scope.release.released


def test_post_accept_child_death_keeps_failed_temporary_channel_on_unreturned_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = _Fixture(monkeypatch, tmp_path)
    channel = fixture.channels[0]
    channel.release.failures = 1

    def exit_on_accept() -> None:
        fixture.scope.child.exited = True

    fixture.endpoints[0].before_accept = exit_on_accept
    with pytest.raises(RuntimeRefusalError) as caught:
        fixture.open()
    assert caught.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    candidate = profile_worker.unreturned_profile_worker(caught.value)
    assert candidate is not None and candidate._channel is None
    assert channel.release.calls == 1 and not channel.release.released
    assert fixture.scope.release.released
    # The parent keeps this candidate after projecting only the refusal code;
    # settlement must work without needing the original exception attachment.
    candidate.close()
    assert channel.release.calls == 2 and channel.release.released
    candidate.close()
    assert channel.release.calls == 2


def _control_request(channel: _Channel, identity: ProfileWorkerIdentity) -> ProfileWorkerRequest:
    """Decode the actual emitted request through the canonical frame reader."""
    reader = _Channel(identity)
    reader.inbound = bytearray(b"".join(channel.writes))
    channel.writes.clear()
    return read_document(reader, ProfileWorkerRequest, deadline=time.monotonic() + 5)


def _control_reply(channel: _Channel, reply: ProfileWorkerStatus | ProfileWorkerHumanOutcome) -> None:
    """Queue actual canonical reply bytes at the explicit native channel port."""
    write_document(channel, reply, deadline=time.monotonic() + 5)
    channel.inbound.extend(b"".join(channel.writes))
    channel.writes.clear()


def _api_lease(identity: ProfileWorkerIdentity) -> AccessSession:
    instant = datetime(2026, 10, 1, tzinfo=UTC)
    return AccessSession(
        session_id=uuid4(),
        binding=identity.binding,
        profile_lock_generation=0,
        runtime_boot_id=identity.runtime_boot_id,
        connection_id=uuid4(),
        client_id=uuid4(),
        kind=SessionKind.API_KEY,
        state=SessionState.ACTIVE,
        scope=AccessScope(
            operations=frozenset(),
            actions=frozenset(),
            disclosures=frozenset(),
            periods=frozenset(),
            allow_period_independent=False,
            allow_delegation=False,
        ),
        grant_id=uuid4(),
        grant_generation=1,
        key_id=uuid4(),
        key_generation=1,
        issued_at=instant,
        expires_at=instant + timedelta(minutes=1),
        issued_monotonic=time.monotonic(),
    )


def test_api_preparation_is_key_free_and_native_liveness_finishes_before_reply(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = _Fixture(monkeypatch, tmp_path)
    worker = fixture.open()
    channel = fixture.channels[0]
    channel.writes.clear()
    blocked, release = Event(), Event()
    requests: list[ProfileWorkerControlRequest] = []

    def respond() -> None:
        if channel.inbound:
            return
        reader = _Channel(fixture.identity)
        reader.inbound = bytearray(b"".join(channel.writes))
        channel.writes.clear()
        request = read_document(reader, ProfileWorkerRequest, deadline=time.monotonic() + 5)
        assert isinstance(request.root, ProfileWorkerControlRequest)
        assert request.root.action == "prepare_api"
        assert not reader.inbound, "key-free preparation emitted extra lease or secret frames"
        requests.append(request.root)
        blocked.set()
        assert release.wait(5), "API preparation reply barrier was not released"
        _control_reply(
            channel, ProfileWorkerStatus(identity=fixture.identity, request_id=request.root.request_id, sessions=())
        )

    channel.before_read = respond
    pool = ThreadPoolExecutor(max_workers=2)
    try:
        preparation = pool.submit(worker.prepare_api_admission, deadline=time.monotonic() + 30)
        assert blocked.wait(2), "actual API preparation did not reach the native reply barrier"
        pool.submit(worker.require_alive).result(timeout=2)
        assert not preparation.done() and not release.is_set()
        assert not fixture.scope.release.released
        assert all(not owned.release.released for owned in fixture.channels)
        release.set()
        assert preparation.result(timeout=2) is None
        assert len(requests) == 1 and not channel.writes and not channel.inbound
    finally:
        release.set()
        pool.shutdown(wait=True)
        worker.close()


def test_api_prepare_and_install_reuse_original_deadline_and_wipe_material(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = _Fixture(monkeypatch, tmp_path)
    worker = fixture.open()
    channel = fixture.channels[0]
    channel.writes.clear()
    lease = _api_lease(fixture.identity)
    material = bytearray(b"s" * 32)
    original_deadline = time.monotonic() + 30
    clock = SimpleNamespace(instant=time.monotonic())
    monkeypatch.setattr(profile_worker, "time", SimpleNamespace(monotonic=lambda: clock.instant))
    outbound_deadlines: list[float] = []
    actions: list[str] = []
    replying = False
    native_write = channel.write_all

    def record_write(payload: bytes | bytearray, *, deadline: float) -> None:
        if not replying:
            outbound_deadlines.append(deadline)
        native_write(payload, deadline=deadline)

    def respond() -> None:
        nonlocal replying
        if channel.inbound:
            return
        reader = _Channel(fixture.identity)
        reader.inbound = bytearray(b"".join(channel.writes))
        channel.writes.clear()
        request = read_document(reader, ProfileWorkerRequest, deadline=time.monotonic() + 5)
        if isinstance(request.root, ProfileWorkerLeaseTransferRequest):
            request = read_worker_lease(reader, request.root, deadline=time.monotonic() + 5)
            assert isinstance(request.root, ProfileWorkerLeaseRequest) and request.root.action == "install"
            assert request.root.lease == lease
            with read_secret(reader, deadline=time.monotonic() + 5) as received:
                assert received == b"s" * 32
        else:
            assert isinstance(request.root, ProfileWorkerControlRequest) and request.root.action == "prepare_api"
        assert not reader.inbound
        actions.append(request.root.action)
        replying = True
        try:
            _control_reply(
                channel,
                ProfileWorkerStatus(identity=fixture.identity, request_id=request.root.request_id, sessions=()),
            )
        finally:
            replying = False

    monkeypatch.setattr(channel, "write_all", record_write)
    channel.before_read = respond
    try:
        worker.prepare_api_admission(deadline=original_deadline)
        assert actions == ["prepare_api"] and any(material)
        clock.instant += 12
        worker.install(lease, material, deadline=original_deadline)
        assert actions == ["prepare_api", "install"]
        assert outbound_deadlines and all(value == original_deadline for value in outbound_deadlines)
        assert not any(material)
        assert not channel.writes and not channel.inbound
    finally:
        worker.close()


@pytest.mark.parametrize("action", ["prepare", "install"])
def test_api_original_deadline_includes_queue_without_writing_or_retiring_worker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, action: str
) -> None:
    fixture = _Fixture(monkeypatch, tmp_path)
    worker = fixture.open()
    channel = fixture.channels[0]
    channel.writes.clear()
    blocked, release = Event(), Event()
    actions: list[str] = []
    material = bytearray(b"s" * 32)

    def respond() -> None:
        if channel.inbound:
            return
        request = _control_request(channel, fixture.identity)
        actions.append(request.root.action)
        assert request.root.action == "status"
        blocked.set()
        assert release.wait(5), "status reply barrier was not released"
        _control_reply(
            channel, ProfileWorkerStatus(identity=fixture.identity, request_id=request.root.request_id, sessions=())
        )

    channel.before_read = respond
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        status = pool.submit(worker.status)
        assert blocked.wait(2), "actual control exchange did not hold the wire lock"
        original_deadline = time.monotonic() - 1
        with pytest.raises(RuntimeRefusalError) as caught:
            if action == "prepare":
                worker.prepare_api_admission(deadline=original_deadline)
            else:
                worker.install(_api_lease(fixture.identity), material, deadline=original_deadline)
        assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
        assert not channel.writes and actions == ["status"]
        assert fixture.scope.release.calls == 0
        assert all(owned.release.calls == 0 for owned in fixture.channels)
        worker.require_alive()
        if action == "install":
            assert not any(material)
        release.set()
        assert status.result(timeout=2).identity == fixture.identity
        worker.require_alive()
    finally:
        release.set()
        pool.shutdown(wait=True)
        worker.close()


def test_worker_native_liveness_finishes_while_control_reply_is_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = _Fixture(monkeypatch, tmp_path)
    worker = fixture.open()
    channel = fixture.channels[0]
    channel.writes.clear()
    blocked, release = Event(), Event()

    def respond() -> None:
        if channel.inbound:
            return
        request = _control_request(channel, fixture.identity)
        blocked.set()
        assert release.wait(5), "control reply barrier was not released"
        _control_reply(
            channel, ProfileWorkerStatus(identity=fixture.identity, request_id=request.root.request_id, sessions=())
        )

    channel.before_read = respond
    pool = ThreadPoolExecutor(max_workers=2)
    status = pool.submit(worker.status)
    try:
        assert blocked.wait(2), "actual worker control exchange did not reach the read barrier"
        alive = pool.submit(worker.require_alive)
        alive.result(timeout=2)
        assert not release.is_set() and not status.done()
    finally:
        release.set()
        pool.shutdown(wait=True)
        worker.close()
    assert status.result().identity == fixture.identity


def test_human_admission_yield_allows_control_status_and_retirement_without_replacing_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = _Fixture(monkeypatch, tmp_path)
    worker = fixture.open()
    channel = fixture.channels[0]
    channel.writes.clear()
    candidate_id, session_id = uuid4(), uuid4()
    instant = datetime(2026, 10, 1, tzinfo=UTC)
    login = ProfileLoginOutcome(
        bucket_id=str(fixture.identity.binding.profile_id),
        label="Synthetic human profile",
        authenticated_at=instant,
        idle_deadline=instant,
        absolute_deadline=instant,
        session_persisted=False,
        already_authenticated=False,
    )
    actions: list[str] = []

    def respond() -> None:
        if channel.inbound:
            return
        request = _control_request(channel, fixture.identity)
        actions.append(request.root.action)
        if request.root.action == "password":
            _control_reply(
                channel,
                ProfileWorkerHumanOutcome(
                    identity=fixture.identity,
                    request_id=request.root.request_id,
                    candidate_id=candidate_id,
                    login=login,
                ),
            )
        else:
            _control_reply(
                channel, ProfileWorkerStatus(identity=fixture.identity, request_id=request.root.request_id, sessions=())
            )

    channel.before_read = respond
    proof = bytearray(b"synthetic-human-proof")
    pool = ThreadPoolExecutor(max_workers=1)
    started = Event()

    def control_transaction() -> ProfileWorkerStatus:
        started.set()
        worker.require_alive()
        status = worker.status()
        worker.retire(session_id)
        return status

    try:
        with worker.authenticate_human(proof) as outcome:
            assert outcome == login
            transaction = pool.submit(control_transaction)
            assert started.wait(2), "separate control transaction did not start"
            assert transaction.result(timeout=2).identity == fixture.identity
            assert worker._human_candidate == candidate_id
            assert actions == ["password", "status", "retire"]
        assert worker._human_candidate is None
        assert not any(proof)
        assert actions == ["password", "status", "retire", "cancel_human"]
    finally:
        pool.shutdown(wait=True)
        worker.close()


@pytest.mark.parametrize("state", ["healthy", "stopped", "dead", "unhealthy"])
def test_worker_native_guard_released_contention_rechecks_current_health(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, state: str
) -> None:
    fixture = _Fixture(monkeypatch, tmp_path)
    worker = fixture.open()
    held, release, checking = Event(), Event(), Event()
    baseline_health = fixture.authorization.health_calls
    baseline_waits = fixture.scope.child.wait_calls

    def hold_native_guard() -> None:
        with worker._native_guard:
            held.set()
            assert release.wait(5), "native guard barrier was not released"

    def current_health() -> RuntimeRefusalCode | None:
        checking.set()
        try:
            worker.require_alive()
        except RuntimeRefusalError as error:
            return error.reason
        return None

    pool = ThreadPoolExecutor(max_workers=2)
    holding = pool.submit(hold_native_guard)
    try:
        assert held.wait(2), "foreign thread did not acquire native guard"
        health = pool.submit(current_health)
        assert checking.wait(2), "current health observation did not start"
        with pytest.raises(TimeoutError):
            health.result(timeout=0.05)
        assert fixture.authorization.health_calls == baseline_health
        assert fixture.scope.child.wait_calls == baseline_waits
        if state == "stopped":
            worker._stopping.set()
        elif state == "dead":
            fixture.scope.child.exited = True
        elif state == "unhealthy":
            fixture.authorization.health_failure = RuntimeRefusalCode.UNAVAILABLE
        release.set()
        expected = (
            None
            if state == "healthy"
            else RuntimeRefusalCode.UNAVAILABLE
            if state == "unhealthy"
            else RuntimeRefusalCode.CONNECTION_CLOSED
        )
        assert health.result(timeout=2) is expected
        assert fixture.authorization.health_calls == baseline_health + int(state != "stopped")
        assert fixture.scope.child.wait_calls == baseline_waits + int(state in {"healthy", "dead"})
        assert fixture.scope.release.calls == fixture.authorization.release.calls == 0
        assert all(channel.release.calls == 0 for channel in fixture.channels)
    finally:
        release.set()
        holding.result(timeout=2)
        pool.shutdown(wait=True)
        worker.close()


def test_worker_native_guard_unreleased_contention_refuses_without_retiring_live_custody(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fixture = _Fixture(monkeypatch, tmp_path)
    worker = fixture.open()
    held, release = Event(), Event()

    def hold_native_guard() -> None:
        with worker._native_guard:
            held.set()
            assert release.wait(5), "native guard barrier was not released"

    pool = ThreadPoolExecutor(max_workers=1)
    holding = pool.submit(hold_native_guard)
    try:
        assert held.wait(2), "foreign thread did not acquire native guard"
        started = time.monotonic()
        with pytest.raises(RuntimeRefusalError) as caught:
            worker.require_alive()
        assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
        assert 1.8 <= time.monotonic() - started < 4
        assert not release.is_set()
        assert fixture.scope.release.calls == fixture.authorization.release.calls == 0
        assert all(channel.release.calls == 0 for channel in fixture.channels)
    finally:
        release.set()
        holding.result(timeout=2)
        pool.shutdown(wait=True)
        try:
            worker.require_alive()
            assert not fixture.scope.release.released
            assert all(not channel.release.released for channel in fixture.channels)
        finally:
            worker.close()


@pytest.mark.parametrize("cancellation", [False, True], ids=["body-failure", "body-cancellation"])
@pytest.mark.parametrize("failed_native_close", [False, True], ids=["contained", "retry-native-close"])
def test_human_admission_cancel_reply_failure_preserves_body_and_actual_cleanup_owner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cancellation: bool, failed_native_close: bool
) -> None:
    fixture = _Fixture(monkeypatch, tmp_path)
    worker = fixture.open()
    channel = fixture.channels[0]
    channel.writes.clear()
    fixture.scope.release.failures = int(failed_native_close)
    primary = (
        asyncio.CancelledError("synthetic admission body cancellation") if cancellation else OSError("body failed")
    )
    cancel_failure = RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
    instant = datetime(2026, 10, 1, tzinfo=UTC)
    login = ProfileLoginOutcome(
        bucket_id=str(fixture.identity.binding.profile_id),
        label="Synthetic human profile",
        authenticated_at=instant,
        idle_deadline=instant,
        absolute_deadline=instant,
        session_persisted=False,
        already_authenticated=False,
    )
    actions: list[str] = []

    def respond() -> None:
        if channel.inbound:
            return
        request = _control_request(channel, fixture.identity)
        actions.append(request.root.action)
        if request.root.action == "password":
            _control_reply(
                channel,
                ProfileWorkerHumanOutcome(
                    identity=fixture.identity,
                    request_id=request.root.request_id,
                    candidate_id=uuid4(),
                    login=login,
                ),
            )
        else:
            assert request.root.action == "cancel_human"
            channel.read_failure = cancel_failure

    channel.before_read = respond
    proof = bytearray(b"synthetic-human-proof")
    try:
        with pytest.raises(type(primary)) as caught, worker.authenticate_human(proof) as outcome:
            assert outcome == login
            raise primary
        assert caught.value is primary
        assert not any(proof)
        assert worker._human_candidate is None
        assert actions == ["password", "cancel_human"]
        retained = _retained(primary)
        assert primary.__dict__["cleanup_error"] is retained
        assert any(failure is cancel_failure for failure in retained._failures)
        assert fixture.scope.release.calls == 1
        assert all(channel.release.released for channel in fixture.channels)
        asyncio.run(retained.retry_cleanup())
        assert fixture.scope.release.released
        assert fixture.scope.release.calls == 1 + int(failed_native_close)
        assert all(channel.release.calls == 1 for channel in fixture.channels)
        assert actions == ["password", "cancel_human"]
    finally:
        if not fixture.scope.release.released:
            worker.close()


def test_human_admission_cancel_merges_cancellation_only_prior_cleanup_owner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prior_release = _Release(failures=1)

    class PriorOwner:
        async def close(self) -> None:
            if not prior_release.released:
                prior_release()

    prior_owner = PriorOwner()
    primary = asyncio.CancelledError("synthetic body cancellation with prior failed cleanup")

    async def retain_prior_failure() -> None:
        with pytest.raises(asyncio.CancelledError) as caught:
            await await_cancellation_complete(
                close_async_resources(prior_owner, task_name="prior-release", primary_error=None),
                task_name="prior-cancellation-settlement",
                cancellation=primary,
            )
        assert caught.value is primary

    asyncio.run(retain_prior_failure())
    assert prior_release.calls == 1 and not prior_release.released
    assert isinstance(primary.__dict__["cleanup_error"], AsyncResourceCleanupError)
    assert "async_cleanup_error" not in primary.__dict__
    fixture = _Fixture(monkeypatch, tmp_path)
    worker = fixture.open()
    channel = fixture.channels[0]
    channel.writes.clear()
    fixture.scope.release.failures = 1
    cancel_failure = RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
    instant = datetime(2026, 10, 1, tzinfo=UTC)
    login = ProfileLoginOutcome(
        bucket_id=str(fixture.identity.binding.profile_id),
        label="Synthetic human profile",
        authenticated_at=instant,
        idle_deadline=instant,
        absolute_deadline=instant,
        session_persisted=False,
        already_authenticated=False,
    )
    actions: list[str] = []

    def respond() -> None:
        if channel.inbound:
            return
        request = _control_request(channel, fixture.identity)
        actions.append(request.root.action)
        if request.root.action == "password":
            _control_reply(
                channel,
                ProfileWorkerHumanOutcome(
                    identity=fixture.identity,
                    request_id=request.root.request_id,
                    candidate_id=uuid4(),
                    login=login,
                ),
            )
        else:
            assert request.root.action == "cancel_human"
            channel.read_failure = cancel_failure

    channel.before_read = respond
    proof = bytearray(b"synthetic-human-proof")
    try:
        with pytest.raises(asyncio.CancelledError) as caught, worker.authenticate_human(proof) as outcome:
            assert outcome == login
            raise primary
        assert caught.value is primary
        assert not any(proof) and worker._human_candidate is None
        retained = _retained(primary)
        assert primary.__dict__["cleanup_error"] is retained
        assert any(failure is cancel_failure for failure in retained._failures)
        assert prior_release.calls == fixture.scope.release.calls == 1
        asyncio.run(retained.retry_cleanup())
        assert prior_release.released and fixture.scope.release.released
        assert prior_release.calls == fixture.scope.release.calls == 2
        assert all(channel.release.calls == 1 for channel in fixture.channels)
        assert actions == ["password", "cancel_human"]
    finally:
        asyncio.run(prior_owner.close())
        if not fixture.scope.release.released:
            worker.close()
