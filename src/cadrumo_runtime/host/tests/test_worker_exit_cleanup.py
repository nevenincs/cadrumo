"""Worker entrypoint/serve release faults; no native admission or execution claim."""

from __future__ import annotations

import asyncio
import logging
import struct
import sys
import threading
import time
from contextlib import nullcontext, suppress
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Never, cast, override
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.operations.drain import OperationDrainResult
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.core.async_cleanup import AsyncResourceCleanupError
from cadrumo_client.contracts.contracts import ChannelWake, Peer, RefusalCode, RefusalError, ServerHello
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import write_document
from cadrumo_runtime.contracts.profile_worker import (
    ProfileWorkerContractRequest,
    ProfileWorkerControlRequest,
    ProfileWorkerLeaseTransferRequest,
    ProfileWorkerRequest,
    ProfileWorkerRetireRequest,
)

from ...adapters.worker_transport import WorkerChannel, WorkerEndpoint
from .. import worker, worker_operation_requests, worker_service
from ..operation_host import ProfileWorkerOperationHost
from ..profile_login import ProfileWorkerHumanLogin

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_description_keeps_loop_responsive_and_retains_host_until_thread_settles() -> None:
    """A cancelled description cannot leave its host in use after cleanup."""

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        loop_thread = threading.get_ident()
        entered = asyncio.Event()
        release = threading.Event()
        finished = threading.Event()
        refusal = RefusalError(RefusalCode.UNAVAILABLE)
        request = ProfileWorkerContractRequest(
            request_id=uuid4(), session_id=uuid4(), definition_id="user-profile.field-mutation"
        )

        def describe(session_id: UUID, definition_id: str) -> Never:
            assert threading.get_ident() != loop_thread
            assert (session_id, definition_id) == (request.session_id, request.definition_id)
            loop.call_soon_threadsafe(entered.set)
            release.wait()
            finished.set()
            raise refusal

        class DescriptionOperations(ProfileWorkerOperationHost):
            def __init__(self) -> None:
                pass

            @override
            def describe(self, session_id: UUID, definition_id: str) -> Never:
                return describe(session_id, definition_id)

        # This path raises before channel or custody access; bind only its host.
        handler = asyncio.create_task(
            worker_operation_requests.describe_contract(cast(WorkerChannel, object()), DescriptionOperations(), request)
        )
        started = asyncio.create_task(entered.wait())
        try:
            await asyncio.wait((handler, started), return_when=asyncio.FIRST_COMPLETED)
            if handler.done():
                await handler
                pytest.fail("Description returned before the release handoff")
            assert entered.is_set() and not finished.is_set()
            handler.cancel()
            await asyncio.sleep(0)
            handler.cancel()
            await asyncio.sleep(0)
            assert not handler.done() and not finished.is_set()
            release.set()
            with pytest.raises(asyncio.CancelledError) as caught:
                await handler
            assert finished.is_set()
            assert caught.value.__dict__["cleanup_error"] is refusal
        finally:
            release.set()
            started.cancel()
            with suppress(asyncio.CancelledError):
                await started
            with suppress(asyncio.CancelledError, RefusalError, AssertionError):
                await handler

    asyncio.run(scenario())


class _Release:
    """An explicit release fault port, successful only after all planned failures."""

    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.calls = 0
        self.closed = False
        self.close_threads: list[int] = []

    def close(self) -> None:
        self.calls += 1
        self.close_threads.append(threading.get_ident())
        if self.calls <= self.failures:
            raise OSError("synthetic release failure")
        self.closed = True


