"""Owned native-boundary fault ports; these cases do not prove OS transport."""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable, Generator
from logging import INFO, Handler, LogRecord
from typing import override
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeClientHello,
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeServerHello,
)
from cadrumo.core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from cadrumo.core.logging import get_logger

from .. import startup
from ..framing import VerifiedRuntimeConnection
from ..runtime_frame_io import write_document
from ..runtime_transport_cleanup import RuntimeTransportCleanup
from ..startup import RuntimeLaunchDoor

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class _BlockedChannel:
    """Hold native handshake/release until explicit owning events settle them."""

    def __init__(self, *, close_failures: int, foreign_version: bool = False) -> None:
        self.peer = RuntimePeer(os_owner_id="synthetic-owner", process_id=1)
        self.loop = asyncio.get_running_loop()
        self.started = asyncio.Event()
        self.close_started = asyncio.Event()
        self.release_handshake = threading.Event()
        self.release_close = threading.Event()
        self.inbound = bytearray()
        self.writes: list[bytes] = []
        self.close_calls = 0
        self.close_failures = close_failures
        self.close_threads: list[int] = []
        self.released = False
        write_document(
            self,
            RuntimeServerHello(
                product_version="foreign" if foreign_version else "cleanup-test",
                storage_identity="a" * 64,
                boot_id=uuid4(),
            ),
            deadline=time.monotonic() + 5,
        )
        self.inbound.extend(b"".join(self.writes))
        self.writes.clear()

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        self.loop.call_soon_threadsafe(self.started.set)
        assert self.release_handshake.wait(5), "test did not settle its held handshake"
        assert len(self.inbound) >= count
        result = bytes(self.inbound[:count])
        del self.inbound[:count]
        return result

    def read_ready(self) -> bool:
        return bool(self.inbound)

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        self.writes.append(bytes(payload))

    def close(self) -> None:
        self.close_threads.append(threading.get_ident())
        self.close_calls += 1
        self.loop.call_soon_threadsafe(self.close_started.set)
        assert self.release_close.wait(5), "test did not settle its held release"
        if self.close_calls <= self.close_failures:
            raise OSError("synthetic native release failure")
        self.released = True


class _Endpoint:
    storage_identity = "a" * 64

    def __init__(self, channel: _BlockedChannel) -> None:
        self.channel = channel

    def connect(self, *, timeout: float) -> _BlockedChannel:
        return self.channel


def _door(channel: _BlockedChannel) -> RuntimeLaunchDoor:
    return RuntimeLaunchDoor(
        _Endpoint(channel), expected=RuntimeClientHello(product_version="cleanup-test", storage_identity="a" * 64)
    )


def _cleanup(error: BaseException) -> AsyncResourceCleanupError:
    cleanup = error.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    return cleanup


