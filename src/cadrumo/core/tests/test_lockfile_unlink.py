"""Tests for the shared share-violation-tolerant lockfile removal."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from ..lockfile_unlink import LOCKFILE_UNLINK_RETRY_SECONDS, unlink_lockfile
from ..external_constants import UTF_8_ENCODING

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_removes_a_free_lockfile(tmp_path: Path) -> None:
    lock = tmp_path / "free.lock"
    lock.write_text("1234\n", encoding=UTF_8_ENCODING)

    assert unlink_lockfile(lock, reason="test") is True
    assert not lock.exists()


def test_reports_success_for_an_already_absent_lockfile(tmp_path: Path) -> None:
    """An absent lockfile is the outcome the caller wanted, not a failure."""
    lock = tmp_path / "absent.lock"

    assert unlink_lockfile(lock, reason="test") is True


def test_return_value_always_describes_the_file_that_is_actually_there(tmp_path: Path) -> None:
    """The report must track reality on every platform, not a hoped-for outcome.

    Windows refuses the removal while a read handle is open and the call
    reports ``False``; POSIX honours the unlink and it reports ``True``. Pinning
    the return value against ``exists()`` keeps the contract meaningful on both
    rather than asserting one platform's behaviour everywhere.
    """
    lock = tmp_path / "held.lock"
    lock.write_text("1234\n", encoding=UTF_8_ENCODING)

    with lock.open("r", encoding=UTF_8_ENCODING):
        removed = unlink_lockfile(lock, reason="test")

    assert removed is not lock.exists()


def test_retries_until_the_holder_releases_its_handle(tmp_path: Path) -> None:
    """A retry budget waits out a peer inspecting the lockfile.

    The wait is what the release path depends on: an abandoned removal leaves a
    lockfile stamped with a live PID, which no peer will ever reclaim as stale.
    On POSIX the first attempt already succeeds, so this asserts the outcome
    both platforms owe the caller -- the file is gone and the call said so.
    """
    lock = tmp_path / "briefly-held.lock"
    lock.write_text("1234\n", encoding=UTF_8_ENCODING)
    handle = lock.open("r", encoding=UTF_8_ENCODING)
    releaser = threading.Timer(0.3, handle.close)
    releaser.start()
    try:
        removed = unlink_lockfile(lock, retry_seconds=LOCKFILE_UNLINK_RETRY_SECONDS, reason="test")
    finally:
        releaser.cancel()
        handle.close()

    assert removed is True
    assert not lock.exists()


def test_a_zero_budget_does_not_wait(tmp_path: Path) -> None:
    """Best-effort callers must return immediately; losing the race costs a poll.

    A stale reclaim that blocked for the release budget would stall the
    acquisition loop it runs inside.
    """
    lock = tmp_path / "contended.lock"
    lock.write_text("1234\n", encoding=UTF_8_ENCODING)

    with lock.open("r", encoding=UTF_8_ENCODING):
        started = time.monotonic()
        unlink_lockfile(lock, reason="test")
        elapsed = time.monotonic() - started

    assert elapsed < 1.0


def test_an_unremovable_target_never_reports_a_clean_removal(tmp_path: Path) -> None:
    """A directory standing where the lockfile belongs must not read as removed.

    Windows reports this with the same ``ERROR_ACCESS_DENIED`` a contended
    removal raises, so it is absorbed and reported as "not removed"; POSIX
    raises. Both are honest. Returning ``True`` would not be, and is the one
    outcome this pins shut on every platform.
    """
    lock = tmp_path / "not-a-file.lock"
    lock.mkdir()

    try:
        removed = unlink_lockfile(lock, reason="test")
    except OSError:
        return

    assert removed is False
    assert lock.exists()
