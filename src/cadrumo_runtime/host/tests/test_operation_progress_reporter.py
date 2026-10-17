"""Committed operations reach the runtime coalesced, from one thread, and never block a commit."""

from __future__ import annotations

from threading import Condition, Event, Lock
from time import monotonic

import pytest

from cadrumo.application.operations.models import OperationId, new_operation_id

from ..operation_progress_reporter import OperationProgressReporter

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _Runtime:
    """Records each report and when it came; the first one can be held in flight or refused."""

    def __init__(
        self,
        *,
        hold_first: bool = False,
        fail_first: bool = False,
        fail_always: bool = False,
        escape_first: bool = False,
    ) -> None:
        self.reports: list[tuple[OperationId, ...]] = []
        self.at: list[float] = []
        self.in_flight = Event()
        self.release = Event()
        self.arrived = Event()
        self._hold_first, self._fail_first, self._escape_first = hold_first, fail_first, escape_first
        self._fail_always = fail_always
        self._lock = Lock()
        self._reported = Condition(self._lock)

    def send(self, batch: tuple[OperationId, ...]) -> None:
        with self._lock:
            first = not self.reports
            self.reports.append(batch)
            self.at.append(monotonic())
            self._reported.notify_all()
        self.arrived.set()
        if first and self._hold_first:
            self.in_flight.set()
            assert self.release.wait(5)
        if self._fail_always or (first and self._fail_first):
            raise OSError("synthetic undeliverable report")
        if first and self._escape_first:
            # Not an ``Exception``: the send guard lets it end the reporting thread.
            raise SystemExit("synthetic escape from the reporting thread")

    def wait_for_reports(self, count: int, timeout: float = 5) -> bool:
        with self._reported:
            return self._reported.wait_for(lambda: len(self.reports) >= count, timeout)


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


def test_an_undeliverable_report_is_retried_ahead_of_later_commits() -> None:
    # The first report is refused only after a later commit has queued behind it.
    runtime = _Runtime(hold_first=True, fail_first=True)
    reporter = OperationProgressReporter(runtime.send)
    refused, later = new_operation_id(), new_operation_id()
    reporter.committed(refused)
    assert runtime.in_flight.wait(5)
    reporter.committed(later)
    runtime.release.set()
    assert runtime.wait_for_reports(2)
    reporter.close()
    assert runtime.reports == [(refused,), (refused, later)]


def test_a_refused_report_waits_out_a_backoff_before_its_retry() -> None:
    runtime = _Runtime(fail_first=True)
    reporter = OperationProgressReporter(runtime.send)
    reporter.committed(new_operation_id())
    assert runtime.wait_for_reports(2)
    reporter.close()
    assert runtime.at[1] - runtime.at[0] >= 0.04


def test_a_close_while_the_runtime_refuses_gives_each_pending_report_one_try() -> None:
    runtime = _Runtime(fail_always=True)
    reporter = OperationProgressReporter(runtime.send)
    reporter.committed(new_operation_id())
    assert runtime.wait_for_reports(1)
    reporter.close()
    tried = len(runtime.reports)
    # A closed reporter stops retrying rather than spinning on a runtime that refuses it.
    assert not runtime.wait_for_reports(tried + 1, timeout=0.3)


def test_a_reporting_thread_ended_by_an_escaping_error_is_replaced() -> None:
    runtime = _Runtime(escape_first=True)
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