@pytest.mark.asyncio
@pytest.mark.parametrize("deadline_mapping", [False, True], ids=["cancellation", "deadline"])
async def test_startup_adaptation_retains_transitive_owners_through_duplicates_and_cycle(
    deadline_mapping: bool,
) -> None:
    channels = (_BlockedChannel(close_failures=2), _BlockedChannel(close_failures=2))
    resources = tuple(RuntimeTransportCleanup(channel) for channel in channels)
    failures: list[AsyncResourceCleanupError] = []
    for channel, resource in zip(channels, resources, strict=True):
        channel.release_close.set()
        with pytest.raises(AsyncResourceCleanupError) as failed:
            await close_async_resources(resource, task_name="nested-startup-close", primary_error=None)
        failures.append(failed.value)
        assert failed.value.resources == (resource,)
        assert not resource.released

    body = RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
    outer = RuntimeError("synthetic outer cleanup")
    inner = RuntimeError("synthetic inner cleanup")
    body.__dict__["cleanup_error"] = outer
    outer.__dict__["body_error"] = inner
    outer.__dict__["cleanup_error"] = failures[0]
    inner.__dict__["async_cleanup_error"] = failures[0]
    inner.__dict__["cleanup_error"] = failures[1]
    inner.__dict__["body_error"] = body
    cancellation = asyncio.CancelledError("first cancellation")
    cancellation.__dict__["cleanup_error"] = body
    cancellation.__cause__ = body
    timeout = TimeoutError()
    timeout.__cause__ = cancellation
    primary: BaseException = cancellation
    if deadline_mapping:
        primary = RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        primary.__cause__ = timeout
    original_cause = primary.__cause__

    startup._carry_cleanup_owner(primary, cancellation)

    with pytest.raises(type(primary)) as caught:
        raise primary
    assert caught.value is primary
    assert primary.__cause__ is original_cause
    assert timeout.__cause__ is cancellation
    assert cancellation.__cause__ is body
    assert cancellation.__dict__["cleanup_error"] is body
    assert body.reason is RuntimeRefusalCode.VERSION_MISMATCH
    if isinstance(primary, RuntimeRefusalError):
        assert primary.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    else:
        assert primary.args == ("first cancellation",)
    cleanup = _cleanup(primary)
    assert len(cleanup.resources) == 2
    assert {id(resource) for resource in cleanup.resources} == {id(resource) for resource in resources}

    with pytest.raises(AsyncResourceCleanupError) as retry_failed:
        await cleanup.retry_cleanup()
    retained = retry_failed.value
    assert len(retained.resources) == 2
    assert {id(resource) for resource in retained.resources} == {id(resource) for resource in resources}
    assert all(not resource.released for resource in resources)
    assert all(channel.close_calls == 2 and not channel.released for channel in channels)
    await retained.retry_cleanup()
    assert all(resource.released for resource in resources)
    assert all(channel.close_calls == 3 and channel.released for channel in channels)
    await retained.retry_cleanup()
    assert all(channel.close_calls == 3 for channel in channels)
    assert all(identity != threading.get_ident() for channel in channels for identity in channel.close_threads)


@pytest.mark.asyncio
@pytest.mark.parametrize("close_failures", [1, 2])
async def test_repeated_cancel_retains_late_connection_failed_release_off_event_loop(close_failures: int) -> None:
    channel = _BlockedChannel(close_failures=close_failures)
    opening = asyncio.create_task(_door(channel).open(timeout=5))
    try:
        await asyncio.wait_for(channel.started.wait(), timeout=2)
        opening.cancel("first cancellation")
        channel.release_handshake.set()
        await asyncio.wait_for(channel.close_started.wait(), timeout=2)
        assert not opening.done()
        assert all(identity != threading.get_ident() for identity in channel.close_threads)
        opening.cancel("second cancellation")
        channel.release_close.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await opening
        assert caught.value.args == ("first cancellation",)
        assert channel.close_calls == 1
        cleanup = _cleanup(caught.value)
        if close_failures == 2:
            with pytest.raises(AsyncResourceCleanupError) as retry_failed:
                await cleanup.retry_cleanup()
            assert not channel.released
            cleanup = retry_failed.value
        await cleanup.retry_cleanup()
        await cleanup.retry_cleanup()
        assert channel.close_calls == close_failures + 1
        assert channel.released
        assert all(identity != threading.get_ident() for identity in channel.close_threads)
    finally:
        channel.release_handshake.set()
        channel.release_close.set()
        if not opening.done():
            opening.cancel()
            with pytest.raises(asyncio.CancelledError):
                await opening


@pytest.mark.asyncio
async def test_cancelled_rejected_handshake_adopts_nested_failed_owner() -> None:
    channel = _BlockedChannel(close_failures=1, foreign_version=True)
    opening = asyncio.create_task(_door(channel).open(timeout=5))
    try:
        await asyncio.wait_for(channel.started.wait(), timeout=2)
        opening.cancel("cancelled admission")
        channel.release_handshake.set()
        await asyncio.wait_for(channel.close_started.wait(), timeout=2)
        channel.release_close.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await opening
        body = caught.value.__dict__.get("cleanup_error")
        assert isinstance(body, RuntimeRefusalError)
        assert body.reason is RuntimeRefusalCode.VERSION_MISMATCH
        assert _cleanup(caught.value) is _cleanup(body)
        await _cleanup(caught.value).retry_cleanup()
        assert channel.released
        assert channel.close_calls == 2
    finally:
        channel.release_handshake.set()
        channel.release_close.set()
        if not opening.done():
            opening.cancel()
            with pytest.raises(asyncio.CancelledError):
                await opening


