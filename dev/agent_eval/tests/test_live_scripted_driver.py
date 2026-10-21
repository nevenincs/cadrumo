"""The scripted floor client sends the person's Modelo 303 answer with the calculation, as a person would."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, override

import anyio
import pytest

from ..live.drivers import RecordedTools, run_scripted
from ..live.scenario import load_scenario

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _EchoTools(RecordedTools):
    """Settles every submitted operation at once with a projection shaped like the real one."""

    def __init__(self) -> None:  # no client session: the double answers every call itself
        self.submitted: list[dict[str, Any]] = []

    @override
    async def call(self, name: str, arguments: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str, bool]:
        if name == "status":
            return {"session": "present"}, "", False
        if name == "execute":
            self.submitted.append(dict(arguments))
            receipt = {"operation_id": str(len(self.submitted))}
            return {"outcome": "submitted", "start": {"kind": "operation_acknowledged"}, "receipt": receipt}, "", False
        if name == "observe":
            projection = {"lifecycle": "terminal"}
            return {"outcome": "reply", "reply": {"observation": {"projection": projection}}}, "", False
        projection = {
            "transaction": {"transaction_id": "t"},
            "outcome": {"unit": {"work_unit_id": "w"}},
            "calculation_revision_id": "r",
        }
        return {"document": {"outcome": "success", "projection": projection}}, "", False


def _calculation_payload(joint_return_elected: bool | None) -> dict[str, Any]:
    scenario = load_scenario("modelo_303_quarter")
    tools = _EchoTools()
    run = anyio.run(
        lambda: run_scripted(
            tools,
            profile_id="p",
            rows=scenario.rows,
            modelo=scenario.modelo,
            filing_year=scenario.filing_year,
            period=scenario.period,
            casillas=scenario.calculation.casillas,
            bindings=scenario.calculation.bindings,
            export_path=Path("export.txt"),
            joint_return_elected=joint_return_elected,
        )
    )
    assert run.completed, run.refusal
    (calculate,) = (call for call in tools.submitted if call["definition_id"] == "modelo.work.calculate")
    payload = calculate["payload"]
    assert isinstance(payload, dict)
    return payload


@pytest.mark.parametrize("elected", [False, True])
def test_the_calculation_carries_the_persons_joint_return_answer(elected: bool) -> None:
    payload = _calculation_payload(elected)
    assert payload["ordinary_m303_filing_evidence"] == {"joint_return_elected": elected}
    assert payload["caller_context"] == "explicit"


def test_a_modelo_that_asks_no_joint_return_question_sends_none() -> None:
    assert "ordinary_m303_filing_evidence" not in _calculation_payload(None)
