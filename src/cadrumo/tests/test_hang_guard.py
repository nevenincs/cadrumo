"""The hang guard returns a step's result and its failure, and fails only a step that cannot finish."""

from __future__ import annotations

from threading import Event

import pytest

from .hang_guard import finishes

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