@pytest.mark.asyncio
async def test_deadline_mapping_preserves_cause_and_retryable_late_connection_owner() -> None:
    channel = _BlockedChannel(close_failures=1)
    channel.release_close.set()
    # The actual asyncio timeout fires first. A separate timer then settles
    # the deliberately held native port, as a late native completion would.
    release = asyncio.get_running_loop().call_later(0.1, channel.release_handshake.set)
    try:
        with pytest.raises(RuntimeRefusalError) as caught:
            await _door(channel).open(timeout=0.05)
        assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
        assert isinstance(caught.value.__cause__, TimeoutError)
        cancellation = caught.value.__cause__.__cause__
        assert isinstance(cancellation, asyncio.CancelledError)
        assert _cleanup(caught.value) is _cleanup(cancellation)
        assert channel.close_calls == 1
        await _cleanup(caught.value).retry_cleanup()
        assert channel.released
        assert channel.close_calls == 2
    finally:
        release.cancel()
        channel.release_handshake.set()
        channel.release_close.set()


class _DiagnosticFailureHandler(Handler):
    """Isolated real handler fault controlled by native-port state."""

    def __init__(self, failure: BaseException, armed: Callable[[], bool]) -> None:
        super().__init__()
        self.failure = failure
        self.armed = armed
        self.failure_calls = 0

    @override
    def emit(self, record: LogRecord) -> None:
        if (
            record.__dict__.get("startup_phase") == "existing_connect"
            and record.__dict__.get("transition") == "leave"
            and self.armed()
        ):
            self.failure_calls += 1
            raise self.failure


class _RefusingStartupEndpoint:
    storage_identity = "a" * 64

    def __init__(self) -> None:
        self.connect_calls = 0

    def connect(self, *, timeout: float) -> RuntimeByteChannel:
        self.connect_calls += 1
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_NOT_READY)


type _FaultHandlerFactory = Callable[[BaseException, Callable[[], bool]], _DiagnosticFailureHandler]


@pytest.fixture
def fault_handler(monkeypatch: pytest.MonkeyPatch) -> Generator[_FaultHandlerFactory]:
    """Keep handler faults local to this module-boundary port, never root logging."""
    logger = get_logger("cadrumo.tests.launch_door_diagnostic_fault")
    previous_level, previous_propagate = logger.level, logger.propagate
    logger.setLevel(INFO)
    logger.propagate = False
    handlers: list[_DiagnosticFailureHandler] = []

    def install(failure: BaseException, armed: Callable[[], bool]) -> _DiagnosticFailureHandler:
        handler = _DiagnosticFailureHandler(failure, armed)
        handlers.append(handler)
        logger.addHandler(handler)
        return handler

    monkeypatch.setattr(startup, "_LOGGER", logger)
    try:
        yield install
    finally:
        for handler in handlers:
            logger.removeHandler(handler)
            handler.close()
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate


@pytest.mark.asyncio
async def test_successful_connection_diagnostic_interruption_retains_failed_release(
    fault_handler: _FaultHandlerFactory,
) -> None:
    channel = _BlockedChannel(close_failures=1)
    channel.release_handshake.set()
    channel.release_close.set()
    interruption = KeyboardInterrupt("synthetic diagnostic interruption")
    handler = fault_handler(interruption, lambda: not channel.inbound)
    with pytest.raises(KeyboardInterrupt) as caught:
        await _door(channel).open(timeout=5)
    assert caught.value is interruption
    assert handler.failure_calls == 1
    assert channel.close_calls == 1
    assert not channel.released
    cleanup = _cleanup(caught.value)
    assert len(cleanup.resources) == 1
    owner = cleanup.resources[0]
    assert isinstance(owner, RuntimeTransportCleanup)
    assert isinstance(owner.resource, VerifiedRuntimeConnection)
    assert not owner.released
    await cleanup.retry_cleanup()
    assert channel.released
    assert owner.released
    assert channel.close_calls == 2
    assert all(thread != threading.get_ident() for thread in channel.close_threads)
    await cleanup.retry_cleanup()
    assert channel.close_calls == 2
