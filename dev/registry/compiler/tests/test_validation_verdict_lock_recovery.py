"""A verdict lock must never outlive its usefulness.

The lock is an optimisation: it saves a duplicate validation and nothing more.
Two ways of holding on to it cost more than it can ever save, and both were
observed on this checkout -- locks stranded by killed processes that no later
key ever revisits, and a waiter queued behind an unbroken succession of live
peers on a continuously revalidated tree. These cover the recovery from each.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from ..validation_verdict_cache import (
    _LOCK_STALE_SECONDS,
    VERDICT_CACHE_DIR_ENV,
    record_validated,
    verdict_cache_dir,
    verdict_validation_lock,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Never a live user process on any supported platform, and ``pid_is_alive``
# rejects it without probing the OS.
_DEAD_PID = "0"


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the verdict cache at an empty per-test store."""
    monkeypatch.setenv(VERDICT_CACHE_DIR_ENV, str(tmp_path / "verdicts"))
    directory = verdict_cache_dir()
    directory.mkdir(parents=True)
    return directory


def _lock(store: Path, key: str, holder: str) -> Path:
    path = store / f"verdict_{key}.lock"
    path.write_text(holder, encoding="ascii")
    return path


def test_a_lock_left_by_a_dead_process_is_taken_over_at_once(store: Path) -> None:
    """A killed validator must not hold its key for the staleness window."""
    stranded = _lock(store, "wanted", _DEAD_PID)

    started = time.monotonic()
    with verdict_validation_lock("wanted", wait_seconds=30.0):
        assert stranded.read_text(encoding="ascii") == str(os.getpid())

    assert not stranded.exists(), "the reclaimed lock must be released again"
    assert time.monotonic() - started < 10.0


def test_locks_stranded_under_other_keys_are_swept(store: Path) -> None:
    """Nothing revisits a dead key, so only a sweep collects what it left."""
    stranded = [_lock(store, f"gone-{index}", _DEAD_PID) for index in range(3)]
    live = _lock(store, "peer", str(os.getpid()))

    with verdict_validation_lock("wanted"):
        pass

    assert [path for path in stranded if path.exists()] == []
    assert live.exists(), "a lock whose holder is alive must survive the sweep"


def test_a_live_peer_is_waited_out_then_passed_rather_than_stolen(store: Path) -> None:
    """Giving up costs one duplicate validation; stealing costs two validators."""
    held = _lock(store, "wanted", str(os.getpid()))

    started = time.monotonic()
    with verdict_validation_lock("wanted", wait_seconds=0.5):
        pass
    waited = time.monotonic() - started

    assert held.read_text(encoding="ascii") == str(os.getpid())
    assert held.exists(), "the peer's lock must not be released by the waiter"
    assert 0.4 < waited < 20.0


def test_a_lock_older_than_any_validation_is_broken_even_when_its_stamp_reads_alive(store: Path) -> None:
    """Pids are recycled, so an old lock whose stamp reads alive is not evidence of a holder."""
    ancient = _lock(store, "wanted", str(os.getpid()))
    aged = time.time() - (_LOCK_STALE_SECONDS + 60.0)
    os.utime(ancient, (aged, aged))

    with verdict_validation_lock("wanted", wait_seconds=0.5):
        pass

    assert not ancient.exists(), "a lock older than the staleness window must be broken and released"


def test_a_verdict_recorded_by_the_holder_ends_the_wait(store: Path) -> None:
    """The verdict is the reason to wait, so its arrival is the reason to stop."""
    held = _lock(store, "wanted", str(os.getpid()))
    record_validated("wanted", subject="registry")

    started = time.monotonic()
    with verdict_validation_lock("wanted", wait_seconds=120.0):
        pass

    assert time.monotonic() - started < 10.0
    assert held.exists()
