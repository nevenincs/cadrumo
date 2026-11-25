"""The runtime CLI resolves and shows every door a refusal offers, primary first."""

from __future__ import annotations

import json

import pytest

from cadrumo.application.modelo.precondition_action_bindings import AlternativeActionArguments
from cadrumo.application.modelo.preconditions import (
    ATTEST_PRIOR_VALUE_ACTION_ID,
    build_modelo_precondition_failure_for_scenario,
)
from cadrumo.application.operator_actions.models import PreconditionVerdict
from cadrumo.application.operator_surface.action_targets import ACTION_TARGETS
from cadrumo.core.operator_action_enums import ActionEvidenceProvenance
from cadrumo_client.commands.output import precondition_action_lines

from ..presentation import resolve_cli_precondition_action

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WORK_UNIT_ID = "5f0c1e2d3b4a5968"
_SOURCE_YEAR = 7


def _verdict(*, attestable: bool) -> PreconditionVerdict:
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
    scenario = "filed_evidence_missing_attestable" if attestable else "filed_evidence_missing"
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.export",
        scenario_id=f"modelo.export.cross_period_dependency.{scenario}",
        evidence_id="modelo.export.cross_period_dependency",
        evidence_values={"work_unit_id": _WORK_UNIT_ID, "source_modelo": "100"},
        provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        action_argument_values={"modelos": "100", "period": "0A", "year": _SOURCE_YEAR},
        alternative_actions=(statement,) if attestable else (),
    ).verdict


def _recorded_path(command_key: str) -> tuple[str, ...]:
    target = next(item for item in ACTION_TARGETS if item.command_key == command_key)
    return (target.program.executable_name, *target.cli_path)


def test_the_runtime_resolver_puts_the_executable_before_every_door() -> None:
    resolved = resolve_cli_precondition_action(_verdict(attestable=True))

    assert resolved.action is not None
    assert resolved.action.cli_path == _recorded_path("app.live.filed.pull")
    assert [item.action.action_id for item in resolved.alternative_actions] == [ATTEST_PRIOR_VALUE_ACTION_ID]
    assert resolved.alternative_actions[0].action.cli_path == _recorded_path("modelo.work.attest_prior_value")


def test_the_runtime_text_rows_show_the_statement_after_the_capture_door() -> None:
    lines = precondition_action_lines(resolve_cli_precondition_action(_verdict(attestable=True)))

    assert lines[7].split("\t", 1)[0] == "precondition_action.alternative_actions"
    alternatives = json.loads(lines[7].split("\t", 1)[1])
    assert alternatives[0]["action"]["cli_path"] == list(_recorded_path("modelo.work.attest_prior_value"))
    assert alternatives[0]["missing_argument_names"] == ["value"]


def test_a_runtime_refusal_with_one_door_adds_no_row() -> None:
    lines = precondition_action_lines(resolve_cli_precondition_action(_verdict(attestable=False)))

    # Seven rows of the refusal, then the served words, their language and the operations the door submits.
    assert len(lines) == 10
    assert not any(line.startswith("precondition_action.alternative_actions") for line in lines)
