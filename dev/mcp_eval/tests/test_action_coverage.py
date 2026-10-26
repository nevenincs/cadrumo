"""Tests for production-derived operator action coverage."""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from .._action_coverage import (
    LeafConditionScenario,
    LeafConditionScenarioMatrix,
    leaf_condition_scenario_matrix,
    production_leaf_condition_scenario_matrix,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_production_matrix_is_live_surface_resolved_and_keeps_outcome_authority_on_profiles() -> None:
    """The evaluator sees every declared profile without recreating action expectations."""
    matrix = production_leaf_condition_scenario_matrix()

    assert tuple(LeafConditionScenario.model_fields) == ("profile",)
    assert tuple(LeafConditionScenarioMatrix.model_fields) == ("rows",)
    assert matrix.rows == tuple(sorted(matrix.rows, key=lambda row: row.identity))
    assert len({row.identity for row in matrix.rows}) == len(matrix.rows)
    assert any(row.profile.resolved_action is not None for row in matrix.rows)
    assert any(row.profile.declaration.no_recovery_outcome is not None for row in matrix.rows)
    for row in matrix.rows:
        assert row.subject_leaf_key == row.profile.declaration.subject_leaf_key
        if row.profile.declaration.action is None:
            assert row.profile.resolved_action is None
        else:
            assert row.profile.resolved_action is not None
            assert row.profile.resolved_action.action_id == row.profile.declaration.action.action_id


def test_matrix_is_constructed_only_from_the_pre_resolved_production_join() -> None:
    """The matrix constructor cannot accept a second action catalogue or schema inventory."""
    parameters = inspect.signature(leaf_condition_scenario_matrix).parameters

    assert tuple(parameters) == ("resolution",)


def test_matrix_refuses_a_duplicate_resolved_production_identity() -> None:
    """A second declaration for one leaf-condition-scenario cannot be hidden in evaluation."""
    matrix = production_leaf_condition_scenario_matrix()

    with pytest.raises(ValidationError, match="matrix identities must be unique"):
        LeafConditionScenarioMatrix(rows=(matrix.rows[0], matrix.rows[0]))


def test_matrix_lookup_fails_closed_for_a_nonproduction_identity() -> None:
    """Evaluator callers cannot silently manufacture a scenario row."""
    matrix = production_leaf_condition_scenario_matrix()

    with pytest.raises(KeyError, match="unknown leaf-condition-scenario identity"):
        matrix.row_for(("modelo.work.unknown", "guard.unknown", "scenario.unknown"))
