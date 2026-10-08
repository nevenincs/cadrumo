"""Faulted transport release keeps native owners until actual cleanup succeeds."""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event, get_ident
from typing import cast, override

import pytest

from cadrumo.application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeShutdownIncompleteError,
)
from cadrumo.core.async_cleanup import AsyncResourceCleanupError

from ..runtime_transport_cleanup import RuntimeTransportCleanup, close_runtime_transport_after_failure
from .retained_server import RetainedRuntimeTransportServer

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


class _Channel:
    def __init__(self, *, close_failures: int = 0, peer_failure: bool = False) -> None:
        self.close_failures, self.peer_failure = close_failures, peer_failure
        self.close_error = OSError("synthetic native channel release failure")
        self.close_attempts = 0
        self.closed = Event()

    @property
    def peer(self) -> RuntimePeer:
        if self.peer_failure:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        return RuntimePeer(os_owner_id="synthetic-owner", process_id=1)

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)

    def read_ready(self) -> bool:
        return False

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        raise AssertionError("a refused peer must receive no private write")

    def close(self) -> None:
        if self.closed.is_set():
            return
        self.close_attempts += 1
        if self.close_attempts <= self.close_failures:
            raise self.close_error
        self.closed.set()


class _Listener:
    storage_identity = "a" * 64

    def __init__(
        self, channel: _Channel, stop: Event, *, reject_on_accept: bool = False, close_failures: int = 0
    ) -> None:
        self.channel, self.stop, self.reject_on_accept = channel, stop, reject_on_accept
        self.accepted = False
        self.closed = Event()
        self.close_failures = close_failures
        self.close_attempts = 0
        self.close_threads: list[int] = []
        self.close_error = OSError("synthetic native listener release failure")

    def listen(self) -> None:
        pass

    def accept(self, *, timeout: float) -> RuntimeByteChannel:
        if self.accepted:
            self.stop.set()
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        self.accepted = True
        if self.reject_on_accept:
            self.stop.set()
        return self.channel

    def close(self) -> None:
        if self.closed.is_set():
            return
        self.close_attempts += 1
        self.close_threads.append(get_ident())
        if self.close_attempts <= self.close_failures:
            raise self.close_error
        self.closed.set()


def _server(channel: _Channel, *, reject: bool = False) -> tuple[RetainedRuntimeTransportServer, _Listener]:
    stop = Event()
    listener = _Listener(channel, stop, reject_on_accept=reject)
    return RetainedRuntimeTransportServer(listener, product_version="cleanup-test", stop=stop), listener


@pytest.mark.parametrize("reject", ["stopping", "capacity"])
def test_rejected_channel_failed_close_is_retried_before_listener_release(reject: str) -> None:
    channel = _Channel(close_failures=1)
    server, listener = _server(channel, reject=reject == "stopping")
    occupied = 0
    if reject == "capacity":
        while server._slots.acquire(blocking=False):
            occupied += 1
    try:
        with pytest.raises(OSError) as caught:
            server.serve()
        assert caught.value is channel.close_error
        assert channel.closed.is_set()
        assert listener.closed.is_set()
        assert channel.close_attempts == 2
    finally:
        for _ in range(occupied):
            server._slots.release()
        channel.close()


