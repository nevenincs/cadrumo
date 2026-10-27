"""The exclusive file lock records waits, long holds and failures, and nothing for a short uncontended hold.

Hot paths take the lock many times per operation, and every diagnostic record
costs a scrub and an append to the shared log file under its own lock.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ...tests.log_records import delivered_records
from .. import locks
from ..locks import exclusive_file_lock, held_descriptor_lock
from ..locks_errors import LockAcquisitionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LOGGER = "cadrumo.core.locks"


# Messages name the sidecar by file name only; the directory it sits in stays out of the log.
_ACQUIRED = re.compile(
    r"exclusive_file_lock: acquired resource\.json\.lock after waiting \d+\.\d{3}s over \d+ attempts"
)
_RELEASED = re.compile(r"exclusive_file_lock: released resource\.json\.lock after holding it \d+\.\d{3}s")
_TIMED_OUT = re.compile(r"exclusive_file_lock: timed out waiting for resource\.json\.lock after 0\.05s")


def _lock_messages(caplog: pytest.LogCaptureFixture) -> list[tuple[int, str]]:
    return [(record.levelno, record.getMessage()) for record in delivered_records(caplog, _LOGGER)]


def test_uncontended_short_holds_record_nothing(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    target = tmp_path / "resource.json"
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        for _ in range(25):
            with exclusive_file_lock(target, timeout=1.0, retry_backoff=0.01):
                pass
    assert _lock_messages(caplog) == []


def _hold_until(target: Path, held: threading.Event, release: threading.Event) -> None:
    with exclusive_file_lock(target, timeout=1.0, retry_backoff=0.01):
        held.set()
        release.wait(5.0)


def test_a_contended_acquire_records_its_wait_and_its_release(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A slow host must not turn the holder's uncontended hold into a long one.
    monkeypatch.setattr(locks, "SLOW_LOCK_HOLD_SECONDS", 60.0)
    target = tmp_path / "resource.json"
    held, release = threading.Event(), threading.Event()
    holder = threading.Thread(target=_hold_until, args=(target, held, release))
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        holder.start()
        try:
            assert held.wait(5.0)
            threading.Timer(0.1, release.set).start()
            with exclusive_file_lock(target, timeout=5.0, retry_backoff=0.01):
                pass
        finally:
            release.set()
            holder.join(5.0)
    messages = _lock_messages(caplog)
    # The holder's own hold was uncontended and short; only the waiter speaks.
    assert [level for level, _message in messages] == [logging.DEBUG, logging.DEBUG]
    acquired, released = (message for _level, message in messages)
    assert _ACQUIRED.fullmatch(acquired), acquired
    assert _RELEASED.fullmatch(released), released


def test_a_timed_out_acquire_still_warns(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    target = tmp_path / "resource.json"
    with (
        caplog.at_level(logging.DEBUG, logger=_LOGGER),
        exclusive_file_lock(target, timeout=1.0, retry_backoff=0.01),
        pytest.raises(LockAcquisitionError, match="within"),
        exclusive_file_lock(target, timeout=0.05, retry_backoff=0.01),
    ):
        pytest.fail("the second acquire cannot succeed while the first holds")
    messages = _lock_messages(caplog)
    assert [level for level, _message in messages] == [logging.WARNING]
    assert _TIMED_OUT.fullmatch(messages[0][1]), messages


def test_a_long_uncontended_hold_records_its_release(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(locks, "SLOW_LOCK_HOLD_SECONDS", 0.05)
    target = tmp_path / "resource.json"
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        with exclusive_file_lock(target, timeout=1.0, retry_backoff=0.01):
            time.sleep(0.1)
        with exclusive_file_lock(target, timeout=1.0, retry_backoff=0.01):
            pass
    messages = _lock_messages(caplog)
    assert [level for level, _message in messages] == [logging.DEBUG]
    assert _RELEASED.fullmatch(messages[0][1]), messages


def test_a_logging_sink_records_nothing_even_when_contended(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    target = tmp_path / "resource.json"
    with (
        caplog.at_level(logging.DEBUG, logger=_LOGGER),
        exclusive_file_lock(target, timeout=1.0, retry_backoff=0.01),
        pytest.raises(LockAcquisitionError),
        exclusive_file_lock(target, timeout=0.05, retry_backoff=0.01, log_events=False),
    ):
        pytest.fail("the second acquire cannot succeed while the first holds")
    assert _lock_messages(caplog) == []


@pytest.mark.parametrize("retained_descriptor", (False, True))
@pytest.mark.parametrize("body_raises", (False, True))
def test_contended_diagnostic_io_runs_only_after_exclusive_ownership_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retained_descriptor: bool, body_raises: bool
) -> None:
    """A blocked acquisition diagnostic cannot prevent the next real lock owner."""
    target = tmp_path / "resource.json"
    contended, logging_started, release_logging, body_entered = (threading.Event() for _ in range(4))
    original_try = locks._try_lock
    messages: list[tuple[str, tuple[object, ...]]] = []
    body_error = RuntimeError("synthetic protected body failure")

    def observed_try(fd: int) -> bool:
        acquired = original_try(fd)
        if not acquired:
            contended.set()
        return acquired

    def blocked_debug(message: object, *arguments: object) -> None:
        messages.append((str(message), arguments))
        if str(message).startswith("exclusive_file_lock: acquired"):
            logging_started.set()
            assert release_logging.wait(10), "diagnostic was not released"

    def protected_body() -> None:
        body_entered.set()
        if body_raises:
            raise body_error

    def contend() -> None:
        if retained_descriptor:
            fd, lock_path = locks._open_lock_fd(target)
            try:
                with held_descriptor_lock(fd, lock_path, timeout=10, retry_backoff=0.001):
                    protected_body()
            finally:
                os.close(fd)
        else:
            with exclusive_file_lock(target, timeout=10, retry_backoff=0.001):
                protected_body()

    monkeypatch.setattr(locks, "_try_lock", observed_try)
    monkeypatch.setattr(locks._log, "debug", blocked_debug)
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            with exclusive_file_lock(target, timeout=0, log_events=False):
                waiter = pool.submit(contend)
                assert contended.wait(10), "waiter never encountered the held lock"
            assert logging_started.wait(10), "acquisition diagnostic never started"
            with exclusive_file_lock(target, timeout=0, log_events=False):
                pass
            assert body_entered.is_set()
        finally:
            release_logging.set()
        if body_raises:
            with pytest.raises(RuntimeError) as raised:
                waiter.result(timeout=10)
            assert raised.value is body_error
        else:
            waiter.result(timeout=10)

    assert len(messages) == 2
    acquired_message, acquired_arguments = messages[0]
    released_message, released_arguments = messages[1]
    assert acquired_message == "exclusive_file_lock: acquired %s after waiting %.3fs over %d attempts"
    assert released_message == "exclusive_file_lock: released %s after holding it %.3fs"
    assert acquired_arguments[0] == released_arguments[0] == locks.sidecar_lock_path(target).name
    assert isinstance(acquired_arguments[1], float) and acquired_arguments[1] >= 0
    assert isinstance(acquired_arguments[2], int) and acquired_arguments[2] >= 2
    assert isinstance(released_arguments[1], float) and released_arguments[1] >= 0


def test_failing_contended_diagnostic_does_not_leak_a_retained_descriptor_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A logging exception propagates only after the retained descriptor is unlocked."""
    target = tmp_path / "resource.json"
    fd, lock_path = locks._open_lock_fd(target)
    contended, body_entered = threading.Event(), threading.Event()
    original_try = locks._try_lock
    diagnostic_error = RuntimeError("synthetic diagnostic failure")

    def observed_try(candidate: int) -> bool:
        acquired = original_try(candidate)
        if not acquired:
            contended.set()
        return acquired

    def failed_debug(message: object, *arguments: object) -> None:
        del message, arguments
        raise diagnostic_error

    def contend() -> None:
        with held_descriptor_lock(fd, lock_path, timeout=10, retry_backoff=0.001):
            body_entered.set()

    monkeypatch.setattr(locks, "_try_lock", observed_try)
    monkeypatch.setattr(locks._log, "debug", failed_debug)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with exclusive_file_lock(target, timeout=0, log_events=False):
                waiter = pool.submit(contend)
                assert contended.wait(10), "waiter never encountered the held lock"
            with pytest.raises(RuntimeError) as raised:
                waiter.result(timeout=10)
            assert raised.value is diagnostic_error
            with exclusive_file_lock(target, timeout=0, log_events=False):
                pass
            assert body_entered.is_set()
    finally:
        os.close(fd)
