"""Owned child exit, stop and the timeout during worker startup acceptance."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from threading import RLock
from typing import override

import pytest

from cadrumo_client.contracts.contracts import ChannelWake, RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import DEFAULT_TIMEOUT_POLICY, OrchestrationTimeoutError
from cadrumo_client.transport.native_wake import NativeWake
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_client.transport.windows_channel import WindowsChannel
from cadrumo_client.transport.windows_process import WindowsOwnedProcess

from ..profile_worker import ProfileWorkerProcess

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

type _Event = str | RefusalCode | Exception | Callable[[], None]
"""What one scripted accept does: connect, refuse, fail, or run a signal first and then report an unmet wait."""


class _Child(WindowsOwnedProcess):
    def __init__(self, *, exit_code: int | None = None, failure: Exception | None = None) -> None:
        self.status = exit_code
        self.failure = failure
        self.wait_timeouts: list[float] = []

    @override
    def exit_code(self) -> int | None:
        return self.status

    @override
    def wait(self, *, timeout: float | None) -> int:
        assert timeout is not None, "profile worker startup must bound process waits"
        self.wait_timeouts.append(timeout)
        if self.failure is not None:
            raise self.failure
        if self.status is not None:
            return self.status
        raise RefusalError(RefusalCode.TIMEOUT)


class _Channel(WindowsChannel):
    def __init__(self) -> None:
        self.closed = False

    @override
    def close(self) -> None:
        self.closed = True


class _Endpoint(WindowsEndpoint):
    def __init__(self, child: _Child, events: tuple[_Event, ...] = ()) -> None:
        self.child = child
        self.events = deque(events)
        self.accept_timeouts: list[float | None] = []
        self.accept_wakes: list[tuple[ChannelWake, ...]] = []
        self.channel = _Channel()

    @override
    def accept(self, *, timeout: float | None = 5.0, wakes: tuple[ChannelWake, ...] = ()) -> WindowsChannel:
        self.accept_timeouts.append(timeout)
        self.accept_wakes.append(wakes)
        assert self.events, "the scripted endpoint was asked to accept more often than the test planned"
        event = self.events.popleft()
        if event == "accepted":
            return self.channel
        if event == "accepted_exit":
            self.child.status = 1
            return self.channel
        if isinstance(event, RefusalCode):
            raise RefusalError(event)
        if isinstance(event, Exception):
            raise event
        assert callable(event), event
        # A set wake ends the real endpoint's wait as an unmet deadline.
        event()
        raise RefusalError(RefusalCode.TIMEOUT)


def _worker(child: _Child) -> ProfileWorkerProcess:
    worker = ProfileWorkerProcess.__new__(ProfileWorkerProcess)
    worker._process = child
    worker._pending_channel_cleanup = []
    worker._native_guard = RLock()
    worker._native_activity_lock = RLock()
    worker._native_activity = None
    worker._stopping = NativeWake()
    worker._process_exited = NativeWake()
    worker._startup_expired = NativeWake()
    worker._owner_stopping = None
    return worker


def _accept(worker: ProfileWorkerProcess, endpoint: _Endpoint) -> WindowsChannel:
    channel = worker._accept_startup_channel(endpoint, deadline=DEFAULT_TIMEOUT_POLICY.deadline())
    assert isinstance(channel, WindowsChannel)
    return channel


@pytest.mark.parametrize("exit_code", [0, 1, 255])
def test_already_exited_child_is_connection_closed_before_accept(exit_code: int) -> None:
    child = _Child(exit_code=exit_code)
    endpoint = _Endpoint(child)
    with pytest.raises(RefusalError) as caught:
        _accept(_worker(child), endpoint)
    assert caught.value.reason is RefusalCode.CONNECTION_CLOSED
    assert endpoint.accept_timeouts == []
    assert child.wait_timeouts == [0]


def test_a_worker_stopped_before_accept_is_connection_closed_without_waiting() -> None:
    child = _Child()
    worker = _worker(child)
    worker._stopping.set()
    endpoint = _Endpoint(child)
    with pytest.raises(RefusalError) as caught:
        _accept(worker, endpoint)
    assert caught.value.reason is RefusalCode.CONNECTION_CLOSED
    assert endpoint.accept_timeouts == []


def test_an_expired_startup_timeout_is_refused_before_accept() -> None:
    child = _Child()
    worker = _worker(child)
    worker._startup_expired.set()
    endpoint = _Endpoint(child)
    with pytest.raises(RefusalError) as caught:
        _accept(worker, endpoint)
    assert caught.value.reason is RefusalCode.TIMEOUT
    assert endpoint.accept_timeouts == []


def test_accept_waits_on_the_workers_own_signals_without_a_timeout() -> None:
    child = _Child()
    worker = _worker(child)
    endpoint = _Endpoint(child, ("accepted",))
    assert _accept(worker, endpoint) is endpoint.channel
    assert endpoint.accept_timeouts == [None]
    assert endpoint.accept_wakes == [(worker._stopping, worker._process_exited, worker._startup_expired)]


def test_the_owner_stop_signal_is_one_more_wake_of_the_accept() -> None:
    child = _Child()
    worker = _worker(child)
    owner_stopping = NativeWake()
    worker._owner_stopping = owner_stopping
    endpoint = _Endpoint(child, ("accepted",))
    _accept(worker, endpoint)
    assert endpoint.accept_wakes == [
        (worker._stopping, worker._process_exited, worker._startup_expired, owner_stopping)
    ]


def test_child_exit_during_accept_is_connection_closed_after_one_wait() -> None:
    child = _Child()
    worker = _worker(child)

    def exit_child() -> None:
        child.status = 1
        worker._process_exited.set()

    endpoint = _Endpoint(child, (exit_child,))
    with pytest.raises(RefusalError) as caught:
        _accept(worker, endpoint)
    assert caught.value.reason is RefusalCode.CONNECTION_CLOSED
    assert endpoint.accept_timeouts == [None]
    assert child.wait_timeouts == [0]


def test_stopping_the_worker_during_accept_is_connection_closed() -> None:
    child = _Child()
    worker = _worker(child)
    endpoint = _Endpoint(child, (worker._stopping.set,))
    with pytest.raises(RefusalError) as caught:
        _accept(worker, endpoint)
    assert caught.value.reason is RefusalCode.CONNECTION_CLOSED
    assert endpoint.accept_timeouts == [None]


def test_the_owner_stopping_during_accept_is_connection_closed() -> None:
    child = _Child()
    worker = _worker(child)
    owner_stopping = NativeWake()
    worker._owner_stopping = owner_stopping
    endpoint = _Endpoint(child, (owner_stopping.set,))
    with pytest.raises(RefusalError) as caught:
        _accept(worker, endpoint)
    assert caught.value.reason is RefusalCode.CONNECTION_CLOSED


def test_the_startup_timeout_during_accept_is_the_timeout() -> None:
    child = _Child()
    worker = _worker(child)
    endpoint = _Endpoint(child, (worker._startup_expired.set,))
    with pytest.raises(RefusalError) as caught:
        _accept(worker, endpoint)
    assert caught.value.reason is RefusalCode.TIMEOUT
    assert endpoint.accept_timeouts == [None]


def test_an_endpoint_timeout_is_the_timeout() -> None:
    child = _Child()
    expired = OrchestrationTimeoutError("orchestration_timeout")
    endpoint = _Endpoint(child, (expired,))
    with pytest.raises(RefusalError) as caught:
        _accept(_worker(child), endpoint)
    assert caught.value.reason is RefusalCode.TIMEOUT
    assert caught.value.__cause__ is expired


def test_an_unmet_wait_no_signal_explains_stays_a_timeout() -> None:
    child = _Child()
    endpoint = _Endpoint(child, (lambda: None,))
    with pytest.raises(RefusalError) as caught:
        _accept(_worker(child), endpoint)
    assert caught.value.reason is RefusalCode.TIMEOUT
    assert endpoint.accept_timeouts == [None]


def test_healthy_child_connects_without_closing_the_channel() -> None:
    child = _Child()
    endpoint = _Endpoint(child, ("accepted",))
    assert _accept(_worker(child), endpoint) is endpoint.channel
    assert not endpoint.channel.closed


def test_child_exit_with_new_connection_closes_accepted_channel() -> None:
    child = _Child()
    endpoint = _Endpoint(child, ("accepted_exit",))
    with pytest.raises(RefusalError) as caught:
        _accept(_worker(child), endpoint)
    assert caught.value.reason is RefusalCode.CONNECTION_CLOSED
    assert endpoint.channel.closed


@pytest.mark.parametrize("failure", [RefusalError(RefusalCode.UNAVAILABLE), OSError("owned process wait failed")])
def test_unexpected_process_error_is_preserved(failure: Exception) -> None:
    child = _Child(failure=failure)
    endpoint = _Endpoint(child)
    with pytest.raises(type(failure)) as caught:
        _accept(_worker(child), endpoint)
    assert caught.value is failure
    assert not endpoint.accept_timeouts


def test_non_timeout_endpoint_error_is_preserved_without_retry() -> None:
    child = _Child()
    endpoint = _Endpoint(child, (RefusalCode.PEER_UNTRUSTED,))
    with pytest.raises(RefusalError) as caught:
        _accept(_worker(child), endpoint)
    assert caught.value.reason is RefusalCode.PEER_UNTRUSTED
    assert len(endpoint.accept_timeouts) == 1
