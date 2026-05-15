"""Tests for the per-bucket ``.lock`` concurrency primitive."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage.bucket._errors import BucketBusyError
from aeat.adapters.persistence.storage.bucket._layout import (
    provision_bucket_directory,
)
from aeat.adapters.persistence.storage.bucket._lockfile import (
    acquire_lock,
    lock_path,
    release_lock,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _holder_script(bucket_dir: Path, hold_seconds: float, ready_path: Path) -> str:
    """Render a subprocess script that acquires the lock and holds it."""

    return textwrap.dedent(
        f"""
        import sys, time
        from pathlib import Path
        sys.path.insert(0, {str(Path(__file__).resolve().parents[5])!r})
        from aeat.adapters.persistence.storage.bucket._layout import bucket_paths
        from aeat.adapters.persistence.storage.bucket._lockfile import (
            acquire_lock,
            release_lock,
        )

        paths = bucket_paths(Path({str(bucket_dir.parent.parent)!r}), {bucket_dir.name!r})
        acquire_lock(paths)
        Path({str(ready_path)!r}).write_text("ready", encoding="utf-8")
        time.sleep({hold_seconds!r})
        release_lock(paths)
        """,
    )


def _wait_for_ready(ready_path: Path, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if ready_path.is_file():
            return
        time.sleep(0.05)
    raise AssertionError(f"subprocess did not signal readiness within {timeout}s")


def test_acquire_then_release_round_trip(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")

    acquire_lock(paths)
    try:
        target = lock_path(paths)
        assert target.is_file()
        assert int(target.read_text(encoding="utf-8").strip()) == os.getpid()
    finally:
        release_lock(paths)

    assert not lock_path(paths).exists()


def test_second_in_process_acquire_fails_fast(tmp_path: Path) -> None:
    """Two ``acquire_lock`` calls in the same process — the second must fail.

    The lockfile uses ``O_EXCL`` so a re-entrant acquire is rejected just
    as a foreign-process acquire would be.
    """

    paths = provision_bucket_directory(tmp_path, "alpha")
    acquire_lock(paths)
    try:
        with pytest.raises(BucketBusyError) as excinfo:
            acquire_lock(paths)
        assert excinfo.value.bucket_id == "alpha"
        assert excinfo.value.holding_pid == os.getpid()
    finally:
        release_lock(paths)


def test_cross_process_busy_detection(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    ready = tmp_path / "ready"
    script = _holder_script(paths.bucket_dir, hold_seconds=2.0, ready_path=ready)

    holder = subprocess.Popen([sys.executable, "-c", script])
    try:
        _wait_for_ready(ready)
        recorded_pid = int(lock_path(paths).read_text(encoding="utf-8").strip())
        with pytest.raises(BucketBusyError) as excinfo:
            acquire_lock(paths)
        assert excinfo.value.bucket_id == "alpha"
        # The lockfile-recorded PID is the subprocess's actual PID, which
        # may differ from ``holder.pid`` on Windows (py launcher chain).
        assert excinfo.value.holding_pid == recorded_pid
        assert recorded_pid != os.getpid()
    finally:
        holder.wait(timeout=10)


def test_wait_seconds_eventually_acquires(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    ready = tmp_path / "ready"
    script = _holder_script(paths.bucket_dir, hold_seconds=0.6, ready_path=ready)

    holder = subprocess.Popen([sys.executable, "-c", script])
    try:
        _wait_for_ready(ready)
        # Holder releases after 0.6s; wait 3s window must succeed.
        acquire_lock(paths, wait_seconds=3.0)
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
    target.write_text(f"{dead_pid}\n", encoding="utf-8")

    # Acquisition must succeed: the stale-reclaim path unlinks the dead
    # PID's lockfile, then O_EXCL succeeds.
    acquire_lock(paths)
    try:
        assert int(target.read_text(encoding="utf-8").strip()) == os.getpid()
    finally:
        release_lock(paths)


def test_release_is_idempotent_when_lock_absent(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")

    release_lock(paths)  # No-op; must not raise.


def test_release_leaves_foreign_lockfile_alone(tmp_path: Path) -> None:
    """``release_lock`` does not delete a lockfile owned by another PID."""

    paths = provision_bucket_directory(tmp_path, "alpha")
    target = lock_path(paths)
    foreign_pid = os.getpid() + 1
    target.write_text(f"{foreign_pid}\n", encoding="utf-8")

    release_lock(paths)
    assert target.is_file()
    # Cleanup: remove manually since the PID is foreign.
    target.unlink()
