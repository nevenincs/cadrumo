"""A slow administration read answers busy at its bound and serves its result next."""

from __future__ import annotations

import time
from threading import Event

import pytest

from ..bounded_read import BUSY, BoundedRead, Identity

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Work:
    def __init__(self) -> None:
        self.release = Event()
        self.runs = 0
        self.fail = False

    def __call__(self) -> str:
        self.runs += 1
        self.release.wait(5)
        if self.fail:
            raise LookupError("work_failed")
        return f"result-{self.runs}"


def _outlive(read: BoundedRead[str], work: _Work, key: object) -> None:
    """Leave one request unanswered by its bound, then let the work finish."""
    work.release.clear()
    assert read.answer(key, within=0.05) == BUSY
    work.release.set()
    deadline = time.monotonic() + 5
    while read.answer(key, within=5) == BUSY and time.monotonic() < deadline:
        pass


def test_unfinished_work_is_busy_at_the_bound_and_its_result_is_served_next() -> None:
    work = _Work()
    read = BoundedRead(work, name="test", fresh_seconds=30)

    started = time.monotonic()
    assert read.answer("lease-1", within=0.2) == BUSY
    assert time.monotonic() - started < 1
    # A second request joins the same work instead of starting another.
    assert read.answer("lease-1", within=0.1) == BUSY
    work.release.set()
    assert read.answer("lease-1", within=5) == "result-1"
    # The work outlived a request, so the request that comes back is served it.
    assert read.answer("lease-1", within=0) == "result-1"
    assert work.runs == 1


def test_work_that_answers_its_own_request_is_not_kept() -> None:
    work = _Work()
    work.release.set()
    read = BoundedRead(work, name="test", fresh_seconds=30)

    assert read.answer("lease-1", within=5) == "result-1"
    assert read.answer("lease-1", within=5) == "result-2"


def test_a_kept_result_is_served_only_for_its_key_and_until_forgotten() -> None:
    work = _Work()
    read = BoundedRead(work, name="test", fresh_seconds=30)
    _outlive(read, work, "lease-1")
    assert read.answer("lease-1", within=5) == "result-1"

    assert read.answer("lease-2", within=5) == "result-2"
    read.forget()
    assert read.answer("lease-1", within=5) == "result-3"


def test_keys_compare_the_objects_they_hold_by_identity() -> None:
    lease = {"lease": "unhashable"}
    assert Identity(lease) == Identity(lease)
    assert Identity(lease) != Identity({"lease": "unhashable"})
    assert hash(Identity(lease)) == hash(Identity(lease))


def test_a_stale_kept_result_is_read_again() -> None:
    work = _Work()
    read = BoundedRead(work, name="test", fresh_seconds=0.05)
    _outlive(read, work, "lease-1")
    time.sleep(0.1)
    assert read.answer("lease-1", within=5) == "result-2"


def test_a_failure_reaches_the_waiting_request_and_is_not_kept() -> None:
    work = _Work()
    work.release.set()
    work.fail = True
    read = BoundedRead(work, name="test", fresh_seconds=30)

    with pytest.raises(LookupError):
        read.answer("lease-1", within=5)
    work.fail = False
    assert read.answer("lease-1", within=5) == "result-2"
