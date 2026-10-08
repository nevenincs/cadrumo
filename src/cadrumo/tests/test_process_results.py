"""Real spawn-process outcomes and absence for the test-only result observer."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from multiprocessing import get_context
from multiprocessing.process import BaseProcess
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Event

import pytest

from .process_results import receive_process_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _publish(results: Queue[str]) -> None:
    results.put("actual child result")


def _finish_without_result() -> None:
    pass


def _crash() -> None:
    os._exit(7)


def _wait_for_release(release: Event) -> None:
    release.wait()


@contextmanager
def _owned(processes: tuple[BaseProcess, ...], results: Queue[str]) -> Iterator[None]:
    try:
        for process in processes:
            process.start()
        yield
    finally:
        for process in processes:
            if process.is_alive():
                process.kill()
            if process.pid is not None:
                process.join(timeout=30)
        results.close()
        results.join_thread()


def test_receive_actual_child_payload_before_join() -> None:
    context = get_context("spawn")
    results: Queue[str] = Queue(ctx=context)
    child = context.Process(target=_publish, args=(results,))
    with _owned((child,), results):
        assert receive_process_result(results, owners=(child,)) == "actual child result"
        child.join()
        assert child.exitcode == 0


def test_receive_drains_result_after_owner_has_already_finished() -> None:
    context = get_context("spawn")
    results: Queue[str] = Queue(ctx=context)
    child = context.Process(target=_publish, args=(results,))
    with _owned((child,), results):
        child.join()
        assert child.exitcode == 0
        assert receive_process_result(results, owners=(child,)) == "actual child result"


def test_missing_result_after_normal_child_exit_fails() -> None:
    context = get_context("spawn")
    results: Queue[str] = Queue(ctx=context)
    child = context.Process(target=_finish_without_result)
    with _owned((child,), results), pytest.raises(AssertionError, match="finished without a result"):
        receive_process_result(results, owners=(child,))
    assert child.exitcode == 0
    assert not child.is_alive()


def test_crash_is_reported_while_sibling_is_live_and_owner_reaps_both() -> None:
    context = get_context("spawn")
    results: Queue[str] = Queue(ctx=context)
    release = context.Event()
    crashed = context.Process(target=_crash)
    sibling = context.Process(target=_wait_for_release, args=(release,))
    with pytest.raises(AssertionError, match="child owner failed"), _owned((crashed, sibling), results):
        receive_process_result(results, owners=(crashed, sibling))
    assert crashed.exitcode == 7
    assert sibling.exitcode is not None and sibling.exitcode != 0
    assert not crashed.is_alive()
    assert not sibling.is_alive()


def test_result_queue_requires_an_actual_owner() -> None:
    context = get_context("spawn")
    results: Queue[str] = Queue(ctx=context)
    try:
        with pytest.raises(ValueError, match="at least one process owner"):
            receive_process_result(results, owners=())
    finally:
        results.close()
        results.join_thread()
