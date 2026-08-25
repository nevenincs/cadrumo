"""Contract tests for the explicit global TUI request."""

from __future__ import annotations

import json

import pytest

from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    "command",
    (
        ("config", "passphrase", "change"),
        ("app", "overview", "status"),
        ("app", "modelo", "work", "calculate", "missing-work-unit"),
    ),
)
def test_global_tui_request_refuses_unimplemented_facets_before_their_preconditions(
    command: tuple[str, ...],
) -> None:
    result = invoke_cached_cli(("--language", "en", "--format", "json", "--tui", *command))

    assert result.exit_code != 0
    document = json.loads(result.stderr)
    assert document["error"]["code"] == "TUI_NOT_IMPLEMENTED"
    assert document["error"]["category"] == "REFUSED"
    assert document["error"]["context"]["command"] == document["command"]
    assert document["error"]["message"]
    assert result.stdout == ""


def test_tui_is_global_only() -> None:
    root_help = invoke_cached_cli(("--language", "en", "--help"))
    local_help = invoke_cached_cli(("--language", "en", "config", "profile", "create", "--help"))

    assert root_help.exit_code == 0
    assert "--tui" in root_help.output
    assert local_help.exit_code == 0
    assert "--tui" not in local_help.output


def test_every_existing_cli_tui_route_is_enrolled() -> None:
    from .._command_spec import TuiCapability
    from .._command_specs import COMMAND_GRAPH

    specs = COMMAND_GRAPH.by_key()
    expected = {
        "config_login",
        "config_profile_status",
        "config_profile_descendiente",
        "config_auth_apoderado_configure",
        "config_profile_create",
        "config_profile_edit",
        "app_modelo_work_wizard",
        "app_modelo_work_amend_wizard",
    }
    available = {key for key, spec in specs.items() if spec.tui_capability is TuiCapability.AVAILABLE}
    assert available == expected


def test_available_tui_route_never_falls_back_on_a_consoleless_host() -> None:
    result = invoke_cached_cli(("--language", "en", "--format", "json", "--tui", "config", "profile", "status"))

    assert result.exit_code != 0
    document = json.loads(result.stderr)
    assert document["error"]["code"] == "REFUSED_FLOW_UNSUPPORTED_CONSOLE"
    assert document["error"]["category"] == "REFUSED"
    assert result.stdout == ""


@pytest.mark.parametrize("command", ((), ("app",), ("config",)))
def test_terminal_root_and_group_paths_do_not_ignore_tui(command: tuple[str, ...]) -> None:
    result = invoke_cached_cli(("--language", "en", "--format", "json", "--tui", *command))

    assert result.exit_code != 0
    assert json.loads(result.stderr)["error"]["code"] == "TUI_NOT_IMPLEMENTED"
