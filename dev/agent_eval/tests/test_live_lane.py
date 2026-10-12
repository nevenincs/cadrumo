"""The live lane's recipes reach exactly the request they name, and its scenario list is closed.

The recipes pass a scenario, a run count and optional flags straight through;
the parsed request must carry numbers, not class attributes, because the spend
bound becomes a command-line budget for the model driver.
"""

from __future__ import annotations

import pytest

from ..live.access import ACCESS_SCENARIOS
from ..live.lane import DEFAULT_RUNS, known_scenarios, parse_request
from ..live.scenario import scenario_names

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_live_recipe_defaults_to_three_runs_and_a_numeric_budget() -> None:
    request = parse_request(["live", "modelo_130_dr130"])
    assert (request.live, request.runs, request.measure_stale_package) == (True, DEFAULT_RUNS, False)
    assert isinstance(request.limits.max_usd, float)
    assert request.limits.max_usd > 0


def test_the_floor_recipe_passes_its_flags_through() -> None:
    request = parse_request(["floor", "access-api-key", "1", "--measure-stale-package", "--max-usd", "0.25"])
    assert (request.live, request.scenario, request.runs) == (False, "access-api-key", 1)
    assert request.measure_stale_package
    assert request.limits.max_usd == 0.25


def test_an_unknown_scenario_is_refused_before_anything_runs() -> None:
    with pytest.raises(SystemExit):
        parse_request(["live", "no-such-scenario"])


def test_every_scenario_is_a_file_or_an_access_scenario() -> None:
    assert set(known_scenarios()) == set(scenario_names()) | set(ACCESS_SCENARIOS)