class _Channel(_Release):
    """Real framing runs against this bounded transport fault port."""

    def __init__(self, failures: int = 0, *, read_failure: BaseException | None = None) -> None:
        super().__init__(failures)
        self.peer = Peer(os_owner_id="synthetic-owner", process_id=41)
        self.incoming = bytearray()
        self.read_failure = read_failure

    def read_ready(self) -> bool:
        if self.read_failure is not None:
            raise self.read_failure
        return bool(self.incoming)

    def wait_readable(self, *wakes: ChannelWake) -> bool:
        while not self.read_ready():
            if any(wake.is_set() for wake in wakes):
                return False
            time.sleep(0.01)
        return True

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        assert deadline > 0
        if self.read_failure is not None:
            raise self.read_failure
        if len(self.incoming) < count:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        result = bytes(self.incoming[:count])
        del self.incoming[:count]
        return result

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        assert deadline > 0 and payload

    def queue(self, document: BaseModel) -> None:
        target = self.incoming

        class _Writer:
            def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
                assert deadline > 0
                target.extend(payload)

        write_document(cast(WorkerChannel, _Writer()), document, deadline=1)


class _Endpoint(_Release):
    storage_identity = "1" * 64

    def __init__(self, channel: _Channel) -> None:
        super().__init__()
        self.channel = channel

    def connect(self) -> WorkerChannel:
        return cast(WorkerChannel, self.channel)


def _identity() -> ProfileWorkerIdentity:
    return ProfileWorkerIdentity(
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


@dataclass
class _Entry:
    identity: ProfileWorkerIdentity
    control: _Channel
    operation: _Channel
    custody: _Release
    endpoints: tuple[_Endpoint, _Endpoint]
    arguments: list[str]


def _entry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    body_failure: BaseException | None = None,
) -> _Entry:
    identity = _identity()
    control, operation = _Channel(), _Channel()
    endpoints = _Endpoint(control), _Endpoint(operation)
    for channel in (control, operation):
        channel.queue(
            ServerHello(
                product_version="test-cohort",
                storage_identity=endpoints[0].storage_identity,
                boot_id=identity.runtime_boot_id,
            )
        )
        channel.queue(identity)
    custody = _Release()
    selected = iter(endpoints)

    def endpoint(*, storage_root: Path, worker_namespace: UUID) -> WorkerEndpoint:
        assert storage_root == tmp_path and isinstance(worker_namespace, UUID)
        return cast(WorkerEndpoint, next(selected))

    async def serve(*_owners: object) -> None:
        if body_failure is not None:
            raise body_failure

    monkeypatch.setattr(
        worker, "sys", SimpleNamespace(platform="linux", flags=SimpleNamespace(isolated=True), exception=sys.exception)
    )
    monkeypatch.setattr(worker, "version", lambda _name: "test-cohort")
    monkeypatch.setattr(worker, "worker_endpoint", endpoint)
    monkeypatch.setattr(worker, "ProfileWorkerCustody", lambda *_args, **_kwargs: custody)
    monkeypatch.setattr(
        worker,
        "ProfileWorkerOperationHost",
        lambda *_args, **_kwargs: SimpleNamespace(profile_decode_context=lambda: None),
    )
    monkeypatch.setattr(worker, "ProfileWorkerHumanLogin", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(worker, "profile_adapter_composition", nullcontext)
    monkeypatch.setattr(worker, "live_exchange_rate_composition", nullcontext)
    monkeypatch.setattr(worker_service, "_serve", serve)
    return _Entry(
        identity,
        control,
        operation,
        custody,
        endpoints,
        [
            "--storage-root",
            str(tmp_path),
            "--worker-id",
            str(identity.worker_id),
            "--parent-pid",
            "41",
            "--expected-version",
            "test-cohort",
        ],
    )


@pytest.mark.parametrize("failures", [1, 2])
@pytest.mark.parametrize("body_kind", ["clean", "typed", "unexpected", "cancelled"])
def test_run_attempts_all_releases_preserves_primary_and_retains_only_failed_owners(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failures: int, body_kind: str
) -> None:
    primary = {
        "clean": None,
        "typed": RefusalError(RefusalCode.INVALID_FRAME),
        "unexpected": ValueError("synthetic worker body failure"),
        "cancelled": asyncio.CancelledError("synthetic worker cancellation"),
    }[body_kind]
    entry = _entry(monkeypatch, tmp_path, body_failure=primary)
    entry.custody.failures = failures
    entry.control.failures = failures
    with pytest.raises((AsyncResourceCleanupError, RefusalError, ValueError, asyncio.CancelledError)) as caught:
        worker.run(entry.arguments)
    if primary is None:
        assert isinstance(caught.value, AsyncResourceCleanupError)
        cleanup = caught.value
    else:
        assert caught.value is primary
        cleanup = primary.__dict__.get("async_cleanup_error") or primary.__dict__.get("cleanup_error")
        assert isinstance(cleanup, AsyncResourceCleanupError)
    assert entry.custody.calls == entry.control.calls == entry.operation.calls == 1
    assert all(endpoint.calls == 1 and endpoint.closed for endpoint in entry.endpoints)
    assert entry.operation.closed
    if failures == 2:
        with pytest.raises(AsyncResourceCleanupError) as retry:
            asyncio.run(cleanup.retry_cleanup())
        cleanup = retry.value
    asyncio.run(cleanup.retry_cleanup())
    asyncio.run(cleanup.retry_cleanup())
    assert entry.custody.closed and entry.control.closed
    assert entry.custody.calls == entry.control.calls == failures + 1
    assert entry.operation.calls == 1 and all(endpoint.calls == 1 for endpoint in entry.endpoints)


@pytest.mark.parametrize("refused", [False, True])
def test_run_reports_clean_or_typed_exit_only_after_every_owner_releases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, refused: bool
) -> None:
    primary = RefusalError(RefusalCode.INVALID_FRAME) if refused else None
    entry = _entry(monkeypatch, tmp_path, body_failure=primary)
    assert worker.run(entry.arguments) == (2 if refused else 0)
    assert entry.custody.calls == entry.control.calls == entry.operation.calls == 1
    assert all(endpoint.calls == 1 for endpoint in entry.endpoints)


