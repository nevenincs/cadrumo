"""Tests for the cross-platform exclusive file-lock helper."""

from __future__ import annotations

import multiprocessing as mp
import os
import time
from pathlib import Path

import pytest

from . import LockAcquisitionError, exclusive_file_lock
from ._lock import _lock_path_for

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestSingleProcessAcquireRelease:
    """A single-process acquire-release round-trip works without contention."""

    def test_acquire_creates_lock_file(self, tmp_path: Path) -> None:
        target = tmp_path / "data.json"
        lock_path = _lock_path_for(target)
        with exclusive_file_lock(target):
            assert lock_path.exists()
        # Lock file is left on disk by design (TOCTOU avoidance).
        assert lock_path.exists()

    def test_yields_lock_path(self, tmp_path: Path) -> None:
        target = tmp_path / "data.json"
        with exclusive_file_lock(target) as lock_path:
            assert lock_path == _lock_path_for(target)

    def test_lock_released_on_normal_exit(self, tmp_path: Path) -> None:
        target = tmp_path / "data.json"
        with exclusive_file_lock(target):
            pass
        # Re-acquiring within the same process must succeed once the
        # previous context exited.
        with exclusive_file_lock(target):
            pass

    def test_lock_released_on_exception(self, tmp_path: Path) -> None:
        target = tmp_path / "data.json"

        class _BoomError(Exception):
            pass

        with pytest.raises(_BoomError), exclusive_file_lock(target):
            raise _BoomError
        # Lock must still be releasable.
        with exclusive_file_lock(target):
            pass

    def test_lock_file_inherits_parent_dir(self, tmp_path: Path) -> None:
        nested = tmp_path / "nested" / "deep"
        target = nested / "data.json"
        with exclusive_file_lock(target):
            assert (nested / "data.json.lock").exists()

    def test_negative_timeout_rejected(self, tmp_path: Path) -> None:
        target = tmp_path / "data.json"
        with pytest.raises(LockAcquisitionError), exclusive_file_lock(target, timeout=-1.0):
            pass

    def test_zero_timeout_succeeds_when_uncontested(self, tmp_path: Path) -> None:
        target = tmp_path / "data.json"
        with exclusive_file_lock(target, timeout=0.0):
            pass


def _hold_lock(target: str, hold_seconds: float, ready_event) -> None:
    """Worker entry: acquire the lock and hold it for ``hold_seconds``."""
    with exclusive_file_lock(Path(target)):
        ready_event.set()
        time.sleep(hold_seconds)


def _try_acquire(target: str, timeout: float, result_queue) -> None:
    """Worker entry: attempt to acquire the lock; report status to ``result_queue``."""
    try:
        with exclusive_file_lock(Path(target), timeout=timeout, retry_backoff=0.01):
            result_queue.put(("acquired", None))
    except LockAcquisitionError as exc:
        result_queue.put(("locked", str(exc)))


@pytest.mark.skipif(
    os.name == "nt" and "AEAT_RUN_LOCK_CONTENTION" not in os.environ,
    reason="Windows mp.spawn flaky in CI; opt-in via AEAT_RUN_LOCK_CONTENTION=1",
)
class TestCrossProcessContention:
    """Two real processes contending for the same lock follow the documented rules."""

    def _spawn_holder(self, target: Path, hold_seconds: float):
        ctx = mp.get_context("spawn")
        ready_event = ctx.Event()
        process = ctx.Process(
            target=_hold_lock,
            args=(str(target), hold_seconds, ready_event),
        )
        process.start()
        ready_event.wait(timeout=10.0)
        return process

    def test_second_acquirer_waits_then_succeeds(self, tmp_path: Path) -> None:
        target = tmp_path / "contended.json"
        ctx = mp.get_context("spawn")
        result_queue = ctx.Queue()
        holder = self._spawn_holder(target, hold_seconds=0.4)
        try:
            waiter = ctx.Process(
                target=_try_acquire,
                args=(str(target), 5.0, result_queue),
            )
            waiter.start()
            waiter.join(timeout=10.0)
            assert not waiter.is_alive()
            outcome, _detail = result_queue.get_nowait()
            assert outcome == "acquired"
        finally:
            holder.join(timeout=10.0)

    def test_short_timeout_raises_locked(self, tmp_path: Path) -> None:
        target = tmp_path / "contended.json"
        ctx = mp.get_context("spawn")
        result_queue = ctx.Queue()
        holder = self._spawn_holder(target, hold_seconds=2.0)
        try:
            waiter = ctx.Process(
                target=_try_acquire,
                args=(str(target), 0.2, result_queue),
            )
            waiter.start()
            waiter.join(timeout=10.0)
            assert not waiter.is_alive()
            outcome, detail = result_queue.get_nowait()
            assert outcome == "locked"
            assert "exclusive lock" in (detail or "")
        finally:
            holder.join(timeout=10.0)


class TestErrorCodeBinding:
    """``LockAcquisitionError`` binds to the registered LOCKED-category code."""

    def test_class_binds_to_registered_code(self) -> None:
        from ..errors._registry import bind_error_code

        bound = bind_error_code(LockAcquisitionError)
        assert bound.code == "LOCKED_STORAGE_LOCK_ACQUISITION"
        assert bound.category.value == "LOCKED"
        assert bound.retryable is True
