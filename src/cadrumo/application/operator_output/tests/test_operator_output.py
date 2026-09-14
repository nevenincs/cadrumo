"""Pure application contracts for operator-output result validation."""

from __future__ import annotations

import json

import pytest

from cadrumo.application.operator_output.emit import emit_operator_json_success
from cadrumo.application.wizard.results import ConfigProfileCreateResult, ProfileWizardStatus
from cadrumo.core.json_contract import OutputSchemaError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_emit_operator_json_success_validates_result_shape_not_command_registration(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The funnel validates the result's schema; the command binding is static."""
    result = ConfigProfileCreateResult(profile_name="probe", status=ProfileWizardStatus.CREATED, active_profile="probe")

    emit_operator_json_success("operator_output.tests.probe", result)

    document = json.loads(capsys.readouterr().out)
    assert document["command"] == "operator_output.tests.probe"
    assert document["result"]["profile_name"] == "probe"


def test_emit_operator_json_success_refuses_a_result_outside_the_registered_schema(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A registered command cannot bypass strict result fields."""
    with pytest.raises(OutputSchemaError) as refusal:
        emit_operator_json_success(
            "config.profile.create",
            {"profile_name": "probe", "status": 1, "active_profile": "probe"},
        )

    message = str(refusal.value)
    assert "config.profile.create" in message
    assert "is not a strict output schema" in message

    assert capsys.readouterr().out == ""
