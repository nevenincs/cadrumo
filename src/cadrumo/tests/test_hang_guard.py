"""The hang guard returns a step's result and its failure, and fails only a step that cannot finish."""

from __future__ import annotations

from threading import Event

import pytest

from .hang_guard import eventually, finishes

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_a_step_that_finishes_returns_its_result() -> None:
    assert finishes(lambda: 7, what="a step") == 7


def test_a_step_that_fails_raises_its_own_failure() -> None:
    def fail() -> None:
        raise RuntimeError("synthetic step failure")

    with pytest.raises(RuntimeError, match="synthetic step failure"):
        finishes(fail, what="a step")


def test_a_step_held_for_good_fails_naming_what_waited() -> None:
    held = Event()
    try:
        # Nothing sets the event until the step has been given up on, so the step cannot finish.
        with pytest.raises(AssertionError, match="a held producer did not finish"):
            finishes(held.wait, what="a held producer", within=0.05)
    finally:
        held.set()


def test_a_condition_that_holds_only_after_some_polls_is_waited_for() -> None:
    polls: list[int] = []

    def third_poll() -> bool:
        polls.append(len(polls))
        return len(polls) == 3

    eventually(third_poll, what="a third poll", interval=0)

    assert polls == [0, 1, 2]


def test_a_condition_that_never_holds_fails_naming_what_waited() -> None:
    with pytest.raises(AssertionError, match="a record that never arrives did not happen"):
        eventually(lambda: False, what="a record that never arrives", within=0.05, interval=0.005)
