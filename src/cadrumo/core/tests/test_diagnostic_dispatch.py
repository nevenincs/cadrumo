"""Diagnostic backpressure, callback failure and shutdown never borrow sink locks."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

import pytest

from ..diagnostic_dispatch import DiagnosticDispatch

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_blocked_callback_bounds_memory_and_drain_without_blocking_producers() -> None:
    entered, release = Event(), Event()

    def blocked(_: int) -> None:
        entered.set()
        assert release.wait(5)

    queue = DiagnosticDispatch(blocked, name="blocked-diagnostic-test", capacity=8)
    try:
        assert queue.submit(0)
        assert entered.wait(2)
        started = time.monotonic()
        admitted = sum(queue.submit(index) for index in range(10000))
        assert time.monotonic() - started < 0.5
        assert admitted == 8
        status = queue.status()
        assert status.pending == 9 and status.dropped == 9992
        assert not queue.flush(timeout=0.01)
        assert not queue.close(timeout=0.01)
        assert not queue.submit(10001)
    finally:
        release.set()
        assert queue.close(timeout=2)
    assert queue.status().completed == 9


def test_callback_failures_do_not_kill_delivery_or_escape_to_the_caller() -> None:
    received: list[int] = []

    def consume(value: int) -> None:
        if value == 1:
            raise RuntimeError("synthetic diagnostic failure")
        received.append(value)

    queue = DiagnosticDispatch(consume, name="failing-diagnostic-test")
    try:
        for value in range(3):
            assert queue.submit(value)
        assert queue.flush(timeout=2)
        assert received == [0, 2]
        assert queue.status().failed == 1
    finally:
        assert queue.close(timeout=2)


def test_concurrent_writers_preserve_each_admitted_record_exactly_once() -> None:
    received: list[tuple[int, int]] = []
    guard = Lock()

    def consume(value: tuple[int, int]) -> None:
        with guard:
            received.append(value)

    queue = DiagnosticDispatch(consume, name="threaded-diagnostic-test", capacity=4096)

    def write(writer: int) -> None:
        for index in range(100):
            assert queue.submit((writer, index))

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(write, range(8)))
        assert queue.flush(timeout=3)
        assert len(received) == len(set(received)) == 800
        for writer in range(8):
            assert [index for origin, index in received if origin == writer] == list(range(100))
        assert queue.status().failed == queue.status().dropped == 0
    finally:
        assert queue.close(timeout=2)


def test_callback_may_observe_status_and_cannot_wait_on_itself() -> None:
    def consume(_: int) -> None:
        assert queue.status().pending == 1
        assert not queue.flush(timeout=1)
        assert not queue.close(timeout=1)

    queue = DiagnosticDispatch(consume, name="recursive-diagnostic-test")
    assert queue.submit(1)
    assert queue.close(timeout=2)
    assert queue.status().failed == 0


def test_weight_bound_is_independent_of_the_record_count_bound() -> None:
    entered, release = Event(), Event()

    def consume(_: int) -> None:
        entered.set()
        assert release.wait(3)

    queue = DiagnosticDispatch(consume, name="weighted-diagnostic-test", capacity=100, maximum_weight=10)
    try:
        assert queue.submit(1, weight=7)
        assert entered.wait(2)
        assert not queue.submit(2, weight=4)
        assert queue.submit(3, weight=3)
        assert not queue.submit(4)
        assert queue.status().retained_weight == 10
    finally:
        release.set()
        assert queue.close(timeout=2)
    assert queue.status().retained_weight == 0


def test_concurrent_flushers_are_all_notified_after_delivery() -> None:
    release = Event()

    def consume(_: int) -> None:
        assert release.wait(3)

    queue = DiagnosticDispatch[int](consume, name="flush-diagnostic-test")
    try:
        assert queue.submit(1)
        with ThreadPoolExecutor(max_workers=16) as pool:
            waiters = [pool.submit(queue.flush, timeout=2) for _ in range(16)]
            release.set()
            assert all(waiter.result(timeout=3) for waiter in waiters)
    finally:
        release.set()
        assert queue.close(timeout=2)


def test_nonfinite_timeouts_never_wait_on_a_stuck_callback() -> None:
    entered, release = Event(), Event()

    def consume(_: int) -> None:
        entered.set()
        assert release.wait(3)

    queue = DiagnosticDispatch[int](consume, name="nonfinite-timeout-test")
    try:
        assert queue.submit(1) and entered.wait(2)
        started = time.monotonic()
        assert not queue.flush(timeout=float("inf"))
        assert not queue.close(timeout=float("nan"))
        assert time.monotonic() - started < 0.5
    finally:
        release.set()
        assert queue.close(timeout=2)


def test_process_change_replaces_inherited_lock_and_daemon_state() -> None:
    received: list[int] = []
    queue = DiagnosticDispatch[int](received.append, name="process-reset-test")
    assert queue.submit(1) and queue.close(timeout=2)
    inherited_guard = queue._guard
    inherited_guard.acquire()
    try:
        queue._pid = -1
        assert queue.submit(2) and queue.close(timeout=2)
        assert queue.status().accepted == queue.status().completed == 1
        assert received == [1, 2]
    finally:
        inherited_guard.release()
