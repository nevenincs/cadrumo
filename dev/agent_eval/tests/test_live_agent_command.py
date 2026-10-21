"""The operator-supplied agent command is run, fed and recorded as the options say, with a real child process.

The child is ``sys.executable -c`` running a tiny script that writes the JSON
event lines the stream translator reads, and reports back what it was given:
its arguments, the environment variables it can see, and the MCP configuration
file it was pointed at. Nothing in the driver is replaced.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from ..live.capture import Scrubber
from ..live.drivers import DriverKind, Limits, McpLaunch, run_agent_command
from ..live.lane import parse_request
from ..live.outcome import UnavailableError
from ..live.recorder import TrajectoryRecorder

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CREDENTIAL = "Planted-model-credential-value-7731"
_OTHER = "Planted-unnamed-host-value-5512"

_SCRIPT = """
import json, os, sys
prompt = sys.stdin.read()
seen = {name: value for name, value in os.environ.items() if name.startswith("PLANTED_")}
with open(sys.argv[2], encoding="utf-8") as handle:
    configuration = json.load(handle)
print("not an event")
print(json.dumps({"type": "system", "subtype": "init", "model": sys.argv[1] + "-reported"}))
report = {"argv": sys.argv[1:], "environment": seen, "servers": sorted(configuration["mcpServers"]), "prompt": prompt}
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": json.dumps(report)}]}}))
print(json.dumps({"type": "result", "subtype": "success", "num_turns": 1, "total_cost_usd": 0.01}))
"""

_PLACEHOLDER_ARGUMENTS = ("{model}", "{mcp_config}", "{system}", "{max_turns}", "{max_usd}")


def _command(*arguments: str) -> tuple[str, ...]:
    return (sys.executable, "-c", _SCRIPT, *arguments)


def _launch(directory: Path) -> McpLaunch:
    return McpLaunch("cadrumo-mcp", ("--stdio",), {"ONLY": "this"}, directory)


def _run(
    directory: Path,
    command: tuple[str, ...],
    *,
    model: str = "declared-model",
    credential_variables: tuple[str, ...] = (),
    limits: Limits | None = None,
    recorder: TrajectoryRecorder | None = None,
    extra_ambient: dict[str, str] | None = None,
) -> tuple[Any, TrajectoryRecorder]:
    recorder = recorder or TrajectoryRecorder(scrubber=Scrubber(()))
    report = run_agent_command(
        _launch(directory),
        recorder,
        command=command,
        model=model,
        credential_variables=credential_variables,
        system="be careful",
        phases=["do the task"],
        limits=limits or Limits(max_turns=7, max_usd=0.5),
        work_directory=directory,
        ambient={**os.environ, **(extra_ambient or {})},
    )
    return report, recorder


def _reported(recorder: TrajectoryRecorder) -> dict[str, Any]:
    return json.loads(recorder.narrations[0].text)


def test_every_placeholder_is_filled_for_the_child(tmp_path: Path) -> None:
    report, recorder = _run(tmp_path, _command(*_PLACEHOLDER_ARGUMENTS))
    told = _reported(recorder)
    model, configuration, system, turns, budget = told["argv"]
    assert model == "declared-model"
    assert Path(configuration).name == "mcp.json"
    assert (system, turns, budget) == ("be careful", "7", "0.50")
    assert told["servers"] == ["cadrumo"]
    assert told["prompt"] == "do the task"
    assert report.phases_completed == 1
    assert not (tmp_path / "agent-command").exists()


def test_an_unknown_placeholder_is_refused_before_anything_runs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown placeholder"):
        _run(tmp_path, _command("{model}", "{provider}"))
    assert not (tmp_path / "agent-command").exists()


def test_a_missing_agent_command_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(UnavailableError) as raised:
        _run(tmp_path, ())
    assert raised.value.reason == "agent_command_missing"


def test_an_executable_that_is_not_installed_is_unavailable(tmp_path: Path) -> None:
    with pytest.raises(UnavailableError) as raised:
        _run(tmp_path, ("no-such-agent-executable-9f3a", "{model}"))
    assert raised.value.reason == "agent_command_missing"
    assert not (tmp_path / "agent-command").exists()


def test_only_the_named_credential_variables_reach_the_child(tmp_path: Path) -> None:
    ambient = {"PLANTED_NAMED": _CREDENTIAL, "PLANTED_UNNAMED": _OTHER}
    _, recorder = _run(
        tmp_path,
        _command("{model}", "{mcp_config}"),
        credential_variables=("PLANTED_NAMED",),
        extra_ambient=ambient,
    )
    assert _reported(recorder)["environment"] == {"PLANTED_NAMED": _CREDENTIAL}


def test_the_named_credential_is_scrubbed_from_what_is_kept(tmp_path: Path) -> None:
    scrubber = Scrubber((("provider_credential", _CREDENTIAL),))
    recorder = TrajectoryRecorder(scrubber=scrubber, known_secrets=(_CREDENTIAL,))
    _run(
        tmp_path,
        _command("{model}", "{mcp_config}"),
        credential_variables=("PLANTED_NAMED",),
        recorder=recorder,
        extra_ambient={"PLANTED_NAMED": _CREDENTIAL},
    )
    kept = recorder.trajectory(scenario="s", persona="p", session_id="r").model_dump_json()
    assert _CREDENTIAL not in kept
    assert "provider_credential" in kept
    assert [failure.invariant for failure in recorder.failures] == ["no_secret_in_narration"]


def test_an_unnamed_variable_never_reaches_the_child(tmp_path: Path) -> None:
    _, recorder = _run(
        tmp_path,
        _command("{model}", "{mcp_config}"),
        extra_ambient={"PLANTED_UNNAMED": _OTHER},
    )
    assert _reported(recorder)["environment"] == {}


def test_the_declared_model_is_recorded_beside_the_reported_one(tmp_path: Path) -> None:
    report, _ = _run(tmp_path, _command("{model}", "{mcp_config}"), model="declared-model")
    assert report.driver is DriverKind.AGENT_COMMAND
    assert report.model_requested == "declared-model"
    assert report.model_reported == "declared-model-reported"
    assert (report.turns, report.cost_usd) == (1, 0.01)


def test_the_command_line_options_reach_the_request() -> None:
    request = parse_request(
        [
            "live",
            "modelo_130_dr130",
            "1",
            "--agent-arg",
            "agent-exe",
            "--agent-arg",
            "{model}",
            "--model",
            "declared-model",
            "--credential-variable",
            "FIRST_VARIABLE",
            "--credential-variable",
            "SECOND_VARIABLE",
        ]
    )
    assert request.agent_command == ("agent-exe", "{model}")
    assert request.model == "declared-model"
    assert request.credential_variables == ("FIRST_VARIABLE", "SECOND_VARIABLE")


def test_without_the_options_the_request_has_no_agent() -> None:
    request = parse_request(["live", "modelo_130_dr130"])
    assert (request.agent_command, request.model, request.credential_variables) == ((), "", ())