def test_rejected_handshake_retains_first_failed_close_and_does_not_close_channel_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = _entry(monkeypatch, tmp_path)
    entry.control.incoming.clear()
    entry.control.queue(
        ServerHello(
            product_version="wrong-cohort",
            storage_identity=entry.endpoints[0].storage_identity,
            boot_id=entry.identity.runtime_boot_id,
        )
    )
    entry.control.failures = 1
    with pytest.raises(RefusalError) as caught:
        worker.run(entry.arguments)
    assert caught.value.reason is RefusalCode.VERSION_MISMATCH
    cleanup = caught.value.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    assert entry.control.calls == 1 and entry.custody.calls == entry.operation.calls == 0
    assert entry.endpoints[0].closed and entry.endpoints[1].calls == 0
    asyncio.run(cleanup.retry_cleanup())
    asyncio.run(cleanup.retry_cleanup())
    assert entry.control.calls == 2 and entry.control.closed


class _Operations:
    def __init__(self, failures: int) -> None:
        self.owner = _Release(failures)

    @property
    def calls(self) -> int:
        return self.owner.calls

    @property
    def closed(self) -> bool:
        return self.owner.closed

    def profile_decode_context(self) -> None:
        """Only the entrypoint's constructor binding is under test."""

    async def close(self) -> OperationDrainResult:
        self.owner.close()
        return OperationDrainResult(unresolved=(), recovery_required=())


class _ServeCustody(_Release):
    def __init__(self) -> None:
        super().__init__()
        self.identity = _identity()

    def expire(self) -> None:
        pass

    def live_sessions(self) -> tuple[UUID, ...]:
        return ()

    def seconds_until_expiry(self) -> float | None:
        return None


class _IdleUploads:
    def expire(self, *, live_sessions: tuple[UUID, ...]) -> None:
        assert live_sessions == ()

    def seconds_until_expiry(self) -> float | None:
        return None


class _IdleHuman:
    def expire(self) -> None:
        pass

    def seconds_until_expiry(self) -> float | None:
        return None


