"""``config provision`` leaves declare what they reach, and the component leaves need no profile session.

The component leaves run the native component engine, which reaches only
installation-wide components no profile holds: its quick check reads local
files only, its full check reaches the network, and its setup also writes
component storage. The local reader's leaves still submit operations in the
signed-in profile, so they declare installation storage and stay behind the
session. How each check answers offline is proved by the engine's own suites.
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


@pytest.mark.parametrize("key", ["config_provision_setup", "config_provision_browser", "config_provision_pull"])
def test_a_setup_declares_its_download_and_its_component_storage(key: str) -> None:
    policy = COMMAND_GRAPH.spec(key).policy

    assert policy.capabilities == frozenset({"network"})
    assert policy.side_effects == frozenset({"network", "local-state"})


@pytest.mark.parametrize(
    "leaf", ["status", "probe", "verify", "setup", "browser", "pull", "report", "start", "load", "remove"]
)
def test_only_the_component_leaves_run_without_a_profile_session(leaf: str) -> None:
    profile_free = command_is_profile_free(COMMAND_GRAPH.spec(f"config_provision_{leaf}"))

    assert profile_free is (leaf in {"status", "probe", "verify", "setup", "browser", "pull"})


def test_the_local_ai_setup_takes_no_model_of_the_operators_choosing() -> None:
    assert [parameter.name for parameter in COMMAND_GRAPH.spec("config_provision_pull").parameters] == ["yes"]
