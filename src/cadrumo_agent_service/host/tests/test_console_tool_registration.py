"""The ``console_environment`` read registers the packaged ``cadrumo-mcp`` for the console's provider programs.

A console runs Claude Code in the profile's agent workspace and Codex with the
profile's ``CODEX_HOME``. Each finds its tool servers in its own file: Claude in
the workspace's ``.mcp.json``, enabled by ``.claude/settings.local.json``, and
Codex in ``config.toml`` in its home. The read writes the ``cadrumo`` entry of
each, naming the launcher the service's environment fixes and its arguments,
and keeps every other entry a person or the provider wrote. The provider homes
stand in for the installed agent's derivation, which the agent checkout test
exercises; the read itself runs through the service's administration entry on
a synthetic profile under a temporary root.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.core.profile_root_environment import PROFILE_ROOT_VARIABLE, profile_root
from cadrumo.core.storage_environment import STORAGE_ROOT
from cadrumo_client.contracts.service_access import ServiceLease
from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import service_console_environment as console_module
from ...adapters.agent_programs import PACKAGE_RELAY_VARIABLE, profile_agent_root, profile_agent_workspace
from ...adapters.console_tool_registration import TOOL_SERVER_NAME
from ...providers.domain.record import LocalEngine
from ...service import AgentService
from ..launch_environment import TOOL_SERVER_ARGUMENTS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SYNTHETIC_CREDENTIAL = "sk-synthetic-console-credential-0123456789abcdef"
"""A credential-like string a provider home holds; no registration may carry it."""


def _lease(profile_id: UUID) -> ServiceLease:
    return ServiceLease(
        lease_id=uuid4(),
        session_id=UUID(int=2),
        profile_id=profile_id,
        parent_session_id=UUID(int=4),
        descriptor_digest="2" * 64,
        service_id="cadrumo-agent-service",
        runtime_boot_id=UUID(int=5),
        connection_id=UUID(int=6),
    )


def _service(root: Path, profile_id: UUID) -> AgentService:
    return AgentService(
        local_engine_default=LocalEngine.LLAMACPP,
        client=cast(
            InstalledServiceClient,
            SimpleNamespace(lease=_lease(profile_id), connection=SimpleNamespace(close=lambda: None)),
        ),
        storage_root=root,
        gateway_bearer=bytearray(b"synthetic-gateway-bearer"),
        emit=lambda _event: None,
    )


def _homes(agent_root: Path) -> dict[str, str]:
    """Homes beneath the agent root, each holding a credential file as a provider sign-in leaves one."""
    homes = {"CLAUDE_CONFIG_DIR": agent_root / "providers" / "claude", "CODEX_HOME": agent_root / "providers" / "codex"}
    for home in homes.values():
        home.mkdir(parents=True, exist_ok=True)
        (home / "credentials.json").write_text(json.dumps({"token": _SYNTHETIC_CREDENTIAL}), encoding="utf-8")
    return {name: str(home) for name, home in homes.items()}


@pytest.fixture
def storage(tmp_path: Path) -> Path:
    root = tmp_path / "storage"
    root.mkdir()
    return root


@pytest.fixture
def launcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The packaged ``cadrumo-mcp`` the service image's launch profile fixes."""
    program = tmp_path / "package" / "bin" / "cadrumo-mcp.exe"
    program.parent.mkdir(parents=True)
    program.write_bytes(b"synthetic launcher")
    monkeypatch.setenv(PACKAGE_RELAY_VARIABLE, str(program))
    monkeypatch.setattr(console_module, "console_provider_homes", _homes)
    return program


def _expected_server(storage: Path, profile: UUID, launcher: Path) -> dict[str, object]:
    return {
        "command": str(launcher),
        "args": list(TOOL_SERVER_ARGUMENTS),
        "env": {STORAGE_ROOT.variable: str(storage), PROFILE_ROOT_VARIABLE: str(profile_root(storage, profile))},
    }


def _registration_files(storage: Path, profile: UUID) -> tuple[Path, Path, Path]:
    agent_root = profile_agent_root(storage, profile)
    workspace = profile_agent_workspace(agent_root)
    codex_home = Path(_homes(agent_root)["CODEX_HOME"])
    return workspace / ".mcp.json", workspace / ".claude" / "settings.local.json", codex_home / "config.toml"


