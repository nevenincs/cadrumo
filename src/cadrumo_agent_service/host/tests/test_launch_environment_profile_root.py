"""The agent and the tools it starts are told the folder of the one profile the agent runs inside."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.core.profile_root_environment import PROFILE_ROOT_VARIABLE, profile_root
from cadrumo.core.storage_environment import STORAGE_ROOT

from ..launch_environment import FORWARD_VARIABLE, GATEWAY_SLOTS, agent_launch_environment

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_A = UUID("4c2e8d3a-7f6b-4a5c-9d0e-9f8a7b6c5d4e")
_PROFILE_B = UUID("5d3f9e4b-8a7c-4b6d-8e1f-0a9b8c7d6e5f")


def _launch(tmp_path: Path, profile_id: UUID | None, received: dict[str, str] | None = None) -> dict[str, str]:
    return agent_launch_environment(
        storage_root=tmp_path / "storage",
        agent_root=tmp_path / "agent",
        relay=tmp_path / "cadrumo-mcp",
        aeat=None,
        python=None,
        received=received or {},
        profile_id=profile_id,
    )


def test_the_gateway_is_told_its_profiles_folder_and_forwards_it_to_its_tools(tmp_path: Path) -> None:
    environment = _launch(tmp_path, _PROFILE_A)

    root = Path(environment[STORAGE_ROOT.variable])
    assert environment[PROFILE_ROOT_VARIABLE] == str(profile_root(root, _PROFILE_A))
    assert environment[FORWARD_VARIABLE].split(",") == [STORAGE_ROOT.variable, PROFILE_ROOT_VARIABLE]
    assert PROFILE_ROOT_VARIABLE in GATEWAY_SLOTS


def test_an_agent_started_for_another_profile_is_told_that_profiles_folder_whatever_it_received(
    tmp_path: Path,
) -> None:
    received = {PROFILE_ROOT_VARIABLE: str(profile_root(tmp_path / "storage", _PROFILE_A))}

    environment = _launch(tmp_path, _PROFILE_B, received)

    root = Path(environment[STORAGE_ROOT.variable])
    assert environment[PROFILE_ROOT_VARIABLE] == str(profile_root(root, _PROFILE_B))


def test_a_launch_for_no_profile_names_and_forwards_no_folder(tmp_path: Path) -> None:
    received = {PROFILE_ROOT_VARIABLE: str(profile_root(tmp_path / "storage", _PROFILE_A))}

    environment = _launch(tmp_path, None, received)

    assert PROFILE_ROOT_VARIABLE not in environment
    assert environment[FORWARD_VARIABLE].split(",") == [STORAGE_ROOT.variable]
