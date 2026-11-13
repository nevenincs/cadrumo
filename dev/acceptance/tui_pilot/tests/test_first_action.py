"""The drive starts with the calculation whenever the return holds one and the form does not offer it."""

from __future__ import annotations

import pytest

from cadrumo.application.modelo.work_form_next_step import ModeloFormNextAction

from ..pilot import first_action

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    "served",
    [
        ModeloFormNextAction.VERIFY,
        ModeloFormNextAction.RESOLVE,
        ModeloFormNextAction.FILL,
        ModeloFormNextAction.EXPORT,
        None,
    ],
)
def test_a_held_calculation_is_pressed_again_before_the_step_the_form_serves(
    served: ModeloFormNextAction | None,
) -> None:
    assert first_action(served, calculated=True) is ModeloFormNextAction.RECALCULATE


@pytest.mark.parametrize("served", [ModeloFormNextAction.CALCULATE, ModeloFormNextAction.RECALCULATE])
def test_a_served_calculation_is_the_first_step_as_it_is_served(served: ModeloFormNextAction) -> None:
    assert first_action(served, calculated=True) is served
    assert first_action(served, calculated=False) is served


@pytest.mark.parametrize("served", [ModeloFormNextAction.FILL, ModeloFormNextAction.VERIFY, None])
def test_a_return_with_no_calculation_starts_with_what_the_form_serves(served: ModeloFormNextAction | None) -> None:
    assert first_action(served, calculated=False) is served
