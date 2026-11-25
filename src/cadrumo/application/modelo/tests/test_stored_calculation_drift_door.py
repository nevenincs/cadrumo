"""A stored revision that no longer matches its content address opens the recalculation of its work unit."""

from __future__ import annotations

import pytest

from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ..action_errors import StoredCalculationDriftError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CALCULATE_ACTION = "operator.modelo.work.calculate"


def test_a_drifted_revision_naming_its_work_unit_opens_calculate_with_it_bound() -> None:
    error = StoredCalculationDriftError(
        translated_message="errors.storage.stored_data_validation_boundary",
        context={"calculation_revision_id": "revision-1", "work_unit_id": "work-unit-1"},
    )

    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == _CALCULATE_ACTION
    assert {
        binding.argument_name: binding.value for binding in verdict.argument_bindings if binding.value is not None
    } == {"work_unit_id": "work-unit-1"}
    assert not verdict.missing_argument_names


def test_a_drifted_revision_without_its_work_unit_leaves_it_to_the_operator() -> None:
    verdict = nested_terminal_precondition_verdict(StoredCalculationDriftError("content-address mismatch"))

    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == _CALCULATE_ACTION
    assert set(verdict.missing_argument_names) == {"work_unit_id"}
