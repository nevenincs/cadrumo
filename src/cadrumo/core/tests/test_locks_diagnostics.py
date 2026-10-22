"""The exclusive file lock records waits, long holds and failures, and nothing for a short uncontended hold.

Hot paths take the lock many times per operation, and every diagnostic record
costs a scrub and an append to the shared log file under its own lock.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from pathlib import Path

import pytest

from .. import locks
from ..locks import exclusive_file_lock
from ..locks_errors import LockAcquisitionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LOGGER = "cadrumo.core.locks"


# The scrubbing filter may shorten the home directory in a path, so messages are matched by the sidecar's name.
_ACQUIRED = re.compile(
    r"exclusive_file_lock: acquired .*resource\.json\.lock after waiting \d+\.\d{3}s over \d+ attempts"
)
_RELEASED = re.compile(r"exclusive_file_lock: released .*resource\.json\.lock after holding it \d+\.\d{3}s")
_TIMED_OUT = re.compile(r"exclusive_file_lock: timed out waiting for .*resource\.json\.lock after 0\.05s")


def _lock_messages(caplog: pytest.LogCaptureFixture) -> list[tuple[int, str]]:
    return [(record.levelno, record.getMessage()) for record in caplog.records if record.name == _LOGGER]


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


def test_a_contended_acquire_records_its_wait_and_its_release(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
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
