"""Committed operations reach the runtime coalesced, from one thread, and never block a commit."""

from __future__ import annotations

from threading import Event, Lock

import pytest

from cadrumo.application.operations.models import OperationId, new_operation_id

from ..operation_progress_reporter import OperationProgressReporter

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _Runtime:
    """Records each report; the first one can be held in flight."""

    def __init__(self, *, hold_first: bool = False, fail_first: bool = False) -> None:
        self.reports: list[tuple[OperationId, ...]] = []
        self.in_flight = Event()
        self.release = Event()
        self.arrived = Event()
        self._hold_first, self._fail_first = hold_first, fail_first
        self._lock = Lock()

    def send(self, batch: tuple[OperationId, ...]) -> None:
        with self._lock:
            first = not self.reports
            self.reports.append(batch)
        self.arrived.set()
        if first and self._hold_first:
            self.in_flight.set()
            assert self.release.wait(5)
        if first and self._fail_first:
            raise OSError("synthetic undeliverable report")


def test_commits_during_a_report_in_flight_join_one_next_report() -> None:
    runtime = _Runtime(hold_first=True)
    reporter = OperationProgressReporter(runtime.send)
    first, second, third = new_operation_id(), new_operation_id(), new_operation_id()
    reporter.committed(first)
    assert runtime.in_flight.wait(5)
    for operation_id in (second, third, second, third):
        reporter.committed(operation_id)
    runtime.release.set()
    reporter.close()
    assert runtime.reports == [(first,), (second, third)]


def test_an_undeliverable_report_is_dropped_not_retried() -> None:
    runtime = _Runtime(fail_first=True)
    reporter = OperationProgressReporter(runtime.send)
    lost, later = new_operation_id(), new_operation_id()
    reporter.committed(lost)
    assert runtime.arrived.wait(5)
    runtime.arrived.clear()
    reporter.committed(later)
    assert runtime.arrived.wait(5)
    reporter.close()
    assert runtime.reports == [(lost,), (later,)]


def test_close_delivers_what_is_pending_then_reports_nothing_more() -> None:
    runtime = _Runtime(hold_first=True)
    reporter = OperationProgressReporter(runtime.send)
    first, pending, late = new_operation_id(), new_operation_id(), new_operation_id()
    reporter.committed(first)
    assert runtime.in_flight.wait(5)
    reporter.committed(pending)
    runtime.release.set()
    reporter.close()
    reporter.committed(late)
    assert runtime.reports == [(first,), (pending,)]
