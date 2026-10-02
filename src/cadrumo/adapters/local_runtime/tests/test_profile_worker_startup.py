"""Owned child exit and absolute deadlines during worker startup acceptance."""

from __future__ import annotations

from collections import deque
from typing import override

import pytest

from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ..profile_worker import ProfileWorkerProcess
from ..windows import WindowsRuntimeChannel, WindowsRuntimeEndpoint
from ..windows_process import WindowsOwnedProcess

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _Clock:
    def __init__(self) -> None:
        self.elapsed = 0.0

    def __call__(self) -> float:
        return self.elapsed


class _Child(WindowsOwnedProcess):
    def __init__(self, *, exit_code: int | None = None, failure: Exception | None = None) -> None:
        self.exit_code = exit_code
        self.failure = failure
        self.wait_timeouts: list[float] = []

    @override
    def wait(self, *, timeout: float) -> int:
        self.wait_timeouts.append(timeout)
        if self.failure is not None:
            raise self.failure
        if self.exit_code is not None:
            return self.exit_code
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)


class _Channel(WindowsRuntimeChannel):
    def __init__(self) -> None:
        self.closed = False

    @override
    def close(self) -> None:
        self.closed = True


class _Endpoint(WindowsRuntimeEndpoint):
    def __init__(self, clock: _Clock, child: _Child, events: tuple[str | RuntimeRefusalCode, ...] = ()) -> None:
        self.clock = clock
        self.child = child
        self.events = deque(events)
        self.accept_timeouts: list[float] = []
        self.channel = _Channel()

    @override
    def accept(self, *, timeout: float = 5.0) -> WindowsRuntimeChannel:
        self.accept_timeouts.append(timeout)
        event = self.events.popleft() if self.events else "deadline"
        if event == "accepted":
            return self.channel
        if event == "accepted_exit":
            self.child.exit_code = 1
            return self.channel
        if isinstance(event, RuntimeRefusalCode):
            raise RuntimeRefusalError(event)
        self.clock.elapsed += timeout
        if event == "exit":
            self.child.exit_code = 1
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)


def _worker(child: _Child) -> ProfileWorkerProcess:
    worker = ProfileWorkerProcess.__new__(ProfileWorkerProcess)
    worker._process = child
    worker._pending_channel_cleanup = []
    return worker


@pytest.mark.parametrize("exit_code", [0, 1, 255])
def test_already_exited_child_is_connection_closed_before_accept(exit_code: int) -> None:
    clock = _Clock()
    child = _Child(exit_code=exit_code)
    endpoint = _Endpoint(clock, child)
    with pytest.raises(RuntimeRefusalError) as caught:
        _worker(child)._accept_startup_channel(endpoint, timeout=45, monotonic=clock)
    assert caught.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    assert endpoint.accept_timeouts == []
    assert child.wait_timeouts == [0]


def test_child_exit_during_accept_is_detected_after_first_timeout() -> None:
    clock = _Clock()
    child = _Child()
    endpoint = _Endpoint(clock, child, ("exit",))
    with pytest.raises(RuntimeRefusalError) as caught:
        _worker(child)._accept_startup_channel(endpoint, timeout=45, monotonic=clock)
    assert caught.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    assert clock.elapsed < 1
    assert len(endpoint.accept_timeouts) == 1
    assert set(child.wait_timeouts) == {0}


@pytest.mark.parametrize("timeout", [45.0, 10.0])
def test_alive_child_keeps_original_absolute_accept_deadline(timeout: float) -> None:
    clock = _Clock()
    child = _Child()
    endpoint = _Endpoint(clock, child)
    with pytest.raises(RuntimeRefusalError) as caught:
        _worker(child)._accept_startup_channel(endpoint, timeout=timeout, monotonic=clock)
    assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    assert clock.elapsed == pytest.approx(timeout)
    assert sum(endpoint.accept_timeouts) == pytest.approx(timeout)
    assert all(0 < duration <= 0.1 for duration in endpoint.accept_timeouts)
    assert set(child.wait_timeouts) == {0}


def test_healthy_child_can_connect_after_retryable_accept_timeouts() -> None:
    clock = _Clock()
    child = _Child()
    endpoint = _Endpoint(clock, child, ("deadline", "deadline", "accepted"))
    channel = _worker(child)._accept_startup_channel(endpoint, timeout=45, monotonic=clock)
    assert channel is endpoint.channel
    assert not endpoint.channel.closed
    assert clock.elapsed == pytest.approx(0.2)


def test_child_exit_with_new_connection_closes_accepted_channel() -> None:
    clock = _Clock()
    child = _Child()
    endpoint = _Endpoint(clock, child, ("accepted_exit",))
    with pytest.raises(RuntimeRefusalError) as caught:
        _worker(child)._accept_startup_channel(endpoint, timeout=10, monotonic=clock)
    assert caught.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    assert endpoint.channel.closed


@pytest.mark.parametrize(
    "failure", [RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE), OSError("owned process wait failed")]
)
def test_unexpected_process_error_is_preserved(failure: Exception) -> None:
    clock = _Clock()
    child = _Child(failure=failure)
    endpoint = _Endpoint(clock, child)
    with pytest.raises(type(failure)) as caught:
        _worker(child)._accept_startup_channel(endpoint, timeout=45, monotonic=clock)
    assert caught.value is failure
    assert not endpoint.accept_timeouts


def test_non_deadline_endpoint_error_is_preserved_without_retry() -> None:
    clock = _Clock()
    child = _Child()
    endpoint = _Endpoint(clock, child, (RuntimeRefusalCode.PEER_UNTRUSTED,))
    with pytest.raises(RuntimeRefusalError) as caught:
        _worker(child)._accept_startup_channel(endpoint, timeout=45, monotonic=clock)
    assert caught.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
    assert len(endpoint.accept_timeouts) == 1
