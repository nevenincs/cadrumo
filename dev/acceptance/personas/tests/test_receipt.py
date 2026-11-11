"""A persona receipt counts its checks, separates findings from failures and serialises to JSON."""

from __future__ import annotations

import json

import pytest

from ..assessment import CalculationObservation, assess_value
from ..receipt import CheckStatus, CliGap, PersonaReceipt, StepOutcome, StepRecord
from .catalogue_support import envelope, value_with_casillas

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _receipt(observed: CalculationObservation) -> PersonaReceipt:
    value = value_with_casillas()
    return PersonaReceipt(
        persona="autonomo-fontanero",
        floor=envelope().floor,
        horizon=envelope().horizon,
        as_of="as-of",
        authority_generation="generation",
        executable="aeat",
        steps=(
            StepRecord(step="profile.create", command="config profile create", outcome=StepOutcome.OK),
            StepRecord(
                step="household.ascendants",
                command="",
                outcome=StepOutcome.GAP,
            ),
        ),
        cli_gaps=(CliGap(persona="autonomo-fontanero", step="household.ascendants", missing="no command"),),
        values=assess_value(value.year.resolve(envelope()), value, observed),
        commands=3,
    )


def test_a_gap_is_a_finding_and_not_a_failure() -> None:
    receipt = _receipt(CalculationObservation(unobserved="no route"))
    assert receipt.passed()
    assert receipt.summary()["GAP"] == len(value_with_casillas().casillas)
    assert receipt.summary()["cli_gaps"] == 1
    assert receipt.summary()["step_gap"] == 1


def test_a_failed_casilla_fails_the_receipt() -> None:
    receipt = _receipt(CalculationObservation(casillas={}))
    assert not receipt.passed()
    assert receipt.summary()[CheckStatus.FAIL.value] == len(value_with_casillas().casillas)


def test_the_receipt_round_trips_through_json() -> None:
    receipt = _receipt(CalculationObservation(refusal="ERROR_X"))
    document = json.loads(json.dumps(receipt.to_dict()))
    assert document["persona"] == "autonomo-fontanero"
    assert document["passed"] is False
    assert document["cli_gaps"] == [
        {"persona": "autonomo-fontanero", "step": "household.ascendants", "missing": "no command"}
    ]
    assert [row["status"] for row in document["values"]] == ["FAIL"] * len(value_with_casillas().casillas)
    assert document["steps"][1]["outcome"] == "gap"
