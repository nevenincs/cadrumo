"""The lane's ledger privacy run: one project that records nothing of the window, and what it is told to scan."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from .. import lane
from ..lane import (
    AGENT_PROJECT,
    PRIVACY_PROJECT,
    RECORDINGS,
    PrivacyScope,
    live_configuration,
    playwright_arguments,
    playwright_environment,
    recording_problems,
    written_directories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.fixture(scope="module")
def configuration(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """The live Playwright configuration as Node evaluates it, the way the lane reads it before a run."""
    assert shutil.which("node") is not None, "node is required to evaluate the live Playwright configuration"
    return live_configuration(tmp_path_factory.mktemp("results"))


def test_the_privacy_project_records_nothing_of_the_window(configuration: dict[str, Any]) -> None:
    assert recording_problems(configuration, PRIVACY_PROJECT) == []
    # The agent project's recording on failure is its own, not the configuration's.
    assert recording_problems(configuration, AGENT_PROJECT)
    assert not {name for name in RECORDINGS if name in (configuration.get("use") or {})}


def _privacy_use(configuration: dict[str, Any]) -> dict[str, Any]:
    (project,) = [entry for entry in configuration["projects"] if entry["name"] == PRIVACY_PROJECT]
    return project["use"]


@pytest.mark.parametrize(
    ("setting", "value"),
    [("trace", "retain-on-failure"), ("screenshot", "only-on-failure"), ("video", "on"), ("trace", {"mode": "on"})],
)
def test_a_project_that_turns_a_recording_on_is_refused(
    configuration: dict[str, Any], setting: str, value: object
) -> None:
    planted = copy.deepcopy(configuration)
    _privacy_use(planted)[setting] = value
    assert recording_problems(planted, PRIVACY_PROJECT) == [f"{setting} is {json.dumps(value)}"]


def test_a_recording_the_project_leaves_to_the_top_level_is_refused(configuration: dict[str, Any]) -> None:
    planted = copy.deepcopy(configuration)
    del _privacy_use(planted)["screenshot"]
    planted["use"] = {**planted.get("use", {}), "screenshot": "only-on-failure"}
    assert recording_problems(planted, PRIVACY_PROJECT) == ['screenshot is "only-on-failure"']
    # Left out everywhere is not the same as turned off.
    del planted["use"]["screenshot"]
    assert recording_problems(planted, PRIVACY_PROJECT) == ["screenshot is null"]


def test_a_missing_or_doubled_privacy_project_is_refused(configuration: dict[str, Any]) -> None:
    without = {**configuration, "projects": [p for p in configuration["projects"] if p["name"] != PRIVACY_PROJECT]}
    assert recording_problems(without, PRIVACY_PROJECT) == [
        f"the live configuration declares 0 projects named {PRIVACY_PROJECT}"
    ]
    doubled = {**configuration, "projects": [*configuration["projects"], *configuration["projects"]]}
    assert recording_problems(doubled, PRIVACY_PROJECT) == [
        f"the live configuration declares 2 projects named {PRIVACY_PROJECT}"
    ]


def test_each_run_runs_one_project() -> None:
    assert playwright_arguments(["-g", "x"], attach_only=False, ledger_privacy=False) == [
        "--project",
        AGENT_PROJECT,
        "-g",
        "x",
    ]
    assert playwright_arguments([], attach_only=True, ledger_privacy=False) == [
        "--project",
        AGENT_PROJECT,
        "tests/live/attach.live.ts",
    ]
    assert playwright_arguments(["--retries=0"], attach_only=False, ledger_privacy=True) == [
        "--project",
        PRIVACY_PROJECT,
        "--retries=0",
    ]


def test_the_privacy_run_is_told_what_to_scan_and_runs_without_debug_logging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEBUG", "pw:api")
    monkeypatch.setenv("PWDEBUG", "1")
    monkeypatch.setenv("CADRUMO_DEV_DESKTOP_LIVE_WRITTEN", "[]")
    root = tmp_path / "root"
    scope = PrivacyScope(tmp_path / "run", written_directories(root), 1_760_000_000.25)
    environment = playwright_environment(
        "http://tauri.localhost/index.html", "http://127.0.0.1:1", tmp_path, "es", scope
    )
    assert environment["CADRUMO_DEV_DESKTOP_LIVE_RUN_DIRECTORY"] == str(tmp_path / "run")
    assert json.loads(environment["CADRUMO_DEV_DESKTOP_LIVE_WRITTEN"]) == [str(root / "logs"), str(root / "agent")]
    assert float(environment["CADRUMO_DEV_DESKTOP_LIVE_STARTED_AT"]) == scope.started_at
    assert environment["PLAYWRIGHT_NO_COPY_PROMPT"] == "1"
    assert environment["CADRUMO_DEV_DESKTOP_LIVE_LANGUAGE"] == "es"
    assert not {"DEBUG", "PWDEBUG"} & set(environment)

    agent = playwright_environment("http://tauri.localhost/index.html", "http://127.0.0.1:1", tmp_path, "es")
    # The agent specs keep their own failure context and the person's debug settings.
    assert agent["DEBUG"] == "pw:api"
    assert not {
        "CADRUMO_DEV_DESKTOP_LIVE_RUN_DIRECTORY",
        "CADRUMO_DEV_DESKTOP_LIVE_WRITTEN",
        "CADRUMO_DEV_DESKTOP_LIVE_STARTED_AT",
        "PLAYWRIGHT_NO_COPY_PROMPT",
    } & set(agent)


def test_the_privacy_run_and_the_attachment_check_are_one_choice(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as refused:
        lane._main(["--attach-only", "--ledger-privacy"])
    assert refused.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err
