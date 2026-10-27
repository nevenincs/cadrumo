"""A long wait for, or hold of, a profile's admission guard names the code that entered it.

The host is composed for real; only the report threshold is shortened. Waiting
and holding use real threads, so the guard the worker session owner shares with
the host is the one measured.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from threading import Event, Thread, Timer

import pytest

from cadrumo.adapters.persistence.storage.master_key import timed_lock
from cadrumo.tests.log_records import delivered_records

from .. import profile_host, session_owner
from ..profile_host import RuntimeProfileHost
from .test_owner_scope_reuse import _host

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SLOW = 0.05
_EVENT = "profile_guard_slow"


def _slow_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seconds: float) -> RuntimeProfileHost:
    monkeypatch.setattr(profile_host, "_GUARD_SLOW_SECONDS", seconds)
    return _host(tmp_path)[0]


def _guard_events(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in delivered_records(caplog, timed_lock.__name__) if record.getMessage() == _EVENT]


def _admit_and_linger(host: RuntimeProfileHost, seconds: float) -> None:
    # The host's own entry is nested in the admission, as its callers nest it.
    with host.owner.admission_guard(), host.guard:
        time.sleep(seconds)


def test_a_long_admission_hold_is_reported_once_under_the_admitting_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    host = _slow_host(tmp_path, monkeypatch, _SLOW)
    with caplog.at_level(logging.DEBUG, logger=timed_lock.__name__):
        _admit_and_linger(host, 3 * _SLOW)

    (event,) = _guard_events(caplog)
    assert event.levelno == logging.WARNING
    assert event.threadName == "MainThread"
    assert event.__dict__["call_name"].startswith(
        f"{session_owner.__name__}:ProfileWorkerSessionOwner.admission_guard < {__name__}:_admit_and_linger"
    )
    assert event.__dict__["hold_seconds"] >= 2 * _SLOW
    assert event.__dict__["wait_seconds"] < _SLOW


def test_a_prompt_hold_reports_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    host = _slow_host(tmp_path, monkeypatch, 60.0)
    with caplog.at_level(logging.DEBUG, logger=timed_lock.__name__):
        _admit_and_linger(host, 0.0)

    assert _guard_events(caplog) == []


def _hold_the_guard(host: RuntimeProfileHost, holding: Event, release: Event) -> None:
    with host.guard:
        holding.set()
        assert release.wait(5)


def test_a_request_waiting_on_the_guard_names_the_code_holding_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    host = _slow_host(tmp_path, monkeypatch, _SLOW)
    holding, release = Event(), Event()
    holder = Thread(target=_hold_the_guard, args=(host, holding, release), name="synthetic-stalled-holder")
    with caplog.at_level(logging.DEBUG, logger=timed_lock.__name__):
        holder.start()
        assert holding.wait(5)
        Timer(4 * _SLOW, release.set).start()
        # The host's own observation takes the guard on this thread, as an admitted request's would.
        host.observe_human_lock_down()
        holder.join(5)

    events = {event.threadName: event.__dict__ for event in _guard_events(caplog)}
    assert set(events) == {"MainThread", "synthetic-stalled-holder"}
    waiter = events["MainThread"]
    assert waiter["call_name"].startswith(f"{profile_host.__name__}:RuntimeProfileHost.observe_human_lock_down")
    assert waiter["wait_seconds"] >= 2 * _SLOW
    assert waiter["held_call_name"].startswith(f"{__name__}:_hold_the_guard")
    assert events["synthetic-stalled-holder"]["hold_seconds"] >= 3 * _SLOW
