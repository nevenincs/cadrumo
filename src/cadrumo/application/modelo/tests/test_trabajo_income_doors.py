"""An unstated work-income box serves the one statement first and keeps the box's own door beside it.

The employer contributions and protected-estate boxes no payer certificate fills share one statement
that they hold nothing; the disability increase and the expense limits have no such statement and keep
their single per-box door.
"""

from __future__ import annotations

import pytest

from ....core.operator_action_enums import ActionEvidenceProvenance
from ...operator_actions.catalogue import lookup_action
from ...operator_surface.models import ManifestActionProfile
from ..precondition_action_bindings import AlternativeActionArguments
from ..preconditions import (
    ATTEST_WORK_INCOME_ACTION_ID,
    MODELO_PRECONDITION_PROFILES,
    ModeloPreconditionFailure,
    build_modelo_precondition_failure_for_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LEAF = "modelo.work.verify"
_SCENARIO_PREFIX = "modelo.work.verify.trabajo_income."


def _profile(scenario: str) -> ManifestActionProfile:
    (profile,) = (
        item
        for item in MODELO_PRECONDITION_PROFILES
        if item.subject_leaf_key == _LEAF and item.scenario_id == f"{_SCENARIO_PREFIX}{scenario}"
    )
    return profile


@pytest.mark.parametrize(
    ("scenario", "alternative"),
    [
        ("unstated", "operator.modelo.work.set_value"),
        ("unstated_source", "operator.modelo.work.override"),
    ],
)
def test_an_unstated_income_box_declares_the_statement_as_its_door_and_the_box_door_as_alternative(
    scenario: str, alternative: str
) -> None:
    profile = _profile(scenario)

    assert profile.action is not None
    assert profile.action.action_id == ATTEST_WORK_INCOME_ACTION_ID
    assert tuple(item.action_id for item in profile.alternative_actions) == (alternative,)
    assert [spec.argument_name for spec in lookup_action(ATTEST_WORK_INCOME_ACTION_ID).argument_specifications] == [
        "work_unit_id"
    ]


@pytest.mark.parametrize(
    ("scenario", "action_id"),
    [
        ("disability_increase_unstated", "operator.modelo.work.set_value"),
        ("expense_above_limit", "operator.modelo.work.set_value"),
        ("expense_above_limit_source", "operator.modelo.work.override"),
    ],
)
def test_the_disability_and_expense_scenarios_keep_their_single_per_box_door(scenario: str, action_id: str) -> None:
    profile = _profile(scenario)

    assert profile.action is not None
    assert profile.action.action_id == action_id
    assert profile.alternative_actions == ()


def _build(
    scenario: str,
    alternatives: tuple[AlternativeActionArguments, ...],
) -> ModeloPreconditionFailure:
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=_LEAF,
        scenario_id=f"{_SCENARIO_PREFIX}{scenario}",
        evidence_id="modelo.work.verify.trabajo_income",
        evidence_values={"calculation_revision_id": "r1", "work_unit_id": "w1", "casilla_id": "0008"},
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_argument_values={"work_unit_id": "w1"},
        alternative_actions=alternatives,
    )


def test_a_box_read_from_no_binding_binds_the_statement_and_offers_its_own_value_door() -> None:
    failure = _build(
        "unstated",
        (
            AlternativeActionArguments(
                action_id="operator.modelo.work.set_value",
                action_argument_values={"work_unit_id": "w1", "casilla_id": "0008"},
                missing_action_arguments=("value",),
            ),
        ),
    )

    assert failure.verdict.action is not None
    assert failure.verdict.action.action_id == ATTEST_WORK_INCOME_ACTION_ID
    (offered,) = failure.verdict.alternative_actions
    assert offered.action.action_id == "operator.modelo.work.set_value"
    assert {
        binding.argument_name: binding.value for binding in offered.argument_bindings if binding.value is not None
    } == {
        "work_unit_id": "w1",
        "casilla_id": "0008",
    }
    assert offered.missing_argument_names == ("value",)


@pytest.mark.parametrize(
    "alternatives",
    [
        (),
        (
            AlternativeActionArguments(
                action_id="operator.modelo.work.override",
                action_argument_values={"work_unit_id": "w1", "binding_id": "b"},
                missing_action_arguments=("value",),
            ),
        ),
    ],
)
def test_the_statement_door_refuses_a_missing_or_wrong_alternative(
    alternatives: tuple[AlternativeActionArguments, ...],
) -> None:
    with pytest.raises(ValueError, match="alternative actions contradict"):
        _build("unstated", alternatives)