def test_control_dispatch_timing_names_retirement_and_keeps_behavior_unchanged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    request_id, session_id = uuid4(), uuid4()
    request = ProfileWorkerRequest(root=ProfileWorkerRetireRequest(request_id=request_id, session_id=session_id))
    retired: list[UUID] = []
    discarded: list[UUID] = []
    expired: list[tuple[UUID, ...]] = []
    forgotten: list[bool] = []
    output: list[bytes] = []

    class Custody(_ServeCustody):
        def retire(self, selected: UUID) -> None:
            retired.append(selected)

    class Human:
        def discard(self, selected: UUID) -> None:
            discarded.append(selected)

    class Operations:
        def forget_settled_ephemeral(self) -> None:
            forgotten.append(True)

        def in_flight_operation_count(self) -> int:
            return 0

    class Uploads:
        def expire(self, *, live_sessions: tuple[UUID, ...]) -> None:
            expired.append(live_sessions)

    class Channel:
        def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
            assert deadline > 0
            output.append(bytes(payload))

    custody = Custody()
    failed = asyncio.Event()
    context = worker_service._WorkerControl(
        channel=cast(WorkerChannel, Channel()),
        custody=cast(ProfileWorkerCustody, custody),
        human=cast(ProfileWorkerHumanLogin, Human()),
        operations=cast(ProfileWorkerOperationHost, Operations()),
        uploads=cast(worker_service.WorkerSubmissionStaging, Uploads()),
        failed=failed,
        operation_release=cast(worker_service._worker_cleanup.WorkerRelease[OperationDrainResult], object()),
        upload_release=cast(worker_service._worker_cleanup.WorkerRelease[None], object()),
        changed=asyncio.Event(),
    )
    receive_calls = 0

    async def receive(*_arguments: object, **_keywords: object) -> ProfileWorkerRequest:
        nonlocal receive_calls
        receive_calls += 1
        if receive_calls == 1:
            return request
        raise RefusalError(RefusalCode.UNAVAILABLE)

    monkeypatch.setattr(worker_service._worker_requests, "receive", receive)
    clock = iter((10.0, 10.75, 11.0))
    monkeypatch.setattr(worker_service, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    caplog.set_level(logging.DEBUG, logger=worker_service._log.name)

    with pytest.raises(RefusalError) as caught:
        asyncio.run(worker_service._serve_control_requests(context))

    assert caught.value.reason is RefusalCode.UNAVAILABLE
    assert retired == discarded == [session_id]
    assert expired == [()]
    assert forgotten == [True]
    assert output
    assert context.changed.is_set(), "a handled command must wake idle custody expiry"
    started = next(
        record for record in caplog.records if record.getMessage() == "profile_worker_control_dispatch_started"
    )
    slow = next(record for record in caplog.records if record.getMessage() == "profile_worker_control_dispatch_slow")
    assert {
        "handler_name": started.__dict__["handler_name"],
        "request_type": started.__dict__["request_type"],
        "request_action": started.__dict__["request_action"],
        "outcome": started.__dict__["outcome"],
    } == {
        "handler_name": "custody_control",
        "request_type": "ProfileWorkerRetireRequest",
        "request_action": "retire",
        "outcome": "started",
    }
    assert {
        "handler_name": slow.__dict__["handler_name"],
        "request_type": slow.__dict__["request_type"],
        "request_action": slow.__dict__["request_action"],
        "elapsed_seconds": slow.__dict__["elapsed_seconds"],
        "outcome": slow.__dict__["outcome"],
    } == {
        "handler_name": "custody_control",
        "request_type": "ProfileWorkerRetireRequest",
        "request_action": "retire",
        "elapsed_seconds": 0.75,
        "outcome": "completed",
    }
    assert "session_id" not in slow.__dict__ and str(session_id) not in repr(slow.__dict__)


def test_idle_custody_validation_keeps_worker_loop_responsive() -> None:
    """A storage-bound custody check must permit concurrent IPC task progress."""

    async def exercise() -> None:
        loop = asyncio.get_running_loop()
        stop, failed = asyncio.Event(), asyncio.Event()
        heartbeat = threading.Event()

        class Custody(_ServeCustody):
            @override
            def live_sessions(self) -> tuple[UUID, ...]:
                loop.call_soon_threadsafe(heartbeat.set)
                assert heartbeat.wait(2), "custody validation blocked the worker loop"
                loop.call_soon_threadsafe(stop.set)
                return ()

        await worker_service._expire_custody(
            stop,
            failed,
            cast(ProfileWorkerCustody, Custody()),
            cast(worker_service.WorkerSubmissionStaging, _IdleUploads()),
            cast(ProfileWorkerHumanLogin, _IdleHuman()),
            _handled(),
        )
        assert not failed.is_set()

    asyncio.run(exercise())


def _handled() -> asyncio.Event:
    """The wake a handled command leaves behind; expiry runs only after one."""
    changed = asyncio.Event()
    changed.set()
    return changed


def test_idle_custody_expiry_runs_only_at_a_deadline_or_a_handled_command() -> None:
    """Idle expiry must not tick: it waits for the next deadline or a command that changed custody."""

    async def exercise() -> None:
        stop, failed, changed = asyncio.Event(), asyncio.Event(), _handled()
        passes = 0
        # The first and third passes leave nothing to expire; the second leaves a lease due in 0.2 s.
        deadlines = iter((None, 0.2, None))

        class Custody(_ServeCustody):
            @override
            def live_sessions(self) -> tuple[UUID, ...]:
                nonlocal passes
                passes += 1
                return ()

            @override
            def seconds_until_expiry(self) -> float | None:
                return next(deadlines)

        async def settled(count: int) -> None:
            async def reached() -> None:
                while passes < count:
                    await asyncio.sleep(0.01)

            await asyncio.wait_for(reached(), timeout=5)

        expiry = asyncio.create_task(
            worker_service._expire_custody(
                stop,
                failed,
                cast(ProfileWorkerCustody, Custody()),
                cast(worker_service.WorkerSubmissionStaging, _IdleUploads()),
                cast(ProfileWorkerHumanLogin, _IdleHuman()),
                changed,
            )
        )
        await settled(1)
        await asyncio.sleep(0.5)
        assert passes == 1, "with nothing held, expiry waited for no deadline"
        changed.set()
        await settled(2)
        await settled(3)
        await asyncio.sleep(0.5)
        assert passes == 3, "after the deadline nothing is held, so expiry waits again"
        stop.set()
        await asyncio.wait_for(expiry, timeout=5)
        assert not failed.is_set()

    asyncio.run(exercise())


def test_idle_custody_failure_retains_original_error_and_fences_work() -> None:
    async def exercise() -> None:
        failure = OSError("custody observation failed")
        failed = asyncio.Event()

        class Custody(_ServeCustody):
            @override
            def live_sessions(self) -> tuple[UUID, ...]:
                raise failure

        with pytest.raises(OSError) as caught:
            await worker_service._expire_custody(
                asyncio.Event(),
                failed,
                cast(ProfileWorkerCustody, Custody()),
                cast(worker_service.WorkerSubmissionStaging, object()),
                cast(ProfileWorkerHumanLogin, object()),
                _handled(),
            )
        assert caught.value is failure
        assert failed.is_set()

    asyncio.run(exercise())


@pytest.mark.parametrize("failures", [1, 2])
@pytest.mark.parametrize("cancelled", [False, True])
@pytest.mark.parametrize("frame_kind", ["malformed", "control-transfer"])
@pytest.mark.parametrize("local_failure", [False, True])
def test_operation_frame_failure_keeps_actual_cleanup_owner_after_worker_loop_closes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failures: int,
    cancelled: bool,
    frame_kind: str,
    local_failure: bool,
) -> None:
    """Real frame decoding/serve/run retire a fault port, never a terminal task."""
    serve = worker_service._serve
    entry = _entry(monkeypatch, tmp_path)
    entered, release = threading.Event(), threading.Event()
    cancellation = asyncio.CancelledError("control cancelled during operation frame read")
    rejected_frame = b"J" + struct.pack("!I", 1) + b"{"
    if frame_kind == "control-transfer":
        framed = _Channel()
        framed.queue(
            ProfileWorkerRequest(
                root=ProfileWorkerLeaseTransferRequest(request_id=uuid4(), byte_count=2, payload_digest="a" * 64)
            )
        )
        rejected_frame = bytes(framed.incoming)

    class OperationChannel(_Channel):
        @override
        def read_exact(self, count: int, *, deadline: float) -> bytes:
            if cancelled and count == 5 and self.incoming == rejected_frame:
                entered.set()
                assert release.wait(5), "control did not settle the native operation read"
            return super().read_exact(count, deadline=deadline)

    class ControlChannel(_Channel):
        @override
        def read_ready(self) -> bool:
            if cancelled and entered.is_set():
                # Control's readiness wait ends in this cancellation only once the
                # operation's real read is in flight, so that read settles first.
                release.set()
                raise cancellation
            return super().read_ready()

    operation, control = OperationChannel(failures), ControlChannel()
    operation.incoming.extend(entry.operation.incoming)
    operation.incoming.extend(rejected_frame)
    control.incoming.extend(entry.control.incoming)
    entry.endpoints[0].channel = control
    entry.endpoints[1].channel = operation
    custody = _ServeCustody()
    custody.identity = entry.identity
    operations = _Operations(1 if local_failure else 0)
    human, uploads = _Release(), _Release()
    monkeypatch.setattr(worker, "ProfileWorkerCustody", lambda *_args, **_kwargs: custody)
    monkeypatch.setattr(worker, "ProfileWorkerOperationHost", lambda *_args, **_kwargs: operations)
    monkeypatch.setattr(worker, "ProfileWorkerHumanLogin", lambda *_args, **_kwargs: human)
    monkeypatch.setattr(worker_service, "WorkerSubmissionStaging", lambda: uploads)
    monkeypatch.setattr(worker_service, "_serve", serve)
    try:
        with pytest.raises((RefusalError, asyncio.CancelledError)) as caught:
            worker.run(entry.arguments)
    finally:
        release.set()
    if cancelled:
        assert caught.value is cancellation
    else:
        assert isinstance(caught.value, RefusalError)
        assert caught.value.reason is RefusalCode.UNAVAILABLE
    task_errors = caught.value.__dict__.get("worker_task_errors")
    assert isinstance(task_errors, tuple)
    frame_errors = [
        error for error in task_errors if isinstance(error, RefusalError) and error.reason is RefusalCode.INVALID_FRAME
    ]
    assert len(frame_errors) == 1
    cleanup = caught.value.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    assert operation.calls == 1 and not operation.closed
    assert custody.calls == control.calls == human.calls == uploads.calls == operations.calls == 1
    assert all(endpoint.calls == 1 and endpoint.closed for endpoint in entry.endpoints)
    # run has closed both original asyncio.run loops. A real channel release
    # must still retry off this thread instead of awaiting the terminal task.
    assert len(operation.close_threads) == 1
    assert operation.close_threads[0] != threading.get_ident()
    if failures == 2:
        with pytest.raises(AsyncResourceCleanupError) as retry:
            asyncio.run(cleanup.retry_cleanup())
        cleanup = retry.value
        assert operation.calls == 2 and not operation.closed
    asyncio.run(cleanup.retry_cleanup())
    asyncio.run(cleanup.retry_cleanup())
    assert operation.closed and operation.calls == failures + 1
    assert all(thread_id != threading.get_ident() for thread_id in operation.close_threads)
    assert custody.calls == control.calls == human.calls == uploads.calls == 1
    assert operations.closed and operations.calls == (2 if local_failure else 1)
    assert all(endpoint.calls == 1 for endpoint in entry.endpoints)


