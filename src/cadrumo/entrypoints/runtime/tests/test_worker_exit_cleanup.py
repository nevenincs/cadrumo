"""Worker entrypoint/serve release faults; no native admission or execution claim."""

from __future__ import annotations

import asyncio
import struct
import sys
import threading
from contextlib import nullcontext, suppress
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.local_runtime.runtime_frame_io import write_document
from cadrumo.adapters.local_runtime.worker_transport import WorkerChannel, WorkerEndpoint
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.operations.drain import OperationDrainResult
from cadrumo.application.runtime.contracts import (
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from cadrumo.application.runtime.profile_worker import (
    ProfileWorkerContractRequest,
    ProfileWorkerControlRequest,
    ProfileWorkerIdentity,
    ProfileWorkerLeaseTransferRequest,
    ProfileWorkerRequest,
)
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.core.async_cleanup import AsyncResourceCleanupError
from cadrumo.entrypoints.runtime import worker, worker_service
from cadrumo.entrypoints.runtime.operation_host import ProfileWorkerOperationHost
from cadrumo.entrypoints.runtime.profile_login import ProfileWorkerHumanLogin

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_description_keeps_loop_responsive_and_retains_host_until_thread_settles() -> None:
    """A cancelled description cannot leave its host in use after cleanup."""

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        loop_thread = threading.get_ident()
        entered = asyncio.Event()
        release = threading.Event()
        finished = threading.Event()
        refusal = RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        request = ProfileWorkerContractRequest(
            request_id=uuid4(), session_id=uuid4(), definition_id="user-profile.field-mutation"
        )

        def describe(session_id: UUID, definition_id: str) -> None:
            assert threading.get_ident() != loop_thread
            assert (session_id, definition_id) == (request.session_id, request.definition_id)
            loop.call_soon_threadsafe(entered.set)
            release.wait()
            finished.set()
            raise refusal

        context = cast(
            worker_service._WorkerControl,
            SimpleNamespace(operations=SimpleNamespace(describe=describe)),
        )
        handler = asyncio.create_task(worker_service._handle_metadata_control(context, request))
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
            with suppress(asyncio.CancelledError, RuntimeRefusalError, AssertionError):
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
        self.peer = RuntimePeer(os_owner_id="synthetic-owner", process_id=41)
        self.incoming = bytearray()
        self.read_failure = read_failure

    def read_ready(self) -> bool:
        if self.read_failure is not None:
            raise self.read_failure
        return bool(self.incoming)

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        assert deadline > 0
        if self.read_failure is not None:
            raise self.read_failure
        if len(self.incoming) < count:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
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
            RuntimeServerHello(
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
        "typed": RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME),
        "unexpected": ValueError("synthetic worker body failure"),
        "cancelled": asyncio.CancelledError("synthetic worker cancellation"),
    }[body_kind]
    entry = _entry(monkeypatch, tmp_path, body_failure=primary)
    entry.custody.failures = failures
    entry.control.failures = failures
    with pytest.raises((AsyncResourceCleanupError, RuntimeRefusalError, ValueError, asyncio.CancelledError)) as caught:
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
    primary = RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) if refused else None
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
        RuntimeServerHello(
            product_version="wrong-cohort",
            storage_identity=entry.endpoints[0].storage_identity,
            boot_id=entry.identity.runtime_boot_id,
        )
    )
    entry.control.failures = 1
    with pytest.raises(RuntimeRefusalError) as caught:
        worker.run(entry.arguments)
    assert caught.value.reason is RuntimeRefusalCode.VERSION_MISMATCH
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

        class Uploads:
            def expire(self, *, live_sessions: tuple[UUID, ...]) -> None:
                assert live_sessions == ()

        class Human:
            def expire(self) -> None:
                pass

        await worker_service._expire_custody(
            stop,
            failed,
            cast(ProfileWorkerCustody, Custody()),
            cast(worker_service.WorkerSubmissionStaging, Uploads()),
            cast(ProfileWorkerHumanLogin, Human()),
        )
        assert not failed.is_set()

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
                # The event loop remains in this call until _serve cancels its
                # operation task, so that task settles the in-flight real read.
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
        with pytest.raises((RuntimeRefusalError, asyncio.CancelledError)) as caught:
            worker.run(entry.arguments)
    finally:
        release.set()
    if cancelled:
        assert caught.value is cancellation
    else:
        assert isinstance(caught.value, RuntimeRefusalError)
        assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
    task_errors = caught.value.__dict__.get("worker_task_errors")
    assert isinstance(task_errors, tuple)
    frame_errors = [
        error
        for error in task_errors
        if isinstance(error, RuntimeRefusalError) and error.reason is RuntimeRefusalCode.INVALID_FRAME
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
    control, operation = _Channel(), _Channel()
    control.queue(ProfileWorkerRequest(root=ProfileWorkerControlRequest(action="stop", request_id=uuid4())))
    custody, human, uploads = _ServeCustody(), _Release(), _Release()
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
