"""A calculation states which head it replaced and what became of the person's entries in it."""

from __future__ import annotations

from typing import cast

import pytest

from ....domain.modelos.work_unit import WorkUnit
from ..calculate_input import WorkCalculateInputBundle
from ..calculation_action_ports import CalculationActionPorts
from ..operation_definitions import PreparedModeloWorkCalculation, replaced_calculation_head
from ..work_calculation_contracts import (
    ModeloOperatorEntriesCarry,
    ModeloWorkCalculateCallerContext,
    ModeloWorkCalculateReplacedHead,
    ModeloWorkCalculateRequest,
)
from .test_wizard_context_operation import _unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EARLIER_HEAD = "a" * 64
_NEW_HEAD = "b" * 64


def _unit_at(head: str | None) -> WorkUnit:
    return _unit().model_copy(update={"current_calculation_revision_id": head})


def _prepared(unit: WorkUnit, *, operator_layer_recorded: bool) -> PreparedModeloWorkCalculation:
    """The admitted unit and its inputs; the head statement reads no port."""
    return PreparedModeloWorkCalculation(
        work_unit=unit,
        ports=cast(CalculationActionPorts, object()),
        inputs=WorkCalculateInputBundle.build(
            casilla_inputs={},
            binding_values={},
            enum_binding_values={},
            relation_values={},
            detail_rows=(),
            borrador_snapshot_id=None,
            record_operator_layer=operator_layer_recorded,
        ),
    )


def _request(unit: WorkUnit, caller_context: ModeloWorkCalculateCallerContext) -> ModeloWorkCalculateRequest:
    return ModeloWorkCalculateRequest(work_unit_id=unit.work_unit_id, actor="operator", caller_context=caller_context)


@pytest.mark.parametrize(
    ("caller_context", "operator_layer_recorded", "carried"),
    [
        (ModeloWorkCalculateCallerContext.REPLAY_HEAD, True, ModeloOperatorEntriesCarry.REPLAYED),
        (ModeloWorkCalculateCallerContext.REPLAY_HEAD, False, ModeloOperatorEntriesCarry.NOT_RECORDED),
        (ModeloWorkCalculateCallerContext.EXPLICIT, True, ModeloOperatorEntriesCarry.REPLACED_BY_REQUEST),
    ],
)
def test_a_calculation_that_moves_the_head_names_the_earlier_one_and_what_it_carried(
    caller_context: ModeloWorkCalculateCallerContext,
    operator_layer_recorded: bool,
    carried: ModeloOperatorEntriesCarry,
) -> None:
    """The earlier revision is named so it can be read, with whether the person's entries reached the new head."""
    earlier = _unit_at(_EARLIER_HEAD)

    replaced = replaced_calculation_head(
        _prepared(earlier, operator_layer_recorded=operator_layer_recorded),
        _request(earlier, caller_context),
        _unit_at(_NEW_HEAD),
    )

    assert replaced == ModeloWorkCalculateReplacedHead(calculation_revision_id=_EARLIER_HEAD, operator_entries=carried)


@pytest.mark.parametrize("caller_context", list(ModeloWorkCalculateCallerContext))
def test_a_first_calculation_replaces_nothing(caller_context: ModeloWorkCalculateCallerContext) -> None:
    """A work unit with no calculation yet has no earlier head to name."""
    never_calculated = _unit_at(None)

    replaced = replaced_calculation_head(
        _prepared(never_calculated, operator_layer_recorded=True),
        _request(never_calculated, caller_context),
        _unit_at(_NEW_HEAD),
    )

    assert replaced is None


@pytest.mark.parametrize("caller_context", list(ModeloWorkCalculateCallerContext))
def test_a_calculation_that_leaves_the_same_revision_current_replaces_nothing(
    caller_context: ModeloWorkCalculateCallerContext,
) -> None:
    """A recalculation that reproduces the head moved nothing, whatever the request carried."""
    current = _unit_at(_EARLIER_HEAD)

    replaced = replaced_calculation_head(
        _prepared(current, operator_layer_recorded=False),
        _request(current, caller_context),
        _unit_at(_EARLIER_HEAD),
    )

    assert replaced is None
