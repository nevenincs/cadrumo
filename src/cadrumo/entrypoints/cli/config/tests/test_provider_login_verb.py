"""``aeat config provider-login`` hands the terminal to the bundled agent's own provider sign-in."""

from __future__ import annotations

import json
import sys

import pytest

from cadrumo_client.commands import profile_selection
from cadrumo_client.commands.profile_selection import LoginTarget

from ...tests.cli_runner import invoke_cached_cli, semantic_cli_output
from .. import provider_login_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = "12345678-1234-5678-1234-567812345678"


def test_the_helper_command_names_the_service_door_the_profile_the_provider_and_the_flow() -> None:
    assert provider_login_cli.helper_command(_PROFILE, "codex", device=True) == [
        sys.executable,
        "-m",
        "cadrumo_agent_service.adapters.provider_login",
        "--profile-id",
        _PROFILE,
        "--provider",
        "codex",
        "--device",
    ]
    assert "--device" not in provider_login_cli.helper_command(_PROFILE, "claude", device=False)


def test_the_helper_runs_on_the_callers_terminal_and_its_exit_status_is_returned() -> None:
    status = provider_login_cli.run_helper([sys.executable, "-c", "import sys; sys.exit(7)"])
    assert status == 7


def test_the_helper_output_reaches_the_inherited_terminal_and_is_not_captured(
    capfd: pytest.CaptureFixture[str],
) -> None:
    status = provider_login_cli.run_helper([sys.executable, "-c", "print('device-code-line')"])
    assert status == 0
    assert "device-code-line" in capfd.readouterr().out


def test_an_unsupported_provider_is_refused_before_any_profile_is_resolved(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(*_arguments: object) -> object:
        raise AssertionError("no profile lookup for a refused provider")

    monkeypatch.setattr(profile_selection, "command_profile_id", unexpected)
    result = invoke_cached_cli(["config", "provider-login", "--provider", "gemini"])
    assert result.exit_code != 0
    assert "gemini" in semantic_cli_output(result)


def test_the_device_flow_is_refused_for_a_provider_without_one() -> None:
    result = invoke_cached_cli(["config", "provider-login", "--provider", "claude", "--device"])
    assert result.exit_code != 0
    assert "--device" in semantic_cli_output(result)


def test_the_selected_profile_and_the_provider_reach_the_helper_and_its_status_ends_the_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[list[str]] = []

    def run(command: list[str]) -> int:
        started.append(command)
        return 5

    monkeypatch.setattr(profile_selection, "command_profile_id", lambda: _PROFILE)
    monkeypatch.setattr(provider_login_cli, "run_helper", run)
    result = invoke_cached_cli(["config", "provider-login", "--provider", "codex", "--device"])
    assert result.exit_code == 5
    assert started == [provider_login_cli.helper_command(_PROFILE, "codex", device=True)]


def test_a_named_profile_is_resolved_by_the_runtime_and_a_signed_in_provider_reports_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[list[str]] = []

    def run(command: list[str]) -> int:
        started.append(command)
        return 0

    monkeypatch.setattr(
        profile_selection, "require_runtime_login_target", lambda name: LoginTarget(_PROFILE, f"label {name}")
    )
    monkeypatch.setattr(provider_login_cli, "run_helper", run)
    result = invoke_cached_cli(["config", "provider-login", "--provider", "antigravity", "--profile", "Mi perfil"])
    assert result.exit_code == 0, result.output
    assert started == [provider_login_cli.helper_command(_PROFILE, "antigravity", device=False)]
    assert "antigravity" in semantic_cli_output(result)


def test_without_a_selected_profile_the_command_refuses_and_starts_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[list[str]] = []
    monkeypatch.setattr(profile_selection, "command_profile_id", lambda: None)
    monkeypatch.setattr(provider_login_cli, "run_helper", lambda command: started.append(command) or 0)
    result = invoke_cached_cli(["config", "provider-login", "--provider", "codex"])
    assert result.exit_code != 0
    assert started == []


def test_json_output_is_refused_because_the_command_is_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[list[str]] = []
    monkeypatch.setattr(provider_login_cli, "run_helper", lambda command: started.append(command) or 0)
    result = invoke_cached_cli(["--format", "json", "config", "provider-login", "--provider", "codex"])
    assert result.exit_code != 0
    error = json.loads(result.output)["error"]
    assert error["category"] == "REFUSED"
    assert "provider-login" in error["message"]
    assert started == []
