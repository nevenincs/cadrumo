"""Proof stop signals wake every owner and settle subscriptions before teardown."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from threading import Event

import pytest

from ..proof_cancellation import ProfileProofCancellation, ProfileProofCancelledError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_a_cancelled_attempt_immediately_wakes_a_new_subscriber() -> None:
    cancellation = ProfileProofCancellation()
    cancellation.cancel()
    woke = Event()
    with cancellation.watch(woke.set):
        assert woke.is_set()
        with pytest.raises(ProfileProofCancelledError):
            cancellation.raise_if_cancelled()


def test_unsubscription_joins_a_captured_callback_before_its_resource_is_closed() -> None:
    cancellation = ProfileProofCancellation()
    entered, finish = Event(), Event()
    calls: list[str] = []

    def callback() -> None:
        entered.set()
        assert finish.wait(10)
        calls.append("resource used")

    subscription = cancellation.watch(callback)
    subscription.__enter__()
    with ExitStack() as cleanup:
        pool = ThreadPoolExecutor(max_workers=2)
        cleanup.callback(pool.shutdown)
        cleanup.callback(finish.set)
        cancelled = pool.submit(cancellation.cancel)
        assert entered.wait(5)
        unsubscribed = pool.submit(subscription.__exit__, None, None, None)
        assert not unsubscribed.done()
        finish.set()
        cancelled.result(timeout=5)
        unsubscribed.result(timeout=5)
    calls.append("resource closed")
    cancellation.cancel()
    assert calls == ["resource used", "resource closed"]


def test_one_broken_wakeup_does_not_strand_the_other_registered_owner() -> None:
    cancellation, woke = ProfileProofCancellation(), Event()

    def broken() -> None:
        raise RuntimeError("synthetic wakeup failure")

    with cancellation.watch(broken), cancellation.watch(woke.set):
        with pytest.raises(ExceptionGroup):
            cancellation.cancel()
        assert woke.is_set()
        with pytest.raises(ProfileProofCancelledError):
            cancellation.raise_if_cancelled()
