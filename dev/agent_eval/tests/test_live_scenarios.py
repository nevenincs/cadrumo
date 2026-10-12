"""Every live scenario file loads, carries no secret, and stays inside what the live lane can reach.

The required subsequence must follow the modelo lifecycle and name no remote
read, because a run on an isolated root cannot reach the tax agency. The
Modelo 130 figures must be the published DR 130 example the value oracle
already grounds, so a drifted file is caught here rather than in a paid run.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from .._models import LIFECYCLE_STAGE_ORDER
from ..live.scenario import LiveScenario, load_scenario, scenario_names

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SECRET_WORDS = ("password", "passphrase", "api key", "contraseña", "sk-ant-")


@pytest.mark.parametrize("name", scenario_names())
def test_each_scenario_loads_and_keeps_the_lifecycle_order(name: str) -> None:
    scenario = load_scenario(name)
    stages = [key for key in scenario.required_trajectory if key in LIFECYCLE_STAGE_ORDER]
    assert stages == sorted(stages, key=LIFECYCLE_STAGE_ORDER.index)
    assert not any(key.startswith("modelo.reconcile") for key in scenario.required_trajectory)
    assert scenario.golden().expected_trajectory == scenario.required_trajectory


@pytest.mark.parametrize("name", scenario_names())
def test_no_scenario_prompt_carries_a_secret(name: str) -> None:
    scenario = load_scenario(name)
    task = scenario.task(Path("C:/run/exports") / scenario.export_file).lower()
    for word in _SECRET_WORDS:
        assert word not in task, word
    assert "never sign in" in scenario.prompt.system


def test_the_modelo_130_scenario_is_the_published_dr130_example() -> None:
    scenario = load_scenario("modelo_130_dr130")
    income = sum(Decimal(row.amount) for row in scenario.rows if row.direction == "INCOMING")
    expenses = sum(Decimal(row.amount) for row in scenario.rows if row.direction == "OUTGOING")
    assert (income, expenses) == (Decimal(12000), Decimal(4000))
    assert {key: Decimal(value) for key, value in scenario.expected.casillas.items()} == {
        "04": Decimal(1600),
        "07": Decimal(1600),
        "13": Decimal(0),
    }
    assert Decimal(scenario.calculation.bindings["irpf.previous_year_economic_activity_net_income"]) > 12000


def test_a_task_without_the_export_placeholder_is_refused(tmp_path: Path) -> None:
    source = load_scenario("modelo_130_dr130").model_dump(mode="json")
    source["prompt"]["task"] = "Export it somewhere."
    with pytest.raises(ValueError, match="export_path"):
        LiveScenario.model_validate(source, strict=False)
