"""``config provision`` leaves declare what they reach, and the component leaves need no profile session.

The component leaves run the native component engine, which reaches only
installation-wide components no profile holds: its quick check reads local
files only, its full check reaches the network, its setup also writes
component storage and its removal deletes from component storage without the
network. The local reader's leaves still submit operations in the signed-in
profile, so they declare installation storage and stay behind the session. How
each check answers offline is proved by the engine's own suites.
"""

from __future__ import annotations

import pytest

from ..command_specs import COMMAND_GRAPH
from ..profile_authentication_policy import command_is_profile_free

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_the_quick_status_reads_only_local_files() -> None:
    status = COMMAND_GRAPH.spec("config_provision_status")

    assert status.policy.capabilities == frozenset({"state-free"})
    assert status.policy.side_effects == frozenset({"none"})
    assert status.parameters == ()


@pytest.mark.parametrize("key", ["config_provision_probe", "config_provision_verify"])
def test_a_full_check_declares_the_network_it_reaches_and_writes_nothing(key: str) -> None:
    policy = COMMAND_GRAPH.spec(key).policy

    assert policy.capabilities == frozenset({"network"})
    assert policy.side_effects == frozenset({"network"})


@pytest.mark.parametrize("key", ["config_provision_setup", "config_provision_browser"])
def test_a_setup_declares_its_download_and_its_component_storage(key: str) -> None:
    policy = COMMAND_GRAPH.spec(key).policy

    assert policy.capabilities == frozenset({"components", "network"})
    assert policy.side_effects == frozenset({"network", "local-state"})


def test_a_removal_declares_the_component_storage_it_deletes_from_and_no_network() -> None:
    policy = COMMAND_GRAPH.spec("config_provision_remove").policy

    assert policy.capabilities == frozenset({"components"})
    assert policy.side_effects == frozenset({"local-state"})
    assert policy.destructive


@pytest.mark.parametrize("leaf", ["status", "probe", "verify", "setup", "browser", "report", "remove"])
def test_only_the_component_leaves_run_without_a_profile_session(leaf: str) -> None:
    profile_free = command_is_profile_free(COMMAND_GRAPH.spec(f"config_provision_{leaf}"))

    assert profile_free is (leaf in {"status", "probe", "verify", "setup", "browser", "remove"})


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
