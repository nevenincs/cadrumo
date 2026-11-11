"""The published verification refusal keeps the statement offered after the door of an absent earlier return."""

from __future__ import annotations

import json

import pytest

from ....core.operator_action_enums import ActionArgumentStatus, ActionConditionality, ActionEvidenceProvenance
from ..precondition_action_bindings import AlternativeActionArguments
from ..preconditions import (
    ATTEST_PRIOR_VALUE_ACTION_ID,
    ModeloPreconditionFailure,
    build_modelo_precondition_failure_for_scenario,
)
from ..verification_projection import ModeloPreconditionSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WORK_UNIT_ID = "5f0c1e2d3b4a5968"
_SOURCE_YEAR = 7


def _failure(scenario: str, alternatives: tuple[AlternativeActionArguments, ...]) -> ModeloPreconditionFailure:
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.work.verify",
        scenario_id=f"modelo.work.verify.cross_period_dependency.{scenario}",
        evidence_id="modelo.work.verify.cross_period_dependency",
        evidence_values={"work_unit_id": _WORK_UNIT_ID, "source_modelo": "100"},
        provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        action_argument_values={"modelo": "100", "period": "0A", "year": _SOURCE_YEAR},
        alternative_actions=alternatives,
    )


def _statement() -> AlternativeActionArguments:
    return AlternativeActionArguments(
        action_id=ATTEST_PRIOR_VALUE_ACTION_ID,
        action_argument_values={
            "work_unit_id": _WORK_UNIT_ID,
            "modelo": "130",
            "year": _SOURCE_YEAR + 1,
            "period": "1T",
            "binding_id": "irpf.previous_year_economic_activity_net_income",
        },
        missing_action_arguments=("value",),
    )


def test_the_snapshot_restores_the_statement_after_the_creation_door() -> None:
    failure = _failure("source_absent_attestable", (_statement(),))

    snapshot = ModeloPreconditionSnapshot.from_failure(failure)
    restored = ModeloPreconditionSnapshot.model_validate_json(snapshot.model_dump_json())

    assert restored == snapshot
    assert restored.to_failure() == failure
    assert restored.action is not None
    assert restored.action.action_id == "operator.modelo.work.create"
    assert [item.action.action_id for item in restored.alternative_actions] == [ATTEST_PRIOR_VALUE_ACTION_ID]
    statement = restored.alternative_actions[0]
    assert statement.conditionality is ActionConditionality.REQUIRES_ARGUMENTS
    assert statement.missing_argument_names == ("value",)
    assert [
        item.argument_name for item in statement.argument_bindings if item.status is ActionArgumentStatus.MISSING
    ] == ["value"]


def test_a_snapshot_without_alternatives_leaves_the_list_out_of_its_record() -> None:
    failure = _failure("source_absent", ())

    snapshot = ModeloPreconditionSnapshot.from_failure(failure)
    document = json.loads(snapshot.model_dump_json())

    assert set(document) == {
        "subject_leaf_key",
        "scenario_id",
        "failed_condition_id",
        "evidence",
        "action",
        "argument_bindings",
        "missing_argument_names",
        "conditionality",
        "no_recovery_outcome",
    }
    assert document["action"] == {"action_id": "operator.modelo.work.create"}
    assert ModeloPreconditionSnapshot.model_validate_json(snapshot.model_dump_json()).to_failure() == failure
