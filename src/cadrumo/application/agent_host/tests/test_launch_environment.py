"""The gateway's environment carries no credential the runtime happens to hold, and of the agent's settings only its slots."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ....core.storage_environment import STORAGE_ROOT, normalize_storage_path
from ..launch_environment import (
    AGENT_SLOTS,
    GATEWAY_PORT_VARIABLE,
    GATEWAY_SLOTS,
    HOSTED_RELAY_VARIABLE,
    HOSTED_ROOT_VARIABLE,
    WORKER_PORT_VARIABLE,
    agent_launch_environment,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RECEIVED = {
    "SystemRoot": "C:\\Windows",
    "PATH": "C:\\Windows\\System32",
    "USERPROFILE": "C:\\Users\\person",
    "ANTHROPIC_API_KEY": "sk-ant-test-NOT-A-REAL-KEY",
    "OPENAI_API_KEY": "sk-test-NOT-A-REAL-KEY",
    "AWS_SECRET_ACCESS_KEY": "aws-test-NOT-A-REAL-KEY",
    "CADRUMO_LLM_ANTHROPIC_API_KEY": "sk-ant-test-NOT-A-REAL-KEY",
    "CADRUMO_AGENT_ANTHROPIC_API_KEY": "sk-ant-test-NOT-A-REAL-KEY",
    "CADRUMO_AGENT_CLAUDE_API_KEY": "sk-ant-test-NOT-A-REAL-KEY",
    "CADRUMO_AGENT_GATEWAY_TOKEN": "gateway-test-NOT-A-REAL-TOKEN",
    "GITHUB_TOKEN": "ghp-test-NOT-A-REAL-TOKEN",
    "PYTHONPATH": "C:\\elsewhere",
}

# The hosting contract retired these program paths; the agent refuses a start that carries either.
_RETIRED_PROGRAM_VARIABLES = ("CADRUMO_AGENT_HOSTED_CLI_EXECUTABLE", "CADRUMO_AGENT_HOSTED_PYTHON_EXECUTABLE")


@pytest.mark.skipif(sys.platform != "win32", reason="the Windows allow-list folds names on the host it describes")
def test_only_allow_listed_system_values_the_pinned_root_and_the_hosted_root_reach_the_agent(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    agent_root = storage_root / "agent" / "opaque"
    environment = agent_launch_environment(
        storage_root=storage_root,
        agent_root=agent_root,
        relay=tmp_path / "cadrumo-mcp.exe",
        received=_RECEIVED,
        sys_platform="win32",
    )
    assert environment[HOSTED_ROOT_VARIABLE] == str(agent_root)
    assert environment["SYSTEMROOT"] == "C:\\Windows"
    assert environment["USERPROFILE"] == "C:\\Users\\person"
    assert "NOT-A-REAL" not in repr(environment)
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN", "PYTHONPATH"):
        assert name not in environment
    assert not any(name.startswith("CADRUMO_LLM_") or name == "CADRUMO_AGENT_GATEWAY_TOKEN" for name in environment)


def test_posix_hosts_keep_only_their_own_allow_list(tmp_path: Path) -> None:
    received = {"HOME": "/home/person", "PATH": "/usr/bin", "ANTHROPIC_API_KEY": "sk-ant-test-NOT-A-REAL-KEY"}
    environment = agent_launch_environment(
        storage_root=tmp_path / "storage",
        agent_root=tmp_path / "storage" / "agent" / "opaque",
        relay=tmp_path / "cadrumo-mcp",
        received=received,
        sys_platform="linux",
    )
    assert environment["HOME"] == "/home/person"
    assert "ANTHROPIC_API_KEY" not in environment
    assert "NOT-A-REAL" not in repr(environment)


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_the_runtime_fills_exactly_the_gateway_slots_and_never_a_retired_program_path(
    tmp_path: Path, platform: str
) -> None:
    agent_root = tmp_path / "storage" / "agent" / "opaque"
    relay = tmp_path / "bin" / "cadrumo-mcp"
    # Every agent setting the runtime itself received, the retired program paths included, stays behind.
    received = {
        **_RECEIVED,
        "HOME": "/home/person",
        **dict.fromkeys(_RETIRED_PROGRAM_VARIABLES, str(tmp_path / "bin" / "aeat")),
        HOSTED_ROOT_VARIABLE: str(tmp_path / "elsewhere"),
        GATEWAY_PORT_VARIABLE: "8080",
        "CADRUMO_AGENT_DEVELOPMENT_TOOL_SERVER": "true",
        "CADRUMO_AGENT_ENV_FILE": str(tmp_path / "agent.env"),
        STORAGE_ROOT.variable: str(tmp_path / "the-developers-own-root"),
    }
    environment = agent_launch_environment(
        storage_root=tmp_path / "storage", agent_root=agent_root, relay=relay, received=received, sys_platform=platform
    )
    assert {name for name in environment if name.startswith("CADRUMO_AGENT_")} == AGENT_SLOTS
    assert {HOSTED_ROOT_VARIABLE, GATEWAY_PORT_VARIABLE, WORKER_PORT_VARIABLE, HOSTED_RELAY_VARIABLE} == AGENT_SLOTS
    assert AGENT_SLOTS | {"CADRUMO_LOCAL_STORAGE_ROOT"} == GATEWAY_SLOTS
    assert set(environment) >= GATEWAY_SLOTS
    assert not set(_RETIRED_PROGRAM_VARIABLES) & set(environment)
    assert not set(_RETIRED_PROGRAM_VARIABLES) & GATEWAY_SLOTS
    # The gateway forwards the runtime's own root to its relay, never the root the runtime itself received.
    assert environment["CADRUMO_LOCAL_STORAGE_ROOT"] == str(normalize_storage_path(tmp_path / "storage"))
    assert environment[HOSTED_ROOT_VARIABLE] == str(agent_root)
    assert environment[GATEWAY_PORT_VARIABLE] == environment[WORKER_PORT_VARIABLE] == "0"
    assert environment[HOSTED_RELAY_VARIABLE] == str(relay)


@pytest.mark.parametrize(("platform", "separator"), [("win32", ";"), ("linux", ":")])
def test_the_search_path_reaches_the_agent_as_received(tmp_path: Path, platform: str, separator: str) -> None:
    # In a package the agent image's host composes the search path; the runtime no longer filters it.
    programs = tmp_path / "bin"
    programs.mkdir()
    for program in ("aeat.exe", "python.exe", "cadrumo-mcp.exe", "cmd.exe"):
        (programs / program).write_bytes(b"")
    search_path = separator.join((str(programs), str(tmp_path / "tools")))
    environment = agent_launch_environment(
        storage_root=tmp_path / "storage",
        agent_root=tmp_path / "storage" / "agent" / "opaque",
        relay=programs / "cadrumo-mcp.exe",
        received={"PATH": search_path},
        sys_platform=platform,
    )
    assert environment["PATH"] == search_path
