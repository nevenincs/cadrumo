"""``exclusive_file_lock_async`` waits without stalling the loop it runs on.

The synchronous primitive parks the calling thread in :func:`time.sleep`
until the lock frees. That is correct for a synchronous caller and wrong
for a coroutine: a UI poll worker awaiting a contended journal read
stalls every other task on the interface event loop, and cannot be
cancelled when the operator closes the surface.

Each property here is paired with the synchronous form measured through
the SAME harness, so a twin that quietly blocks is distinguishable from
one that yields. Without that pairing a responsiveness assertion passes
on any implementation fast enough to look instant.

Contention is real throughout: a second thread holds the OS lock through
the shipped synchronous primitive. Nothing is mocked, patched or faked.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import pytest

from ..locks import exclusive_file_lock, exclusive_file_lock_async
from ..locks_errors import LockAcquisitionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_HOLD_SECONDS = 0.4
"""How long the competing holder keeps the lock. Long enough that a blocked
loop is unambiguous, short enough to keep the suite quick."""

_TICK_SECONDS = 0.005
"""Ticker period. Over ``_HOLD_SECONDS`` a free loop turns many times."""

_RESPONSIVE_TICKS = 10
"""A free loop clears this comfortably; a blocked one cannot reach it."""


class _Holder:
    """Hold the real OS lock on a background thread for a bounded window."""

    def __init__(self, target: Path) -> None:
        self._target = target
        self._acquired = threading.Event()
        self._release = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        with exclusive_file_lock(self._target, timeout=5.0, retry_backoff=0.01):
            self._acquired.set()
            self._release.wait(timeout=10.0)

    def __enter__(self) -> _Holder:
        self._thread.start()
        assert self._acquired.wait(timeout=5.0), "the competing holder never acquired the lock"
        return self

    def __exit__(self, *_exc: object) -> None:
        self._release.set()
        self._thread.join(timeout=10.0)

    def release_after(self, seconds: float) -> None:
        """Free the lock from a timer thread, so the waiter really waits."""
        threading.Timer(seconds, self._release.set).start()


async def _count_ticks_during(work: object) -> tuple[int, object]:
    """Run ``work`` while a ticker turns, returning ticks observed and its result.

    The tick count is the responsiveness measurement: it can only advance
    if the loop scheduled something else while ``work`` was pending.
    """
    ticks = 0
    stop = False

    async def ticker() -> None:
        nonlocal ticks
        while not stop:
            ticks += 1
            await asyncio.sleep(_TICK_SECONDS)

    spinner = asyncio.ensure_future(ticker())
    await asyncio.sleep(0)
    baseline = ticks
    try:
        outcome = await work  # type: ignore[misc]
    finally:
        stop = True
        spinner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await spinner
    return ticks - baseline, outcome


def test_the_awaitable_acquisition_keeps_the_loop_turning_while_contended(tmp_path: Path) -> None:
    """A coroutine waiting on a held lock does not stop other loop work."""
    target = tmp_path / "resource.json"
    target.write_text("{}", encoding="utf-8")

    async def scenario() -> tuple[int, bool]:
        with _Holder(target) as holder:
            holder.release_after(_HOLD_SECONDS)

            async def acquire() -> bool:
                async with exclusive_file_lock_async(target, timeout=5.0, retry_backoff=0.01) as held:
                    return held.exists()

            ticks, acquired = await _count_ticks_during(acquire())
            return ticks, bool(acquired)

    ticks, acquired = asyncio.run(scenario())

    assert acquired, "the awaitable acquisition must still obtain the lock once it frees"
    assert ticks >= _RESPONSIVE_TICKS, (
        f"the event loop turned only {ticks} times while the lock was contended; "
        "the awaitable acquisition is blocking the loop"
    )


def test_the_synchronous_acquisition_stalls_the_same_loop(tmp_path: Path) -> None:
    """The paired control: this is the behaviour the twin exists to avoid.

    Without this, the responsiveness assertion above would pass against an
    implementation that never actually yields, because an uncontended
    acquire returns instantly either way.
    """
    target = tmp_path / "resource.json"
    target.write_text("{}", encoding="utf-8")

    async def scenario() -> tuple[int, bool]:
        with _Holder(target) as holder:
            holder.release_after(_HOLD_SECONDS)

            async def acquire_blocking() -> bool:
                with exclusive_file_lock(target, timeout=5.0, retry_backoff=0.01) as held:
                    return held.exists()

            ticks, acquired = await _count_ticks_during(acquire_blocking())
            return ticks, bool(acquired)

    ticks, acquired = asyncio.run(scenario())

    assert acquired, "the synchronous acquisition still obtains the lock"
    assert ticks < _RESPONSIVE_TICKS, (
        f"the synchronous acquisition let the loop turn {ticks} times; this control "
        "no longer demonstrates the blocking it exists to contrast against"
    )


def test_a_waiting_acquisition_is_cancellable(tmp_path: Path) -> None:
    """Closing a surface must abandon the wait, not ride out the timeout."""
    target = tmp_path / "resource.json"
    target.write_text("{}", encoding="utf-8")

    async def scenario() -> float:
        with _Holder(target):

            async def acquire() -> None:
                async with exclusive_file_lock_async(target, timeout=30.0, retry_backoff=0.01):
                    pytest.fail("the lock was held; this acquisition must not succeed")

            waiter = asyncio.ensure_future(acquire())
            await asyncio.sleep(_TICK_SECONDS * 4)
            started = time.monotonic()
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter
            return time.monotonic() - started

    elapsed = asyncio.run(scenario())

    assert elapsed < 1.0, (
        f"cancellation took {elapsed:.2f}s against a 30s acquire timeout; the wait is not a cancellation point"
    )


def test_the_awaitable_form_carries_the_same_refusals(tmp_path: Path) -> None:
    """One contract across both forms: same deadline, same bounds, same error."""
    target = tmp_path / "resource.json"
    target.write_text("{}", encoding="utf-8")

    async def timed_out() -> None:
        with _Holder(target):
            async with exclusive_file_lock_async(target, timeout=0.05, retry_backoff=0.01):
                pytest.fail("a held lock must not be acquired within the deadline")

    async def bad_backoff() -> None:
        async with exclusive_file_lock_async(target, timeout=0.1, retry_backoff=0):
            pytest.fail("an invalid retry backoff must not acquire the lock")

    with pytest.raises(LockAcquisitionError, match="failed to acquire exclusive lock"):
        asyncio.run(timed_out())

    with pytest.raises(LockAcquisitionError, match="retry_backoff"):
        asyncio.run(bad_backoff())