def test_failed_submission_preserves_exact_error_and_retries_its_native_owner() -> None:
    channel = _Channel(close_failures=1)
    stop = Event()
    listener = _Listener(channel, stop)
    submission_error = ValueError("synthetic executor admission failure")

    class FailedExecutor:
        def submit(self, *_args: object) -> Future[None]:
            stop.set()
            raise submission_error

    class FailedSubmissionServer(RetainedRuntimeTransportServer):
        @override
        def _accept_connections(self, workers: ThreadPoolExecutor) -> None:
            super()._accept_connections(cast(ThreadPoolExecutor, FailedExecutor()))

    server = FailedSubmissionServer(listener, product_version="cleanup-test", stop=stop)
    with pytest.raises(ValueError) as caught:
        server.serve()
    assert caught.value is submission_error
    assert isinstance(submission_error.__dict__.get("async_cleanup_error"), AsyncResourceCleanupError)
    assert channel.closed.is_set() and listener.closed.is_set()
    assert channel.close_attempts == 2
    assert server._slots.acquire(blocking=False)
    server._slots.release()


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["listen", "accept", "submit"])
@pytest.mark.parametrize("failure", ["ordinary", "refusal", "cancellation"])
@pytest.mark.parametrize("persistent", [False, True])
async def test_listener_failure_preserves_primary_and_retains_retry_owner(
    phase: str, failure: str, persistent: bool
) -> None:
    channel = _Channel(close_failures=1)
    stop = Event()
    primary: BaseException = (
        asyncio.CancelledError("synthetic cancellation")
        if failure == "cancellation"
        else RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if failure == "refusal"
        else ValueError("synthetic admission failure")
    )

    class FailedListener(_Listener):
        @override
        def listen(self) -> None:
            if phase == "listen":
                raise primary

        @override
        def accept(self, *, timeout: float) -> RuntimeByteChannel:
            if phase == "accept":
                close_runtime_transport_after_failure(channel, primary)
                raise primary
            return super().accept(timeout=timeout)

    class FailedExecutor:
        def submit(self, *_args: object) -> Future[None]:
            raise primary

    class FailedServer(RetainedRuntimeTransportServer):
        @override
        def _accept_connections(self, workers: ThreadPoolExecutor) -> None:
            super()._accept_connections(cast(ThreadPoolExecutor, FailedExecutor()) if phase == "submit" else workers)

    attempts = 2 if persistent else 1
    listener = FailedListener(channel, stop, close_failures=attempts)
    server = FailedServer(listener, product_version="cleanup-test", stop=stop)
    with pytest.raises(type(primary)) as caught:
        server.serve()
    assert caught.value is primary
    assert not listener.closed.is_set() and not server.ready.is_set()
    assert listener.close_attempts == 1
    cleanup = primary.__dict__.get("async_cleanup_error")
    assert isinstance(cleanup, AsyncResourceCleanupError)
    channel_attempts = channel.close_attempts
    assert channel_attempts == (0 if phase == "listen" else 2)
    if persistent:
        with pytest.raises(AsyncResourceCleanupError) as failed_retry:
            await cleanup.retry_cleanup()
        assert not listener.closed.is_set()
        cleanup = failed_retry.value
    await cleanup.retry_cleanup()
    assert listener.closed.is_set()
    assert listener.close_attempts == attempts + 1
    assert listener.close_threads[0] == get_ident()
    assert all(thread != get_ident() for thread in listener.close_threads[1:])
    await cleanup.retry_cleanup()
    assert listener.close_attempts == attempts + 1 and channel.close_attempts == channel_attempts


@pytest.mark.asyncio
@pytest.mark.parametrize("active_caller_error", [False, True])
async def test_clean_serve_listener_failure_has_its_own_retry_error(active_caller_error: bool) -> None:
    stop = Event()
    stop.set()
    listener = _Listener(_Channel(), stop, close_failures=1)
    server = RetainedRuntimeTransportServer(listener, product_version="cleanup-test", stop=stop)
    caller_error = ValueError("synthetic caller exception")
    if active_caller_error:
        try:
            raise caller_error
        except ValueError:
            with pytest.raises(AsyncResourceCleanupError) as caught:
                server.serve()
    else:
        with pytest.raises(AsyncResourceCleanupError) as caught:
            server.serve()
    assert caught.value.__cause__ is listener.close_error
    assert "async_cleanup_error" not in caller_error.__dict__
    assert not server.ready.is_set() and not listener.closed.is_set()
    assert listener.close_attempts == 1
    await caught.value.retry_cleanup()
    await caught.value.retry_cleanup()
    assert listener.closed.is_set() and listener.close_attempts == 2


@pytest.mark.parametrize("failure", ["peer_refusal", "unexpected"])
def test_accept_failure_transfers_unreturned_native_owner_before_mapping(failure: str) -> None:
    channel = _Channel(close_failures=1)
    stop = Event()
    primary: Exception = (
        RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        if failure == "peer_refusal"
        else ValueError("synthetic native peer construction failure")
    )

    class FailedAcceptListener(_Listener):
        @override
        def accept(self, *, timeout: float) -> RuntimeByteChannel:
            if self.accepted:
                return super().accept(timeout=timeout)
            self.accepted = True
            close_runtime_transport_after_failure(channel, primary)
            raise primary

    listener = FailedAcceptListener(channel, stop)
    server = RetainedRuntimeTransportServer(listener, product_version="cleanup-test", stop=stop)
    with pytest.raises(type(primary)) as caught:
        server.serve()
    assert caught.value is primary
    assert channel.closed.is_set() and listener.closed.is_set()
    assert channel.close_attempts == 2


@pytest.mark.parametrize("peer_failure", [False, True])
def test_connection_release_failure_fences_host_and_releases_its_slot(peer_failure: bool) -> None:
    channel = _Channel(close_failures=1, peer_failure=peer_failure)
    server, listener = _server(channel)
    assert server._slots.acquire(blocking=False)
    if peer_failure:
        with pytest.raises(OSError) as caught:
            server._connection(channel)
        assert caught.value is channel.close_error
    else:
        server._connection(channel)
    assert server.stop.is_set()
    assert not channel.closed.is_set()
    # The failed framing/native owner transfers to global drain, rather than
    # immediately issuing a second native close in the connection's finally.
    assert channel.close_attempts == 1
    acquired = 0
    try:
        while server._slots.acquire(blocking=False):
            acquired += 1
        assert acquired == 32
    finally:
        for _ in range(acquired):
            server._slots.release()
    with pytest.raises(RuntimeRefusalError) as caught:
        server.serve()
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
    assert channel.closed.is_set() and listener.closed.is_set()
    assert channel.close_attempts == 2


