"""Tests for the per-bucket ``.lock`` concurrency primitive."""

from __future__ import annotations

import logging
import multiprocessing
import os
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from multiprocessing.process import BaseProcess
from multiprocessing.queues import Queue
from pathlib import Path
from typing import Protocol, runtime_checkable

import pytest

from ......core.errors import build_error_envelope
from ......core.external_constants import UTF_8_ENCODING
from .._errors import BucketBusyError, BucketValidationError
from .._layout import (
    bucket_paths,
    provision_bucket_directory,
)
from .._lockfile import (
    acquire_lock,
    lock_path,
    release_lock,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@runtime_checkable
class _ProcessFactory(Protocol):
    def __call__(
        self,
        *,
        target: Callable[..., None],
        args: tuple[object, ...],
    ) -> BaseProcess: ...


@runtime_checkable
class _ProcessContext(Protocol):
    """Context surface required to construct one child lock contender."""

    Process: _ProcessFactory


def _holder_script(bucket_dir: Path, hold_seconds: float, ready_path: Path) -> str:
    """Render a subprocess script that acquires the lock and holds it."""

    return textwrap.dedent(
        f"""
        import sys, time
        from pathlib import Path
        sys.path.insert(0, {str(Path(__file__).resolve().parents[5])!r})
        from cadrumo.adapters.persistence.storage.bucket._layout import bucket_paths
        from cadrumo.adapters.persistence.storage.bucket._lockfile import (
            acquire_lock,
            release_lock,
        )

        paths = bucket_paths(Path({str(bucket_dir.parent.parent)!r}), {bucket_dir.name!r})
        acquire_lock(paths)
        Path({str(ready_path)!r}).write_text("ready", encoding={UTF_8_ENCODING!r})
        time.sleep({hold_seconds!r})
        release_lock(paths)
        """,
    )


@cache
def _bare_interpreter_spawn_seconds() -> float:
    """Return this host's CURRENT cost of spawning a bare interpreter.

    Measured rather than assumed, and measured now rather than at authoring
    time, so the readiness budget below tracks load instead of encoding one
    machine's idle speed. Cached: the baseline is a property of the host, not
    of any single test.
    """
    started = time.monotonic()
    subprocess.run(
        [sys.executable, "-c", "import sys"],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return time.monotonic() - started


def _readiness_budget_seconds() -> float:
    """Return a load-proportional ceiling for a holder to signal readiness.

    This is a HANG GUARD, not a latency assertion -- the same distinction
    :func:`test_wait_seconds_eventually_acquires` already draws for its own
    wait, whose budget was widened to 30s after a tight one produced false
    timeouts unrelated to the contract under test. The readiness wait covers
    strictly MORE work than that one (a fresh interpreter, the storage-bucket
    import chain, and a lock acquisition), so a fixed 5s ceiling was the
    tighter of the two on the heavier operation: on a saturated shared box the
    holder is descheduled well past it and the test fails for the schedule
    rather than for the lock contract.

    The floor keeps a quiet machine from deriving an implausibly small budget;
    the multiple of the measured spawn cost is what carries a loaded one.
    """
    return max(30.0, _bare_interpreter_spawn_seconds() * 40.0)


def _wait_for_ready(ready_path: Path, process: subprocess.Popen[bytes], *, timeout: float | None = None) -> None:
    """Block until the holder signals readiness, it dies, or the guard expires.

    Polling the process is what keeps the widened budget safe: a holder that
    crashed on import would otherwise burn the whole window and then report a
    timeout, hiding the real cause. Its exit code is surfaced immediately
    instead.
    """
    budget = _readiness_budget_seconds() if timeout is None else timeout
    deadline = time.monotonic() + budget
    while time.monotonic() < deadline:
        if ready_path.is_file():
            return
        exit_code = process.poll()
        if exit_code is not None:
            raise AssertionError(f"holder subprocess exited with code {exit_code} before signalling readiness")
        time.sleep(0.05)
    raise AssertionError(f"subprocess did not signal readiness within {budget:.1f}s")


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _attempt_lock_in_child(
    root: str,
    bucket_id: str,
    results: Queue[tuple[str, int]],
) -> None:
    paths = bucket_paths(Path(root), bucket_id)
    try:
        acquire_lock(paths, wait_seconds=0.05)
    except BucketBusyError as exc:
        results.put(("busy", exc.holding_pid))
        return
    results.put(("acquired", os.getpid()))
    release_lock(paths)


def test_acquire_then_release_round_trip(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")

    acquire_lock(paths)
    try:
        target = lock_path(paths)
        assert target.is_file()
        assert int(target.read_text(encoding=UTF_8_ENCODING).strip()) == os.getpid()
        if os.name == "posix":
            assert target.stat().st_mode & 0o777 == 0o600
    finally:
        release_lock(paths)

    assert not lock_path(paths).exists()


def test_same_thread_reentrant_acquire_releases_only_at_final_depth(
    tmp_path: Path,
) -> None:
    """Nested ownership composes production writers onto one lockfile."""

    paths = provision_bucket_directory(tmp_path, "alpha")
    acquire_lock(paths)
    acquire_lock(paths)

    release_lock(paths)
    assert lock_path(paths).is_file()

    release_lock(paths)
    assert lock_path(paths).exists() is False


def test_different_thread_cannot_reenter_same_process_lock(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    acquire_lock(paths)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            blocked = executor.submit(acquire_lock, paths, wait_seconds=0.05)
            with pytest.raises(BucketBusyError) as excinfo:
                blocked.result(timeout=5)
        assert excinfo.value.bucket_id == "alpha"
        assert excinfo.value.holding_pid == os.getpid()
        assert lock_path(paths).is_file()
    finally:
        release_lock(paths)


def test_missing_bucket_lock_target_is_not_materialized(tmp_path: Path) -> None:
    paths = bucket_paths(tmp_path, "missing")

    with pytest.raises(BucketValidationError) as excinfo:
        acquire_lock(paths)

    assert excinfo.value.context == {
        "reason": "bucket_dir_missing",
        "surface": "bucket_lockfile",
    }
    assert paths.bucket_dir.exists() is False


def test_equivalent_path_release_clears_canonical_local_ownership(
    tmp_path: Path,
) -> None:
    equivalent_root = tmp_path / ".." / tmp_path.name
    relative_paths = provision_bucket_directory(equivalent_root, "alpha")
    absolute_paths = bucket_paths(tmp_path.resolve(), "alpha")

    acquire_lock(relative_paths)
    release_lock(absolute_paths)

    assert lock_path(absolute_paths).exists() is False
    acquire_lock(absolute_paths)
    release_lock(absolute_paths)


def test_child_process_cannot_inherit_parent_local_lock_ownership(
    tmp_path: Path,
) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    if "fork" in multiprocessing.get_all_start_methods():
        context = multiprocessing.get_context("fork")
    else:
        context = multiprocessing.get_context("spawn")
    results = context.Queue()
    assert isinstance(context, _ProcessContext)

    acquire_lock(paths)
    child = context.Process(
        target=_attempt_lock_in_child,
        args=(str(tmp_path), "alpha", results),
    )
    try:
        child.start()
        child.join(timeout=10)
        assert child.exitcode == 0
        assert results.get(timeout=5) == ("busy", os.getpid())
        assert lock_path(paths).is_file()
    finally:
        if child.is_alive():
            child.terminate()
            child.join(timeout=10)
        release_lock(paths)
        results.close()


def test_cross_process_busy_detection(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    ready = tmp_path / "ready"
    script = _holder_script(paths.bucket_dir, hold_seconds=30.0, ready_path=ready)

    holder = subprocess.Popen([sys.executable, "-c", script])
    try:
        _wait_for_ready(ready, holder)
        recorded_pid = int(lock_path(paths).read_text(encoding=UTF_8_ENCODING).strip())
        with pytest.raises(BucketBusyError) as excinfo:
            acquire_lock(paths)
        assert excinfo.value.bucket_id == "alpha"
        # The lockfile-recorded PID is the subprocess's actual PID, which
        # may differ from ``holder.pid`` on Windows (py launcher chain).
        assert excinfo.value.holding_pid == recorded_pid
        assert recorded_pid != os.getpid()
    finally:
        _stop_process(holder)


def test_wait_seconds_eventually_acquires(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    ready = tmp_path / "ready"
    script = _holder_script(paths.bucket_dir, hold_seconds=0.25, ready_path=ready)

    holder = subprocess.Popen([sys.executable, "-c", script])
    try:
        _wait_for_ready(ready, holder)
        # Holder releases after 0.25s; the waiting acquisition must succeed
        # once it does. The window is a hang guard, not a latency assertion:
        # on a heavily loaded shared box the holder subprocess can be
        # descheduled well past its nominal 0.25s hold, and a tight 2s
        # budget produced false timeouts unrelated to the wait contract.
        acquire_lock(paths, wait_seconds=30.0)
        try:
            assert lock_path(paths).is_file()
        finally:
            release_lock(paths)
    finally:
        holder.wait(timeout=10)


def test_stale_lock_with_dead_pid_is_reclaimed(tmp_path: Path) -> None:
    """A lockfile carrying a PID that is no longer alive must be reclaimable.

    Synthesised by writing a lockfile with a PID known not to be live —
    we spawn a short-lived subprocess, wait for it to exit, and stamp its
    (now dead) PID into the lockfile.
    """

    paths = provision_bucket_directory(tmp_path, "alpha")

    proc = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(0)"])
    proc.wait(timeout=5)
    dead_pid = proc.pid

    target = lock_path(paths)
    target.write_text(f"{dead_pid}\n", encoding=UTF_8_ENCODING)

    # Acquisition must succeed: the stale-reclaim path unlinks the dead
    # PID's lockfile, then O_EXCL succeeds.
    acquire_lock(paths)
    try:
        assert int(target.read_text(encoding=UTF_8_ENCODING).strip()) == os.getpid()
    finally:
        release_lock(paths)


def test_malformed_lockfile_pid_is_reclaimed_with_debug_log(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    target = lock_path(paths)
    target.write_text("not-a-pid\n", encoding=UTF_8_ENCODING)

    with caplog.at_level(logging.DEBUG, logger="cadrumo.adapters.persistence.storage.bucket._lockfile"):
        acquire_lock(paths)
    try:
        assert int(target.read_text(encoding=UTF_8_ENCODING).strip()) == os.getpid()
    finally:
        release_lock(paths)

    assert "bucket lockfile pid malformed; treating lock as stale" in caplog.text
    assert str(target) not in caplog.text
    assert str(tmp_path) not in caplog.text


def test_release_is_idempotent_when_lock_absent(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")

    with caplog.at_level(logging.DEBUG, logger="cadrumo.adapters.persistence.storage.bucket._lockfile"):
        release_lock(paths)  # No-op; must not raise.

    assert "bucket lockfile release skipped missing lockfile" in caplog.text
    assert str(tmp_path) not in caplog.text


def test_release_leaves_foreign_lockfile_alone(tmp_path: Path) -> None:
    """``release_lock`` does not delete a lockfile owned by another PID."""

    paths = provision_bucket_directory(tmp_path, "alpha")
    target = lock_path(paths)
    foreign_pid = os.getpid() + 1
    target.write_text(f"{foreign_pid}\n", encoding=UTF_8_ENCODING)

    release_lock(paths)
    assert target.is_file()
    # Cleanup: remove manually since the PID is foreign.
    target.unlink()


def test_bucket_dir_file_collision_is_typed_and_redacted(tmp_path: Path) -> None:
    paths = bucket_paths(tmp_path, "alpha")
    paths.bucket_dir.parent.mkdir(parents=True)
    paths.bucket_dir.write_text("not a directory", encoding=UTF_8_ENCODING)

    with pytest.raises(BucketValidationError) as excinfo:
        acquire_lock(paths)

    assert excinfo.value.context == {
        "reason": "bucket_dir_not_directory",
        "surface": "bucket_lockfile",
    }
    assert str(tmp_path) not in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, FileExistsError)
    envelope = build_error_envelope(excinfo.value)
    assert envelope.code == "INTEGRITY_STORAGE_BUCKET_VALIDATION"
    assert str(tmp_path) not in envelope.model_dump_json()