@pytest.mark.asyncio
async def test_serve_clean_stop_drains_once_and_keeps_native_and_custody_ownership_with_caller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class IdleRelease(_Release):
        def expire(self, *, live_sessions: tuple[UUID, ...] = ()) -> None:
            assert live_sessions == ()

        def seconds_until_expiry(self) -> float | None:
            return None

    control, operation = _Channel(), _Channel()
    control.queue(ProfileWorkerRequest(root=ProfileWorkerControlRequest(action="stop", request_id=uuid4())))
    custody, human, uploads = _ServeCustody(), IdleRelease(), IdleRelease()
    operations = _Operations(0)
    monkeypatch.setattr(worker_service, "WorkerSubmissionStaging", lambda: uploads)
    await worker_service._serve(
        cast(WorkerChannel, control),
        cast(WorkerChannel, operation),
        cast(ProfileWorkerCustody, custody),
        cast(ProfileWorkerHumanLogin, human),
        cast(ProfileWorkerOperationHost, operations),
    )
    assert operations.calls == human.calls == uploads.calls == 1
    assert operations.closed and human.closed and uploads.closed
    assert custody.calls == control.calls == operation.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failures", [1, 2])
async def test_serve_preserves_control_failure_retires_all_local_owners_and_leaves_custody_to_caller(
    monkeypatch: pytest.MonkeyPatch, failures: int
) -> None:
    primary = ValueError("synthetic control validation failure")
    control, operation = _Channel(read_failure=primary), _Channel()
    custody, human, uploads = _Release(), _Release(failures), _Release(failures)
    operations = _Operations(failures)
    monkeypatch.setattr(worker_service, "WorkerSubmissionStaging", lambda: uploads)
    with pytest.raises(ValueError) as caught:
        await worker_service._serve(
            cast(WorkerChannel, control),
            cast(WorkerChannel, operation),
            cast(ProfileWorkerCustody, custody),
            cast(ProfileWorkerHumanLogin, human),
            cast(ProfileWorkerOperationHost, operations),
        )
    assert caught.value is primary
    cleanup = primary.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    assert operations.calls == human.calls == uploads.calls == 1
    assert custody.calls == control.calls == operation.calls == 0
    if failures == 2:
        with pytest.raises(AsyncResourceCleanupError) as retry:
            await cleanup.retry_cleanup()
        cleanup = retry.value
    await cleanup.retry_cleanup()
    await cleanup.retry_cleanup()
    assert operations.calls == human.calls == uploads.calls == failures + 1
    assert operations.closed and human.closed and uploads.closed
    assert custody.calls == 0


