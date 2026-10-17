"""The gateway's environment carries no credential the runtime happens to hold, and of the agent's names only its slots and what Cadrumo advertises."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from cadrumo.core.storage_environment import STORAGE_ROOT, normalize_storage_path
from cadrumo_harness.mcp.surfaces import DEFAULT_MCP_SURFACE

from ..launch_environment import (
    ADVERTISED_VARIABLES,
    AGENT_LOG_LEVEL_VARIABLE,
    AGENT_SLOTS,
    DIAGNOSTIC_VARIABLES,
    EXTERNAL_BIN_DIRECTORIES_VARIABLE,
    FORWARD_VARIABLE,
    GATEWAY_PORT_VARIABLE,
    GATEWAY_SLOTS,
    HOSTED_ROOT_VARIABLE,
    PROGRAM_AEAT_VARIABLE,
    PROGRAM_PYTHON_VARIABLE,
    TOOL_SERVER_ARGUMENTS_VARIABLE,
    TOOL_SERVER_VARIABLE,
    WORKER_PORT_VARIABLE,
    agent_binary_directories,
    agent_launch_environment,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RETIRED_INSTRUCTION_VARIABLES = frozenset({"CADRUMO_AGENT_SKILLS_DIR", "CADRUMO_AGENT_RULES_DIR"})


def _write_package_manifest(root: Path, *, packages: str, executable: str) -> None:
    manifest_path = root / "data" / "package-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({"layout": {"paths": {"packages": packages, "executable": executable}}}),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("platform", "name"), [("win32", "cadrumo_external_bin_dirs"), ("linux", "CADRUMO_EXTERNAL_BIN_DIRS")]
)
def test_declared_provider_binary_directories_reach_the_native_agent_host(
    tmp_path: Path, platform: str, name: str
) -> None:
    environment = agent_launch_environment(
        storage_root=tmp_path / "storage",
        agent_root=tmp_path / "agent",
        relay=tmp_path / "cadrumo-mcp",
        aeat=None,
        python=None,
        received={name: str(tmp_path), "CODEX_HOME": "private-account", "API_KEY": "private-key"},
        sys_platform=platform,
    )
    assert environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE] == str(tmp_path)
    assert "CODEX_HOME" not in environment
    assert "API_KEY" not in environment


@pytest.mark.parametrize(
    ("platform", "python_name", "packages_relative", "node_relative", "separator"),
    [
        ("win32", "python.exe", "cadrumo/site-packages", ("node", "node.exe"), ";"),
        ("linux", "python", "lib/cadrumo/site-packages", ("node", "bin", "node"), ":"),
    ],
)
def test_packaged_node_bin_precedes_declared_provider_binary_directories(
    tmp_path: Path,
    platform: str,
    python_name: str,
    packages_relative: str,
    node_relative: tuple[str, ...],
    separator: str,
) -> None:
    python = tmp_path / python_name
    python.touch()
    packages = python.parent.joinpath(*packages_relative.split("/"))
    packages.mkdir(parents=True)
    _write_package_manifest(python.parent, packages=packages_relative, executable=python_name)
    node = packages.parent.joinpath(*node_relative)
    node.parent.mkdir(parents=True)
    node.touch()
    provider_bins = separator.join((str(tmp_path / "codex"), str(tmp_path / "claude")))

    environment = agent_launch_environment(
        storage_root=tmp_path / "storage",
        agent_root=tmp_path / "agent",
        relay=tmp_path / "cadrumo-mcp",
        aeat=None,
        python=python,
        received={EXTERNAL_BIN_DIRECTORIES_VARIABLE: provider_bins},
        sys_platform=platform,
    )

    expected_directories = separator.join((str(node.parent), str(tmp_path / "codex"), str(tmp_path / "claude")))
    assert (
        agent_binary_directories(
            python=python,
            received={EXTERNAL_BIN_DIRECTORIES_VARIABLE: provider_bins},
            sys_platform=platform,
        )
        == expected_directories
    )
    assert environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE] == expected_directories


@pytest.mark.parametrize(
    ("platform", "python_name", "packages_relative", "node_relative", "separator"),
    [
        ("win32", "python.exe", "cadrumo/site-packages", ("node", "node.exe"), ";"),
        ("linux", "python", "lib/cadrumo/site-packages", ("node", "bin", "node"), ":"),
    ],
)
def test_missing_packaged_node_keeps_declared_provider_directories_without_phantom_entries(
    tmp_path: Path,
    platform: str,
    python_name: str,
    packages_relative: str,
    node_relative: tuple[str, ...],
    separator: str,
) -> None:
    python = tmp_path / python_name
    python.touch()
    packages = python.parent.joinpath(*packages_relative.split("/"))
    packages.mkdir(parents=True)
    _write_package_manifest(python.parent, packages=packages_relative, executable=python_name)
    provider_bins = separator.join((str(tmp_path / "codex"), str(tmp_path / "claude")))

    environment = agent_launch_environment(
        storage_root=tmp_path / "storage",
        agent_root=tmp_path / "agent",
        relay=tmp_path / "cadrumo-mcp",
        aeat=None,
        python=python,
        received={EXTERNAL_BIN_DIRECTORIES_VARIABLE: provider_bins},
        sys_platform=platform,
    )

    assert environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE] == provider_bins
    assert str(packages.parent.joinpath(*node_relative[:-1])) not in environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE]


@pytest.mark.parametrize(
    ("platform", "python_name", "packages_relative", "node_relative", "separator"),
    [
        ("win32", "python.exe", "cadrumo/site-packages", ("node", "node.exe"), ";"),
        ("linux", "python", "lib/cadrumo/site-packages", ("node", "bin", "node"), ":"),
    ],
)
@pytest.mark.parametrize("manifest_state", ["missing", "malformed"])
def test_missing_or_malformed_package_manifest_never_injects_node_directory(
    tmp_path: Path,
    platform: str,
    python_name: str,
    packages_relative: str,
    node_relative: tuple[str, ...],
    separator: str,
    manifest_state: str,
) -> None:
    python = tmp_path / python_name
    python.touch()
    packages = python.parent.joinpath(*packages_relative.split("/"))
    packages.mkdir(parents=True)
    node = packages.parent.joinpath(*node_relative)
    node.parent.mkdir(parents=True)
    node.touch()
    manifest_path = python.parent / "data" / "package-manifest.json"
    if manifest_state == "malformed":
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text("{", encoding="utf-8")
    provider_bins = separator.join((str(tmp_path / "codex"), str(tmp_path / "claude")))

    environment = agent_launch_environment(
        storage_root=tmp_path / "storage",
        agent_root=tmp_path / "agent",
        relay=tmp_path / "cadrumo-mcp",
        aeat=None,
        python=python,
        received={EXTERNAL_BIN_DIRECTORIES_VARIABLE: provider_bins},
        sys_platform=platform,
    )

    assert environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE] == provider_bins


@pytest.mark.parametrize(
    ("platform", "python_name", "separator"),
    [("win32", "python.exe", ";"), ("linux", "python", ":")],
)
def test_manifest_package_path_cannot_escape_the_python_root(
    tmp_path: Path, platform: str, python_name: str, separator: str
) -> None:
    package_root = tmp_path / "package"
    package_root.mkdir()
    python = package_root / python_name
    python.touch()
    outside_packages = tmp_path / "outside" / "site-packages"
    outside_packages.mkdir(parents=True)
    _write_package_manifest(package_root, packages="../outside/site-packages", executable=python_name)
    node = outside_packages.parent / "node" / ("node.exe" if platform == "win32" else "bin/node")
    node.parent.mkdir(parents=True)
    node.touch()
    provider_bins = str(tmp_path / "codex")

    environment = agent_launch_environment(
        storage_root=tmp_path / "storage",
        agent_root=tmp_path / "agent",
        relay=tmp_path / "cadrumo-mcp",
        aeat=None,
        python=python,
        received={EXTERNAL_BIN_DIRECTORIES_VARIABLE: provider_bins},
        sys_platform=platform,
    )

    assert environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE] == provider_bins
    assert str(node.parent) not in environment[EXTERNAL_BIN_DIRECTORIES_VARIABLE]


_RECEIVED = {
    "SystemRoot": "C:\\Windows",
    "PATH": "C:\\Windows\\System32",
    "USERPROFILE": "C:\\Users\\person",
    "EXAMPLE_PROVIDER_API_KEY": "sk-ant-test-NOT-A-REAL-KEY",
    "OTHER_PROVIDER_API_KEY": "sk-test-NOT-A-REAL-KEY",
    "AWS_SECRET_ACCESS_KEY": "aws-test-NOT-A-REAL-KEY",
    "CADRUMO_LLM_EXAMPLE_API_KEY": "sk-ant-test-NOT-A-REAL-KEY",
    "CADRUMO_AGENT_EXAMPLE_API_KEY": "sk-ant-test-NOT-A-REAL-KEY",
    "CADRUMO_AGENT_OTHER_API_KEY": "sk-ant-test-NOT-A-REAL-KEY",
    "CADRUMO_AGENT_GATEWAY_TOKEN": "gateway-test-NOT-A-REAL-TOKEN",
    "GITHUB_TOKEN": "ghp-test-NOT-A-REAL-TOKEN",
    "PYTHONPATH": "C:\\elsewhere",
}

# The retired relay slot; the runtime advertises the tool server instead.
_RETIRED_RELAY_VARIABLE = "CADRUMO_AGENT_HOSTED_" + "RELAY_EXECUTABLE"
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
        aeat=tmp_path / "aeat.exe",
        python=tmp_path / "python.exe",
        received=_RECEIVED,
        sys_platform="win32",
    )
    assert environment[HOSTED_ROOT_VARIABLE] == str(agent_root)
    assert environment["SYSTEMROOT"] == "C:\\Windows"
    assert environment["USERPROFILE"] == "C:\\Users\\person"
    assert "NOT-A-REAL" not in repr(environment)
    for name in (
        "EXAMPLE_PROVIDER_API_KEY",
        "OTHER_PROVIDER_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "GITHUB_TOKEN",
        "PYTHONPATH",
    ):
        assert name not in environment
    assert not any(name.startswith("CADRUMO_LLM_") or name == "CADRUMO_AGENT_GATEWAY_TOKEN" for name in environment)


def test_posix_hosts_keep_only_their_own_allow_list(tmp_path: Path) -> None:
    received = {"HOME": "/home/person", "PATH": "/usr/bin", "EXAMPLE_PROVIDER_API_KEY": "sk-ant-test-NOT-A-REAL-KEY"}
    environment = agent_launch_environment(
        storage_root=tmp_path / "storage",
        agent_root=tmp_path / "storage" / "agent" / "opaque",
        relay=tmp_path / "cadrumo-mcp",
        aeat=tmp_path / "aeat",
        python=tmp_path / "python",
        received=received,
        sys_platform="linux",
    )
    assert environment["HOME"] == "/home/person"
    assert "EXAMPLE_PROVIDER_API_KEY" not in environment
    assert "NOT-A-REAL" not in repr(environment)


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_the_runtime_fills_exactly_the_gateway_slots_and_advertises_exactly_what_cadrumo_supplies(
    tmp_path: Path, platform: str
) -> None:
    agent_root = tmp_path / "storage" / "agent" / "opaque"
    relay = tmp_path / "bin" / "cadrumo-mcp"
    aeat = tmp_path / "bin" / "aeat"
    python = tmp_path / "bin" / "python"
    # Every agent setting the runtime itself received, the retired program paths included, stays behind.
    received = {
        **_RECEIVED,
        "HOME": "/home/person",
        **dict.fromkeys(_RETIRED_PROGRAM_VARIABLES, str(tmp_path / "bin" / "aeat")),
        _RETIRED_RELAY_VARIABLE: str(relay),
        HOSTED_ROOT_VARIABLE: str(tmp_path / "elsewhere"),
        GATEWAY_PORT_VARIABLE: "8080",
        "CADRUMO_AGENT_DEVELOPMENT_TOOL_SERVER": "true",
        "CADRUMO_AGENT_ENV_FILE": str(tmp_path / "agent.env"),
        "CADRUMO_AGENT_SKILLS_DIR": str(tmp_path / "retired-skills"),
        "CADRUMO_AGENT_RULES_DIR": str(tmp_path / "retired-rules"),
        STORAGE_ROOT.variable: str(tmp_path / "the-developers-own-root"),
    }
    environment = agent_launch_environment(
        storage_root=tmp_path / "storage",
        agent_root=agent_root,
        relay=relay,
        aeat=aeat,
        python=python,
        received=received,
        sys_platform=platform,
    )
    assert {
        name for name in environment if name.startswith("CADRUMO_AGENT_")
    } == AGENT_SLOTS | ADVERTISED_VARIABLES | DIAGNOSTIC_VARIABLES
    assert {HOSTED_ROOT_VARIABLE, GATEWAY_PORT_VARIABLE, WORKER_PORT_VARIABLE} == AGENT_SLOTS
    assert AGENT_SLOTS | {"CADRUMO_LOCAL_STORAGE_ROOT"} == GATEWAY_SLOTS
    assert set(environment) >= GATEWAY_SLOTS
    assert not set(_RETIRED_PROGRAM_VARIABLES) & set(environment)
    assert not _RETIRED_INSTRUCTION_VARIABLES & set(environment)
    assert _RETIRED_RELAY_VARIABLE not in environment
    assert not (set(_RETIRED_PROGRAM_VARIABLES) | {_RETIRED_RELAY_VARIABLE}) & GATEWAY_SLOTS
    # The agent forwards the runtime's own root to what it starts, never the root the runtime itself received.
    assert environment["CADRUMO_LOCAL_STORAGE_ROOT"] == str(normalize_storage_path(tmp_path / "storage"))
    assert environment[HOSTED_ROOT_VARIABLE] == str(agent_root)
    assert environment[GATEWAY_PORT_VARIABLE] == environment[WORKER_PORT_VARIABLE] == "0"


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_the_advertised_programs_tool_server_and_forwarded_names_are_plain_absolute_values(
    tmp_path: Path, platform: str
) -> None:
    bin_directory = tmp_path.resolve() / "bin"
    environment = agent_launch_environment(
        storage_root=tmp_path / "storage",
        agent_root=tmp_path / "storage" / "agent" / "opaque",
        relay=bin_directory / "cadrumo-mcp",
        aeat=bin_directory / "aeat",
        python=bin_directory / "python",
        received={"PATH": "x"},
        sys_platform=platform,
    )
    assert environment[PROGRAM_AEAT_VARIABLE] == str(bin_directory / "aeat")
    assert environment[PROGRAM_PYTHON_VARIABLE] == str(bin_directory / "python")
    assert environment[TOOL_SERVER_VARIABLE] == str(bin_directory / "cadrumo-mcp")
    # The surface comes from the application's own definition, and the value is a JSON array of strings.
    assert json.loads(environment[TOOL_SERVER_ARGUMENTS_VARIABLE]) == ["--surface", DEFAULT_MCP_SURFACE.value]
    assert not _RETIRED_INSTRUCTION_VARIABLES & set(environment)
    for variable in (PROGRAM_AEAT_VARIABLE, PROGRAM_PYTHON_VARIABLE, TOOL_SERVER_VARIABLE):
        assert Path(environment[variable]).is_absolute()
    forwarded = environment[FORWARD_VARIABLE].split(",")
    assert forwarded == [STORAGE_ROOT.variable]
    assert all(name in environment for name in forwarded)
    # The agent refuses a forwarded name under its own prefix; the prefix is spelled by the composer's own names.
    own_prefix = TOOL_SERVER_VARIABLE.removesuffix("TOOL_SERVER_CADRUMO")
    assert not any(name.startswith(own_prefix) for name in forwarded)
    # Each program, tool server and arguments name ends in a name of capitals and digits.
    for variable in (
        PROGRAM_AEAT_VARIABLE,
        PROGRAM_PYTHON_VARIABLE,
        TOOL_SERVER_VARIABLE,
        TOOL_SERVER_ARGUMENTS_VARIABLE,
    ):
        assert re.fullmatch(r"[A-Z0-9]+", variable.rsplit("_", 1)[-1]), variable


def test_a_program_the_runtime_cannot_name_is_left_out_not_advertised_empty(tmp_path: Path) -> None:
    environment = agent_launch_environment(
        storage_root=tmp_path / "storage",
        agent_root=tmp_path / "storage" / "agent" / "opaque",
        relay=tmp_path / "bin" / "cadrumo-mcp",
        aeat=None,
        python=None,
        received={"PATH": "x"},
        sys_platform="linux",
    )
    assert PROGRAM_AEAT_VARIABLE not in environment
    assert PROGRAM_PYTHON_VARIABLE not in environment
    assert TOOL_SERVER_VARIABLE in environment


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
        aeat=programs / "aeat.exe",
        python=programs / "python.exe",
        received={"PATH": search_path},
        sys_platform=platform,
    )
    assert environment["PATH"] == search_path


@pytest.mark.parametrize("override,expected", [(None, "debug"), ("info", "info"), ("ERROR", "error"), ("bad", "debug")])
def test_agent_diagnostic_capture_level(tmp_path: Path, override: str | None, expected: str) -> None:
    environment = agent_launch_environment(
        storage_root=tmp_path / "storage",
        agent_root=tmp_path / "agent",
        relay=tmp_path / "relay",
        aeat=None,
        python=None,
        received={} if override is None else {AGENT_LOG_LEVEL_VARIABLE: override},
    )
    assert environment[AGENT_LOG_LEVEL_VARIABLE] == expected
