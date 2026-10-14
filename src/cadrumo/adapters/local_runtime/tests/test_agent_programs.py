"""The runtime starts the package's agent image and mounts the package's relay, both as its own environment names them."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cadrumo.application.agent_host.launcher_protocol import AgentLauncherRefusal

from ..agent_programs import (
    PACKAGE_AGENT_VARIABLE,
    PACKAGE_RELAY_VARIABLE,
    AgentProgramRefusalError,
    agent_image,
    hosted_relay,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _program(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def test_the_package_agent_image_starts_the_gateway_invocation_in_the_agents_root(tmp_path: Path) -> None:
    image = _program(tmp_path / "package" / "bin" / "cadrumo-agent.exe")
    agent_root = tmp_path / "agent"
    started = agent_image(None, agent_root=agent_root, received={PACKAGE_AGENT_VARIABLE: str(image)})
    assert started.executable == image
    assert started.arguments == ("-m", "cadrumo_agent.cli.main", "serve")
    assert started.directory == agent_root


def test_outside_a_package_there_is_no_bundled_agent(tmp_path: Path) -> None:
    with pytest.raises(AgentProgramRefusalError) as refused:
        agent_image(None, agent_root=tmp_path, received={})
    assert refused.value.code is AgentLauncherRefusal.SERVICE_ABSENT


@pytest.mark.parametrize("declared", ["bin/cadrumo-agent.exe", "{root}/missing/cadrumo-agent.exe", "{root}"])
def test_an_agent_image_the_package_names_but_cannot_start_is_a_service_failure(tmp_path: Path, declared: str) -> None:
    with pytest.raises(AgentProgramRefusalError) as refused:
        agent_image(
            None, agent_root=tmp_path, received={PACKAGE_AGENT_VARIABLE: declared.format(root=tmp_path.as_posix())}
        )
    assert refused.value.code is AgentLauncherRefusal.SERVICE_FAILED


def test_a_named_source_tree_runs_from_its_own_environment_with_the_same_invocation(tmp_path: Path) -> None:
    source = tmp_path / "agent-source"
    interpreter = _program(
        source / ".venv" / "Scripts" / "python.exe" if sys.platform == "win32" else source / ".venv" / "bin" / "python"
    )
    image = _program(tmp_path / "package" / "bin" / "cadrumo-agent.exe")
    started = agent_image(str(source), agent_root=tmp_path / "agent", received={PACKAGE_AGENT_VARIABLE: str(image)})
    assert (started.executable, started.arguments, started.directory) == (
        interpreter,
        ("-m", "cadrumo_agent.cli.main", "serve"),
        source,
    )


def test_a_source_tree_without_its_environment_is_absent(tmp_path: Path) -> None:
    (tmp_path / "agent-source").mkdir()
    for source in (str(tmp_path / "agent-source"), "agent-source"):
        with pytest.raises(AgentProgramRefusalError) as refused:
            agent_image(source, agent_root=tmp_path, received={})
        assert refused.value.code is AgentLauncherRefusal.SERVICE_ABSENT


def test_the_package_relay_is_the_one_the_runtime_environment_names(tmp_path: Path) -> None:
    relay = _program(tmp_path / "package" / "bin" / "cadrumo-mcp.exe")
    checkout = _program(tmp_path / "checkout" / ("cadrumo-mcp.exe" if sys.platform == "win32" else "cadrumo-mcp"))
    named = hosted_relay(received={PACKAGE_RELAY_VARIABLE: str(relay)}, interpreter=checkout.parent / "python")
    assert named == relay


def test_a_checkout_mounts_the_relay_beside_its_interpreter(tmp_path: Path) -> None:
    relay = _program(tmp_path / "checkout" / ("cadrumo-mcp.exe" if sys.platform == "win32" else "cadrumo-mcp"))
    assert hosted_relay(received={}, interpreter=relay.parent / "python") == relay


@pytest.mark.parametrize("declared", ["bin/cadrumo-mcp.exe", "{root}/missing/cadrumo-mcp.exe"])
def test_a_relay_that_cannot_be_started_is_a_service_failure(tmp_path: Path, declared: str) -> None:
    with pytest.raises(AgentProgramRefusalError) as refused:
        hosted_relay(received={PACKAGE_RELAY_VARIABLE: declared.format(root=tmp_path.as_posix())})
    assert refused.value.code is AgentLauncherRefusal.SERVICE_FAILED