@pytest.mark.asyncio
async def test_serve_repeated_cancellation_waits_for_cleanup_and_preserves_original_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = asyncio.CancelledError("original control cancellation")
    control, operation = _Channel(read_failure=primary), _Channel()
    custody, human, uploads = _Release(), _Release(1), _Release()
    entered, finish = asyncio.Event(), asyncio.Event()

    class PendingOperations(_Operations):
        @override
        async def close(self) -> OperationDrainResult:
            entered.set()
            await finish.wait()
            return await super().close()

    operations = PendingOperations(1)
    monkeypatch.setattr(worker_service, "WorkerSubmissionStaging", lambda: uploads)
    running = asyncio.create_task(
        worker_service._serve(
            cast(WorkerChannel, control),
            cast(WorkerChannel, operation),
            cast(ProfileWorkerCustody, custody),
            cast(ProfileWorkerHumanLogin, human),
            cast(ProfileWorkerOperationHost, operations),
        )
    )
    try:
        async with asyncio.timeout(5):
            await entered.wait()
            running.cancel("first late cancellation")
            await asyncio.sleep(0)
            running.cancel("second late cancellation")
            await asyncio.sleep(0)
            assert not running.done()
            finish.set()
            with pytest.raises(asyncio.CancelledError) as caught:
                await running
        assert caught.value is primary
        cleanup = primary.__dict__.get("cleanup_error")
        assert isinstance(cleanup, AsyncResourceCleanupError)
        assert operations.calls == human.calls == uploads.calls == 1
        assert uploads.closed and custody.calls == 0
        await cleanup.retry_cleanup()
        await cleanup.retry_cleanup()
        assert operations.calls == human.calls == 2 and uploads.calls == 1
    finally:
        finish.set()
        running.cancel()
        if not running.done():
            with suppress(asyncio.CancelledError):
                await running