def test_the_read_registers_the_packaged_tool_server_for_claude_and_codex(storage: Path, launcher: Path) -> None:
    profile = uuid4()

    answer = _service(storage, profile).admin("console_environment")

    assert answer["kind"] == "console_environment"
    mcp_json, settings, config = _registration_files(storage, profile)
    assert Path(answer["working_directory"]) == mcp_json.parent
    assert Path(answer["environment"]["CODEX_HOME"]) == config.parent
    expected = _expected_server(storage, profile, launcher)
    claude = json.loads(mcp_json.read_text(encoding="utf-8"))["mcpServers"][TOOL_SERVER_NAME]
    assert claude == {"type": "stdio", **expected}
    assert TOOL_SERVER_NAME in json.loads(settings.read_text(encoding="utf-8"))["enabledMcpjsonServers"]
    codex = tomllib.loads(config.read_text(encoding="utf-8"))["mcp_servers"][TOOL_SERVER_NAME]
    assert codex == expected
    for written in (mcp_json, settings, config):
        assert _SYNTHETIC_CREDENTIAL not in written.read_text(encoding="utf-8")
    assert _SYNTHETIC_CREDENTIAL not in json.dumps(answer)


def test_the_registration_keeps_other_entries_replaces_its_own_and_is_idempotent(storage: Path, launcher: Path) -> None:
    profile = uuid4()
    mcp_json, settings, config = _registration_files(storage, profile)
    settings.parent.mkdir(parents=True, exist_ok=True)
    config.parent.mkdir(parents=True, exist_ok=True)
    mcp_json.write_text(
        json.dumps({"mcpServers": {"other": {"command": "other.exe"}, TOOL_SERVER_NAME: {"command": "stale.exe"}}}),
        encoding="utf-8",
    )
    settings.write_text(json.dumps({"enabledMcpjsonServers": ["other"], "model": "kept"}), encoding="utf-8")
    config.write_text(
        'model = "kept"\n\n'
        f'[mcp_servers.{TOOL_SERVER_NAME}]\ncommand = "stale.exe"\n\n'
        f'[mcp_servers.{TOOL_SERVER_NAME}.env]\nSTALE = "1"\n\n'
        '[mcp_servers.other]\ncommand = "other.exe"\n\n'
        '[projects."C:\\\\work"]\ntrust_level = "trusted"\n',
        encoding="utf-8",
    )
    service = _service(storage, profile)

    service.admin("console_environment")
    first = [path.read_bytes() for path in (mcp_json, settings, config)]
    service.admin("console_environment")

    assert [path.read_bytes() for path in (mcp_json, settings, config)] == first
    expected = _expected_server(storage, profile, launcher)
    claude = json.loads(mcp_json.read_text(encoding="utf-8"))
    assert claude["mcpServers"] == {"other": {"command": "other.exe"}, TOOL_SERVER_NAME: {"type": "stdio", **expected}}
    local = json.loads(settings.read_text(encoding="utf-8"))
    assert local == {"enabledMcpjsonServers": ["other", TOOL_SERVER_NAME], "model": "kept"}
    codex = tomllib.loads(config.read_text(encoding="utf-8"))
    assert codex["model"] == "kept"
    assert codex["projects"] == {"C:\\work": {"trust_level": "trusted"}}
    assert codex["mcp_servers"] == {"other": {"command": "other.exe"}, TOOL_SERVER_NAME: expected}


def test_a_file_that_is_not_its_providers_form_is_kept_and_the_read_still_answers(
    storage: Path, launcher: Path
) -> None:
    profile = uuid4()
    mcp_json, settings, config = _registration_files(storage, profile)
    settings.parent.mkdir(parents=True, exist_ok=True)
    config.parent.mkdir(parents=True, exist_ok=True)
    broken = {mcp_json: "{not json", settings: "[]", config: "model = \n"}
    for path, text in broken.items():
        path.write_text(text, encoding="utf-8")

    answer = _service(storage, profile).admin("console_environment")

    assert answer["kind"] == "console_environment"
    for path, text in broken.items():
        assert path.read_text(encoding="utf-8") == text
    assert launcher.is_file()


def test_a_launcher_the_package_does_not_hold_refuses_the_read(
    storage: Path, launcher: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PACKAGE_RELAY_VARIABLE, str(launcher.with_name("absent.exe")))

    answer = _service(storage, uuid4()).admin("console_environment")

    assert answer == {"kind": "refused", "code": "console_environment_unavailable"}
