"""The agent's environment carries no credential the launcher happens to hold."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ..launch_environment import HOSTED_ROOT_VARIABLE, agent_launch_environment

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
    "CADRUMO_AGENT_GATEWAY_TOKEN": "gateway-test-NOT-A-REAL-TOKEN",
    "GITHUB_TOKEN": "ghp-test-NOT-A-REAL-TOKEN",
    "PYTHONPATH": "C:\\elsewhere",
}


@pytest.mark.skipif(sys.platform != "win32", reason="the Windows allow-list folds names on the host it describes")
def test_only_allow_listed_system_values_the_pinned_root_and_the_hosted_root_reach_the_agent(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    agent_root = storage_root / "agent" / "opaque"
    environment = agent_launch_environment(
        storage_root=storage_root, agent_root=agent_root, received=_RECEIVED, sys_platform="win32"
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
        received=received,
        sys_platform="linux",
    )
    assert environment["HOME"] == "/home/person"
    assert "ANTHROPIC_API_KEY" not in environment
    assert "NOT-A-REAL" not in repr(environment)
