"""The CLI shows every door a refusal offers, primary first, and adds nothing when it offers one.

A first-quarter Modelo 130 reads the previous ejercicio's Modelo 100 (RIRPF art.
110.3.c). When that return is absent here and the filer may state its figure,
the refusal offers creating the return and, after it, stating the figure.
"""

from __future__ import annotations

import json

import pytest

from cadrumo_client.commands.output import precondition_action_lines

from ....application.modelo.action_errors import ModeloCrossPeriodCleanStateError
from ....application.modelo.preconditions import (
    ATTEST_PRIOR_VALUE_ACTION_ID,
    AlternativeActionArguments,
    ModeloPreconditionFailure,
    build_modelo_precondition_failure_for_scenario,
)
from ....core.operator_action_enums import ActionEvidenceProvenance
from ..command_specs import COMMAND_GRAPH
from ..common import cli_policy_refusal_projection, resolve_cli_precondition_action
from ..errors import render_error_payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WORK_UNIT_ID = "5f0c1e2d3b4a5968"
_SOURCE_YEAR = 7


def _failure(*, attestable: bool) -> ModeloPreconditionFailure:
    statement = AlternativeActionArguments(
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
    scenario = "source_absent_attestable" if attestable else "source_absent"
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.work.file",
        scenario_id=f"modelo.work.file.cross_period_dependency.{scenario}",
        evidence_id="modelo.work.file.cross_period_dependency",
        evidence_values={"work_unit_id": _WORK_UNIT_ID, "source_modelo": "100"},
        provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        action_argument_values={"modelo": "100", "period": "0A", "year": _SOURCE_YEAR},
        alternative_actions=(statement,) if attestable else (),
    )


def _refusal(failure: ModeloPreconditionFailure) -> ModeloCrossPeriodCleanStateError:
    return ModeloCrossPeriodCleanStateError(
        translated_message="application.modelo.errors.cross_period_clean_state_incomplete",
        context={"modelo": "130", "filing_year": str(_SOURCE_YEAR + 1), "period": "1T", "finding_count": "1"},
        precondition_failure=failure,
    )


def test_the_resolved_refusal_names_both_doors_under_the_executable() -> None:
    resolved = resolve_cli_precondition_action(_failure(attestable=True).verdict)
    executable = COMMAND_GRAPH.root().token

    assert resolved.action is not None
    assert resolved.action.cli_path == (executable, "app", "modelo", "work", "create")
    statement = resolved.alternative_actions[0]
    assert statement.action.action_id == ATTEST_PRIOR_VALUE_ACTION_ID
    assert statement.action.cli_path == (executable, "app", "modelo", "work", "attest-prior-value")
    assert statement.missing_argument_names == ("value",)


def test_the_json_refusal_carries_the_primary_door_then_the_statement() -> None:
    error = _refusal(_failure(attestable=True))
    projection = cli_policy_refusal_projection(error)
    assert projection is not None

    document = json.loads(render_error_payload(error, as_json=True, action=projection.precondition_action))

    action = document["error"]["action"]
    assert action["action"]["action_id"] == "operator.modelo.work.create"
    assert [item["action"]["action_id"] for item in action["alternative_actions"]] == [ATTEST_PRIOR_VALUE_ACTION_ID]
    assert action["alternative_actions"][0]["conditionality"] == "requires_arguments"


def test_the_text_refusal_adds_one_line_for_the_alternatives() -> None:
    error = _refusal(_failure(attestable=True))
    projection = cli_policy_refusal_projection(error)
    assert projection is not None

    text = render_error_payload(error, as_json=False, action=projection.precondition_action)

    lines = [line for line in text.splitlines() if line.startswith("  action.")]
    assert [line.split(":", 1)[0] for line in lines] == [
        "  action.failed_condition_id",
        "  action.evidence",
        "  action.action",
        "  action.argument_bindings",
        "  action.missing_argument_names",
        "  action.conditionality",
        "  action.no_recovery_outcome",
        "  action.alternative_actions",
    ]
    alternatives = json.loads(lines[-1].split(": ", 1)[1])
    assert [item["action"]["action_id"] for item in alternatives] == [ATTEST_PRIOR_VALUE_ACTION_ID]


def test_a_refusal_without_alternatives_renders_no_alternatives_line_or_member() -> None:
    error = _refusal(_failure(attestable=False))
    projection = cli_policy_refusal_projection(error)
    assert projection is not None
    action = projection.precondition_action

    text = render_error_payload(error, as_json=False, action=action)
    document = json.loads(render_error_payload(error, as_json=True, action=action))

    assert "action.alternative_actions" not in text
    assert "alternative_actions" not in document["error"]["action"]
    assert len([line for line in text.splitlines() if line.startswith("  action.")]) == 7


def test_the_shared_text_rows_add_the_alternatives_only_when_offered() -> None:
    offered = precondition_action_lines(resolve_cli_precondition_action(_failure(attestable=True).verdict))
    single = precondition_action_lines(resolve_cli_precondition_action(_failure(attestable=False).verdict))

    assert [line.split("\t", 1)[0] for line in single] == [
        "precondition_action.failed_condition_id",
        "precondition_action.evidence",
        "precondition_action.action",
        "precondition_action.argument_bindings",
        "precondition_action.missing_argument_names",
        "precondition_action.conditionality",
        "precondition_action.no_recovery_outcome",
    ]
    assert offered[:-1] == single
    assert offered[-1].split("\t", 1)[0] == "precondition_action.alternative_actions"
    assert len(offered) == len(single) + 1
