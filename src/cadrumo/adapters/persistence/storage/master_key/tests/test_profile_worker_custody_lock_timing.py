"""A slow wait for, or hold of, a timed lock is reported by caller; a prompt one is not.

The lock is exercised with real threads and short thresholds, both through its
labelled ``held`` entry and through the ``RLock`` protocol that names the
calling code. Custody is built without pinning the process-wide worker binding,
which other tests rely on.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from threading import Event, RLock, Thread, Timer
from uuid import UUID, uuid4

import pytest

from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.core.time.clock import now
from cadrumo.core.time.utc import UtcInstant
from cadrumo.tests.log_records import delivered_records
from cadrumo_client.contracts.automation_codes import AutomationCustodyError
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity

from .. import timed_lock
from ..profile_worker_custody import ProfileWorkerCustody
from ..timed_lock import TimedRLock

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_LOGGER_NAME = timed_lock.__name__
_SLOW = 0.05


def _slow_events(
    caplog: pytest.LogCaptureFixture, event: str = "profile_worker_custody_lock_slow"
) -> list[logging.LogRecord]:
    return [record for record in delivered_records(caplog, _LOGGER_NAME) if record.getMessage() == event]


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


_PROTOCOL_EVENT = "synthetic_protocol_lock_slow"


def _on_another_thread(action: Callable[[], object]) -> object:
    """Run ``action`` on a fresh thread and return what it returned, or the exception it raised."""
    outcome: list[object] = []

    def run() -> None:
        try:
            outcome.append(action())
        except BaseException as error:
            outcome.append(error)

    thread = Thread(target=run)
    thread.start()
    thread.join(5)
    assert not thread.is_alive()
    return outcome[0]


def _described(outcome: object) -> object:
    return (type(outcome).__name__, str(outcome)) if isinstance(outcome, BaseException) else outcome


def _acquired_then_released(lock: RLock | TimedRLock) -> bool:
    acquired = lock.acquire(blocking=False)
    if acquired:
        lock.release()
    return acquired


@pytest.mark.parametrize("make_lock", [RLock, TimedRLock], ids=["rlock", "timed"])
def test_acquire_and_release_follow_the_rlock_contract(make_lock: Callable[[], RLock | TimedRLock]) -> None:
    """The same expectations hold for ``RLock`` itself, so they are not derived from the timed lock."""
    lock = make_lock()
    unheld = ("RuntimeError", "cannot release un-acquired lock")
    assert _described(_on_another_thread(lock.release)) == unheld
    with pytest.raises(ValueError, match="non-blocking"):
        lock.acquire(blocking=False, timeout=1)
    with pytest.raises(ValueError, match="non-negative"):
        lock.acquire(timeout=-2)
    assert _on_another_thread(lambda: _acquired_then_released(lock)) is True, "a refused call left the lock held"

    assert lock.acquire() is True
    assert lock.acquire(blocking=False) is True
    with lock as entered:
        assert entered is True
        assert _on_another_thread(lambda: lock.acquire(blocking=False)) is False
        assert _on_another_thread(lambda: lock.acquire(timeout=0.02)) is False
        assert _described(_on_another_thread(lock.release)) == unheld
    lock.release()
    assert _on_another_thread(lambda: lock.acquire(blocking=False)) is False, "one level is still held"
    lock.release()
    assert _on_another_thread(lambda: _acquired_then_released(lock)) is True
    with pytest.raises(RuntimeError, match="un-acquired"):
        lock.release()


def _hold_reentrantly(lock: TimedRLock, seconds: float) -> None:
    with lock, lock:
        time.sleep(seconds)


def test_a_slow_with_block_is_reported_once_under_the_code_that_entered_it(caplog: pytest.LogCaptureFixture) -> None:
    lock = TimedRLock(slow_seconds=_SLOW, event=_PROTOCOL_EVENT)
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        _hold_reentrantly(lock, 3 * _SLOW)

    (event,) = _slow_events(caplog, _PROTOCOL_EVENT)
    assert event.levelno == logging.WARNING
    assert event.__dict__["call_name"].startswith(f"{__name__}:_hold_reentrantly < {__name__}:")
    assert event.__dict__["hold_seconds"] >= 2 * _SLOW
    assert event.__dict__["wait_seconds"] < _SLOW
    assert event.threadName == "MainThread"
    assert _slow_events(caplog) == [], "an event name is the lock's own"


@contextmanager
def _admission(lock: TimedRLock) -> Generator[None]:
    with lock:
        yield


def test_contextlib_frames_do_not_name_an_entry(caplog: pytest.LogCaptureFixture) -> None:
    lock = TimedRLock(slow_seconds=_SLOW, event=_PROTOCOL_EVENT)
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME), ExitStack() as stack:
        stack.enter_context(_admission(lock))
        time.sleep(2 * _SLOW)

    (event,) = _slow_events(caplog, _PROTOCOL_EVENT)
    name = event.__dict__["call_name"]
    assert name.startswith(f"{__name__}:_admission < {__name__}:test_contextlib_frames_do_not_name_an_entry")
    assert "contextlib" not in [frame.split(":")[0] for frame in name.split(" < ")]


def _hold_until_released(lock: TimedRLock, holding: Event, release: Event) -> None:
    with lock:
        holding.set()
        assert release.wait(5)


def _wait_for(lock: TimedRLock) -> None:
    with lock:
        pass


def test_a_contended_with_reports_its_wait_and_names_the_code_that_held_the_lock(
    caplog: pytest.LogCaptureFixture,
) -> None:
    lock = TimedRLock(slow_seconds=_SLOW, event=_PROTOCOL_EVENT)
    holding, release = Event(), Event()
    holder = Thread(target=_hold_until_released, args=(lock, holding, release), name="synthetic-holder")
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        holder.start()
        assert holding.wait(5)
        Timer(4 * _SLOW, release.set).start()
        _wait_for(lock)
        holder.join(5)

    events = {event.__dict__["call_name"].split(" < ")[0]: event for event in _slow_events(caplog, _PROTOCOL_EVENT)}
    assert set(events) == {f"{__name__}:_hold_until_released", f"{__name__}:_wait_for"}
    waited = events[f"{__name__}:_wait_for"]
    assert waited.__dict__["wait_seconds"] >= 2 * _SLOW
    assert waited.__dict__["held_call_name"].startswith(f"{__name__}:_hold_until_released")
    assert waited.__dict__["held_elapsed_seconds"] >= _SLOW
    held = events[f"{__name__}:_hold_until_released"]
    assert held.threadName == "synthetic-holder"
    assert held.__dict__["hold_seconds"] >= 3 * _SLOW
    assert "held_call_name" not in held.__dict__


def test_an_expired_timed_acquire_is_refused_unreported_and_leaves_the_holder_intact(
    caplog: pytest.LogCaptureFixture,
) -> None:
    lock = TimedRLock(slow_seconds=_SLOW, event=_PROTOCOL_EVENT)
    holding, release = Event(), Event()
    holder = Thread(target=_hold_until_released, args=(lock, holding, release), name="synthetic-holder")
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        holder.start()
        assert holding.wait(5)
        assert not lock.acquire(blocking=False)
        assert not lock.acquire(timeout=_SLOW / 2)
        assert not lock.acquire(timeout=2 * _SLOW)
        release.set()
        holder.join(5)

    (event,) = _slow_events(caplog, _PROTOCOL_EVENT)
    assert event.threadName == "synthetic-holder"
    assert _on_another_thread(lambda: _acquired_then_released(lock)) is True


def test_a_timed_acquire_that_outlasts_the_threshold_but_succeeds_names_its_blocker(
    caplog: pytest.LogCaptureFixture,
) -> None:
    lock = TimedRLock(slow_seconds=_SLOW, event=_PROTOCOL_EVENT)
    holding, release = Event(), Event()
    holder = Thread(target=_hold_until_released, args=(lock, holding, release), name="synthetic-holder")
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        holder.start()
        assert holding.wait(5)
        Timer(3 * _SLOW, release.set).start()
        assert lock.acquire(timeout=20 * _SLOW)
        lock.release()
        holder.join(5)

    waited = next(event for event in _slow_events(caplog, _PROTOCOL_EVENT) if event.threadName == "MainThread")
    assert waited.__dict__["wait_seconds"] >= 2 * _SLOW
    assert waited.__dict__["held_call_name"].startswith(f"{__name__}:_hold_until_released")


def test_a_failing_with_block_propagates_reports_and_releases(caplog: pytest.LogCaptureFixture) -> None:
    lock = TimedRLock(slow_seconds=_SLOW, event=_PROTOCOL_EVENT)
    with caplog.at_level(logging.DEBUG, logger=_LOGGER_NAME):
        with pytest.raises(ValueError, match="synthetic body failure"), lock:
            time.sleep(2 * _SLOW)
            raise ValueError("synthetic body failure")
        assert _on_another_thread(lambda: _acquired_then_released(lock)) is True

    assert len(_slow_events(caplog, _PROTOCOL_EVENT)) == 1
