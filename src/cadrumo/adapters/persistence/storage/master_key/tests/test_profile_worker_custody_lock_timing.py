"""A slow wait for, or hold of, the worker's custody lock is reported by caller; a prompt one is not.

The lock is exercised with real threads and short thresholds. Custody is built
without pinning the process-wide worker binding, which other tests rely on.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from threading import Event, Thread, Timer
from uuid import UUID, uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.core.logging import flush_logging
from cadrumo.core.time.clock import now
from cadrumo.core.time.utc import UtcInstant
from cadrumo_client.contracts.automation_codes import AutomationCustodyError
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity

from .. import timed_lock
from ..profile_worker_custody import ProfileWorkerCustody
from ..timed_lock import TimedRLock

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_LOGGER_NAME = timed_lock.__name__
_SLOW = 0.05


def _slow_events(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    assert flush_logging(timeout=5)
    return [
        record
        for record in caplog.records
        if record.name == _LOGGER_NAME and record.getMessage() == "profile_worker_custody_lock_slow"
    ]


def _hold_until(lock: TimedRLock, call_name: str, holding: Event, release: Event) -> Thread:
    def hold() -> None:
        with lock.held(call_name):
            holding.set()
            assert release.wait(5)

    thread = Thread(target=hold, name=f"synthetic-{call_name}")
    thread.start()
    assert holding.wait(5)
    return thread


def test_a_prompt_uncontended_entry_reports_nothing(caplog: pytest.LogCaptureFixture) -> None:
    lock = TimedRLock(slow_seconds=1.0)
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME), lock.held("quick"):
        pass

    assert _slow_events(caplog) == []


def test_a_long_hold_is_reported_under_its_label_with_the_seconds_held(caplog: pytest.LogCaptureFixture) -> None:
    lock = TimedRLock(slow_seconds=_SLOW)
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME), lock.held("slow_holder"):
        time.sleep(3 * _SLOW)

    (event,) = _slow_events(caplog)
    assert event.levelno == logging.WARNING
    assert event.__dict__["call_name"] == "slow_holder"
    assert event.__dict__["hold_seconds"] >= 2 * _SLOW
    assert event.__dict__["wait_seconds"] < _SLOW
    assert "held_call_name" not in event.__dict__
    assert event.threadName == "MainThread"


def test_a_contended_entry_reports_its_wait_and_names_the_entry_that_blocked_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    lock = TimedRLock(slow_seconds=_SLOW)
    holding, release = Event(), Event()
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        holder = _hold_until(lock, "holder", holding, release)
        Timer(4 * _SLOW, release.set).start()
        with lock.held("waiter"):
            pass
        holder.join(5)

    events = {event.__dict__["call_name"]: event for event in _slow_events(caplog)}
    assert set(events) == {"holder", "waiter"}
    waited = events["waiter"].__dict__
    assert waited["wait_seconds"] >= 2 * _SLOW
    assert waited["held_call_name"] == "holder"
    assert waited["held_elapsed_seconds"] >= _SLOW
    assert events["holder"].threadName == "synthetic-holder"
    assert events["holder"].__dict__["hold_seconds"] >= 3 * _SLOW
    assert "held_call_name" not in events["holder"].__dict__


def test_reentry_by_the_holding_thread_neither_blocks_nor_is_reported_apart(caplog: pytest.LogCaptureFixture) -> None:
    lock = TimedRLock(slow_seconds=_SLOW)
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME), lock.held("outer"), lock.held("inner"):
        time.sleep(2 * _SLOW)

    (event,) = _slow_events(caplog)
    assert event.__dict__["call_name"] == "outer"


def test_exclusion_is_kept_between_threads() -> None:
    lock = TimedRLock(slow_seconds=1.0)
    order: list[str] = []
    entered = Event()

    def other() -> None:
        entered.wait(5)
        with lock.held("other"):
            order.append("other")

    thread = Thread(target=other)
    thread.start()
    with lock.held("first"):
        entered.set()
        time.sleep(_SLOW)
        order.append("first")
    thread.join(5)

    assert order == ["first", "other"]


def test_a_failing_body_propagates_and_still_releases_the_lock(caplog: pytest.LogCaptureFixture) -> None:
    lock = TimedRLock(slow_seconds=_SLOW)
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        with pytest.raises(ValueError, match="synthetic body failure"), lock.held("failing"):
            time.sleep(2 * _SLOW)
            raise ValueError("synthetic body failure")
        entered = Event()

        def enter_after() -> None:
            with lock.held("after"):
                entered.set()

        thread = Thread(target=enter_after)
        thread.start()
        thread.join(5)

    assert entered.is_set(), "the lock stayed held after its body failed"
    assert [event.__dict__["call_name"] for event in _slow_events(caplog)] == ["failing"]


def _custody(tmp_path: Path) -> ProfileWorkerCustody:
    identity = ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
    )
    custody = ProfileWorkerCustody.__new__(ProfileWorkerCustody)
    custody._hold_nothing(identity, storage_root=tmp_path, clock=now, monotonic=time.monotonic)
    return custody


def _hold_custody(custody: ProfileWorkerCustody) -> tuple[Thread, Event]:
    """Hold the custody lock inside a real entry by making that entry's clock read wait."""
    holding, release = Event(), Event()

    def waiting_clock() -> UtcInstant:
        custody.clock = now
        holding.set()
        assert release.wait(5)
        return now()

    custody.clock = waiting_clock
    holder = Thread(target=custody.seconds_until_expiry, name="synthetic-holder")
    holder.start()
    assert holding.wait(5)
    return holder, release


@pytest.mark.parametrize("method", ["expire", "live_sessions", "seconds_until_expiry", "retire", "require", "close"])
def test_custody_entries_report_a_slow_wait_under_their_own_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, method: str
) -> None:
    monkeypatch.setattr(timed_lock, "SLOW_LOCK_SECONDS", _SLOW)
    custody = _custody(tmp_path)
    session_id: UUID = uuid4()

    def call() -> None:
        if method == "retire":
            custody.retire(session_id)
        elif method == "require":
            with pytest.raises(AutomationCustodyError):
                custody.require(session_id)
        else:
            getattr(custody, method)()

    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        holder, release = _hold_custody(custody)
        Timer(3 * _SLOW, release.set).start()
        call()
        holder.join(5)

    (waited,) = [
        event.__dict__
        for event in _slow_events(caplog)
        if event.__dict__["call_name"] == method and event.__dict__["wait_seconds"] >= _SLOW
    ]
    assert waited["held_call_name"] == "seconds_until_expiry"
    assert waited["held_elapsed_seconds"] >= _SLOW
    assert not {"session_id", "lease", "identity"}.intersection(waited)
