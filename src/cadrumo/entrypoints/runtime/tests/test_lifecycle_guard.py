"""Lifecycle ownership, default lock semantics and real FIFO poll handoffs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import TIMEOUT_MAX, Event

import pytest

from ....core.errors.hierarchy import InternalInvariantError
from ..lifecycle_guard import RuntimeLifecycleGuard

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_reentrant_owner_retains_exclusion_and_foreign_release_cannot_drop_it() -> None:
    guard = RuntimeLifecycleGuard()
    assert guard.acquire_poll()
    assert guard.acquire(blocking=False)
    assert guard.acquire_delete()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(InternalInvariantError, match="cannot release un-acquired lock"):
            pool.submit(guard.release).result()
        assert not pool.submit(guard.acquire, False).result()
        guard.release()
        guard.release()
        assert not pool.submit(guard.acquire_poll).result()
        guard.release()
        assert pool.submit(guard.acquire_delete).result()
        pool.submit(guard.release).result()
    with pytest.raises(InternalInvariantError, match="cannot release un-acquired lock"):
        guard.release()


@pytest.mark.parametrize("timeout", [-1, TIMEOUT_MAX])
def test_default_wait_uses_owned_release_and_the_supplied_timeout(
    monkeypatch: pytest.MonkeyPatch, timeout: float
) -> None:
    guard = RuntimeLifecycleGuard()
    assert guard.acquire()
    observations: Queue[str] = Queue()
    original_wait = guard._condition.wait

    def observed_wait(timeout: float | None = None) -> bool:
        observations.put("waiting")
        return original_wait(timeout)

    monkeypatch.setattr(guard._condition, "wait", observed_wait)

    def acquire_and_release() -> bool:
        admitted = guard.acquire(timeout=timeout)
        if admitted:
            guard.release()
        return admitted

    with ThreadPoolExecutor(max_workers=1) as pool:
        waiting = pool.submit(acquire_and_release)
        waiting.add_done_callback(lambda _future: observations.put("finished"))
        try:
            observation = observations.get()
            if observation != "waiting":
                waiting.result()
            assert observation == "waiting"
        finally:
            guard.release()
        assert waiting.result()
    assert guard.acquire_poll()
    guard.release()


def test_default_zero_timeout_and_nonblocking_calls_preserve_exclusive_busy_result() -> None:
    guard = RuntimeLifecycleGuard()
    assert guard.acquire()
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert not pool.submit(guard.acquire, timeout=0).result()
        assert not pool.submit(guard.acquire, blocking=False).result()
    guard.release()
    assert guard.acquire(timeout=0)
    guard.release()


def test_poll_and_nonblocking_close_do_not_wait_on_condition_bookkeeping() -> None:
    guard = RuntimeLifecycleGuard()
    with guard._condition, ThreadPoolExecutor(max_workers=1) as pool:
        assert not pool.submit(guard.acquire_poll).result()
        assert not pool.submit(guard.acquire, blocking=False).result()
        assert not pool.submit(guard.acquire, timeout=0).result()
    assert guard.acquire_poll()
    guard.release()


@pytest.mark.parametrize("case", ["nonblocking_timeout", "negative", "overflow"])
def test_default_acquire_refuses_invalid_native_lock_timeout_inputs(case: str) -> None:
    guard = RuntimeLifecycleGuard()
    if case == "overflow":
        with pytest.raises(OverflowError):
            guard.acquire(timeout=TIMEOUT_MAX * 2)
    elif case == "negative":
        with pytest.raises(ValueError):
            guard.acquire(timeout=-2)
    else:
        with pytest.raises(ValueError):
            guard.acquire(blocking=False, timeout=0)
    assert guard.acquire_poll()
    guard.release()


def test_actual_poll_transfers_registered_deletes_fifo_and_new_poll_cannot_starve_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = RuntimeLifecycleGuard()
    assert guard.acquire_poll()
    registered: Queue[int] = Queue()
    acquired: Queue[tuple[str, int]] = Queue()
    release = [Event(), Event(), Event()]
    original_wait = guard._condition.wait

    def observed_wait(timeout: float | None = None) -> bool:
        registered.put(len(guard._delete_waiters))
        return original_wait(timeout)

    monkeypatch.setattr(guard._condition, "wait", observed_wait)

    def delete(index: int) -> bool:
        admitted = guard.acquire_delete()
        if admitted:
            try:
                acquired.put(("acquired", index))
                release[index].wait()
            finally:
                guard.release()
        return admitted

    poll_owned = True
    with ThreadPoolExecutor(max_workers=3) as pool:
        waiting = []
        try:
            for index in range(3):
                waiting.append(pool.submit(delete, index))
                waiting[-1].add_done_callback(lambda _future: registered.put(-1))
                waiting[-1].add_done_callback(lambda _future, completed=index: acquired.put(("finished", completed)))
                count = registered.get()
                if count == -1:
                    waiting[-1].result()
                assert count == index + 1
            guard.release()
            poll_owned = False
            for index in range(3):
                while True:
                    outcome, observed = acquired.get()
                    if outcome == "acquired":
                        assert observed == index
                        break
                    if observed >= index:
                        waiting[observed].result()
                        pytest.fail("delete completed before its owned handoff was observed")
                    assert waiting[observed].result()
                assert not guard.acquire_poll()
                # A new custody caller cannot extend the registered poll batch.
                assert not guard.acquire_delete()
                release[index].set()
                assert waiting[index].result()
        finally:
            if poll_owned:
                guard.release()
            for ready in release:
                ready.set()
    # New delete requests cannot starve later polling after the finite handoff batch.
    assert guard.acquire_poll()
    guard.release()


@pytest.mark.parametrize("owner", ["exclusive", "delete"])
def test_fresh_delete_colliding_with_real_exclusive_custody_or_close_owner_refuses(owner: str) -> None:
    guard = RuntimeLifecycleGuard()
    assert guard.acquire() if owner == "exclusive" else guard.acquire_delete()
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert not pool.submit(guard.acquire_delete).result()
        assert not pool.submit(guard.acquire_poll).result()
    guard.release()
    assert guard.acquire_delete()
    guard.release()


@pytest.mark.parametrize("interruption", ["waiting", "granted"])
def test_interrupted_delete_removes_only_its_ticket_or_settles_its_granted_handoff(
    monkeypatch: pytest.MonkeyPatch, interruption: str
) -> None:
    guard = RuntimeLifecycleGuard()
    assert guard.acquire_poll()
    observations: Queue[str] = Queue()
    original_wait = guard._condition.wait

    def interrupted_wait(timeout: float | None = None) -> bool:
        observations.put("waiting")
        if interruption == "granted":
            original_wait(timeout)
        raise LookupError("injected lifecycle waiter interruption")

    monkeypatch.setattr(guard._condition, "wait", interrupted_wait)
    with ThreadPoolExecutor(max_workers=1) as pool:
        waiting = pool.submit(guard.acquire_delete)
        waiting.add_done_callback(lambda _future: observations.put("finished"))
        try:
            observation = observations.get()
            assert observation == "waiting"
        finally:
            guard.release()
        with pytest.raises(LookupError, match="injected lifecycle waiter interruption"):
            waiting.result()
    assert guard.acquire_poll()
    guard.release()


@pytest.mark.parametrize("owner", ["poll", "delete", "exclusive"])
def test_owned_reentry_ignores_foreign_monitor_bookkeeping_but_validates_native_arguments(
    owner: str,
) -> None:
    guard = RuntimeLifecycleGuard()
    if owner == "poll":
        assert guard.acquire_poll()
    elif owner == "delete":
        assert guard.acquire_delete()
    else:
        assert guard.acquire()
    held: Queue[str] = Queue()
    release_monitor = Event()
    owned_depth = 1

    def hold_foreign_monitor() -> None:
        with guard._condition:
            held.put("monitor_held")
            release_monitor.wait()

    def acquire_and_release_poll() -> bool:
        admitted = guard.acquire_poll()
        if admitted:
            guard.release()
        return admitted

    with ThreadPoolExecutor(max_workers=1) as pool:
        bookkeeping = pool.submit(hold_foreign_monitor)
        bookkeeping.add_done_callback(lambda _future: held.put("finished"))
        try:
            observation = held.get()
            if observation != "monitor_held":
                bookkeeping.result()
            assert observation == "monitor_held"
            # This same logical owner must not contend with foreign metadata bookkeeping.
            assert guard.acquire(blocking=False)
            owned_depth += 1
            assert guard.acquire(timeout=0)
            owned_depth += 1
            assert guard.acquire_poll()
            owned_depth += 1
            assert guard.acquire_delete()
            owned_depth += 1
            assert guard.acquire()
            owned_depth += 1
            assert guard.acquire(timeout=TIMEOUT_MAX)
            owned_depth += 1
            # Native argument errors must occur before any reentrant depth increment.
            with pytest.raises(ValueError):
                guard.acquire(blocking=False, timeout=0)
            with pytest.raises(ValueError):
                guard.acquire(timeout=-2)
            with pytest.raises(OverflowError):
                guard.acquire(timeout=TIMEOUT_MAX * 2)
        finally:
            release_monitor.set()
            bookkeeping.result()
            for _ in range(owned_depth):
                guard.release()
        # A foreign poll acquiring after exactly the successful releases proves no hidden depth.
        assert pool.submit(acquire_and_release_poll).result()