def test_terminal_request_with_unsettled_callback_retains_listener() -> None:
    stop, complete_work, callback_entered, release_callback, callback_settled = (
        Event(),
        Event(),
        Event(),
        Event(),
        Event(),
    )
    channel = _Channel()
    listener = _Listener(channel, stop)

    class CallbackServer(RetainedRuntimeTransportServer):
        @override
        def _accept_connections(self, workers: ThreadPoolExecutor) -> None:
            def request() -> None:
                assert complete_work.wait(2)

            future = workers.submit(request)
            self._requests.add(future)
            future.add_done_callback(self._forget_request)
            complete_work.set()
            assert callback_entered.wait(2)
            assert future.done()
            stop.set()

        @override
        def _forget_request(self, request: Future[None]) -> None:
            callback_entered.set()
            try:
                assert release_callback.wait(2)
                super()._forget_request(request)
            finally:
                callback_settled.set()

    server = CallbackServer(listener, product_version="cleanup-test", stop=stop)
    server.DRAIN_SECONDS = 0.1
    try:
        with pytest.raises(RuntimeShutdownIncompleteError) as caught:
            server.serve()
        assert not listener.closed.is_set()
        assert listener.close_attempts == 0
        assert "async_cleanup_error" not in caught.value.__dict__
        with pytest.raises(RuntimeShutdownIncompleteError):
            server.retry_drain(deadline=time.monotonic() + 0.05)
        assert listener.close_attempts == 0
    finally:
        release_callback.set()
        assert callback_settled.wait(2)
        server.retry_drain(deadline=time.monotonic() + 1)
        server.retry_drain(deadline=time.monotonic() + 1)
        assert listener.closed.is_set() and listener.close_attempts == 1


def test_drain_retry_before_serve_settles_keeps_listener_owned() -> None:
    server, listener = _server(_Channel())
    with pytest.raises(RuntimeShutdownIncompleteError):
        server.retry_drain(deadline=time.monotonic() + 0.05)
    assert not listener.closed.is_set() and listener.close_attempts == 0


def test_drain_retry_uses_remaining_deadline_for_concurrent_listener_cleanup() -> None:
    entered, release, stop = Event(), Event(), Event()
    stop.set()

    class HeldListener(_Listener):
        @override
        def close(self) -> None:
            if self.close_attempts > 0:
                entered.set()
                assert release.wait(2)
            super().close()

    listener = HeldListener(_Channel(), stop, close_failures=1)
    server = RetainedRuntimeTransportServer(listener, product_version="cleanup-test", stop=stop)
    with pytest.raises(AsyncResourceCleanupError) as caught:
        server.serve()
    cleanup = caught.value

    def retry() -> None:
        asyncio.run(cleanup.retry_cleanup())

    with ThreadPoolExecutor(max_workers=1) as executor:
        original = executor.submit(retry)
        try:
            assert entered.wait(2)
            deadline = time.monotonic() + 0.05
            with pytest.raises(AsyncResourceCleanupError):
                server.retry_drain(deadline=deadline)
            assert time.monotonic() < deadline + 0.5
            assert not listener.closed.is_set() and listener.close_attempts == 1
        finally:
            release.set()
            original.result(timeout=2)
    server.retry_drain(deadline=time.monotonic() + 1)
    assert listener.closed.is_set() and listener.close_attempts == 2


def test_cleanup_owner_lock_uses_remaining_absolute_drain_budget() -> None:
    entered, release = Event(), Event()

    class HeldChannel(_Channel):
        @override
        def close(self) -> None:
            entered.set()
            assert release.wait(2)
            super().close()

    channel = HeldChannel()
    owner = RuntimeTransportCleanup(channel)
    with ThreadPoolExecutor(max_workers=1) as pool:
        closing = pool.submit(owner.close_now)
        try:
            assert entered.wait(2)
            with pytest.raises(RuntimeRefusalError) as caught:
                owner.close_now(deadline=time.monotonic() + 0.05)
            assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
            assert not owner.released and not channel.closed.is_set()
        finally:
            release.set()
            closing.result(timeout=2)
    assert owner.released and channel.closed.is_set()
    owner.close_now()
    assert channel.close_attempts == 1
