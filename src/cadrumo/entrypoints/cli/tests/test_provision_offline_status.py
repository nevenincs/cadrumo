"""Provision commands declare their effects and require a signed-in profile."""

from __future__ import annotations

import pytest

from cadrumo.tests.english_locale_fixture import english_locale_fixture

from ..command_specs import COMMAND_GRAPH
from ..profile_authentication_policy import command_is_profile_free
from .cli_runner import invoke_cached_cli, semantic_cli_text
from .sessionless_root_fixtures import _sessionless_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]
__all__ = ["_sessionless_root", "english_locale_fixture"]


def test_the_quick_status_reads_only_local_files() -> None:
    status = COMMAND_GRAPH.spec("config_provision_status")

    assert status.policy.capabilities == frozenset({"profile-custody"})
    assert status.policy.side_effects == frozenset({"none"})
    assert status.parameters == ()


@pytest.mark.parametrize("key", ["config_provision_probe", "config_provision_verify"])
def test_a_full_check_declares_the_network_it_reaches_and_writes_nothing(key: str) -> None:
    policy = COMMAND_GRAPH.spec(key).policy

    assert policy.capabilities == frozenset({"network", "profile-custody"})
    assert policy.side_effects == frozenset({"network"})


@pytest.mark.parametrize("key", ["config_provision_setup", "config_provision_browser"])
def test_a_setup_declares_its_download_and_its_component_storage(key: str) -> None:
    policy = COMMAND_GRAPH.spec(key).policy

    assert policy.capabilities == frozenset({"components", "network", "profile-custody"})
    assert policy.side_effects == frozenset({"network", "local-state"})


def test_a_removal_declares_the_component_storage_it_deletes_from_and_no_network() -> None:
    policy = COMMAND_GRAPH.spec("config_provision_remove").policy

    assert policy.capabilities == frozenset({"components", "profile-custody"})
    assert policy.side_effects == frozenset({"local-state"})
    assert policy.destructive


@pytest.mark.parametrize("leaf", ["status", "probe", "verify", "setup", "browser", "report", "remove", "review"])
def test_component_leaves_require_a_profile_session(leaf: str) -> None:
    profile_free = command_is_profile_free(COMMAND_GRAPH.spec(f"config_provision_{leaf}"))

    assert profile_free is False


@pytest.mark.parametrize(
    "arguments",
    [
        ["status"],
        ["probe"],
        ["verify"],
        ["setup"],
        ["browser"],
        ["remove", "browser", "--yes"],
        ["review", "a" * 64, "--yes"],
    ],
)
def test_provision_verbs_say_sign_in_first_without_a_profile(_sessionless_root, arguments: list[str]) -> None:
    result = invoke_cached_cli(["config", "provision", *arguments])
    assert result.exit_code != 0
    assert "sign in" in semantic_cli_text(result.output).lower()


def test_the_local_ai_server_has_no_start_leaf_because_the_manager_runs_it() -> None:
    leaves = {node.path[-1] for node in COMMAND_GRAPH.nodes() if node.path[1:3] == ("config", "provision")}

    assert "start" not in leaves
    assert {"status", "setup", "verify", "remove", "report"} <= leaves
    assert "load" not in leaves, "the local reader loads no model directly"


def test_the_command_line_has_no_leaf_that_pulls_a_model_or_sets_up_the_local_ai() -> None:
    nodes = [node for node in COMMAND_GRAPH.nodes() if node.path[1:3] == ("config", "provision") and len(node.path) > 3]

    assert "pull" not in {node.path[-1] for node in nodes}
    assert all("model" not in [parameter.name for parameter in node.spec.parameters] for node in nodes)
    assert [parameter.name for parameter in COMMAND_GRAPH.spec("config_provision_browser").parameters] == ["yes"]
    assert [parameter.name for parameter in COMMAND_GRAPH.spec("config_provision_setup").parameters] == ["yes"]
