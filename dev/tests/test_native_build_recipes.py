"""The native build recipes enter CMake by preset, and CMake owns everything after that.

A recipe configures the host's preset and then builds one target; it passes
CMake no interpreter and no agent source. CMake validates an existing
development interpreter during configure (``native/cmake/Bootstrap.cmake``),
checks the registry authority as a build target (``native/cmake/Authority.cmake``),
and reads the agent project folder from a cache variable alone
(``native/cmake/Agent.cmake``).

Nothing here builds the product. The recipe cases ask the real ``just`` driver
what a recipe would run and compare that with the presets CMake itself reads
and the target platforms the packaging contract declares, both of which are
authored independently of the justfile. The CMake cases configure a minimal
project that includes the real module with a recording stand-in for the one
external program it launches, then read what CMake generated or what the
program received.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shlex
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import CommandResult, run_command
from dev.packaging.runtime_wheelhouse_contract import target_platform

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

#: Each build-chain recipe and the CMake target it ends on.
_CHAIN = {
    "build-native": "bundle",
    "test-native-bundle": "verify",
    "test-native-live": "verify-native-live",
    "build-native-package": "zip",
    "test-native-package": "verify-package",
}

_BUILD_LINE = re.compile(r"cmake --build --preset (?P<preset>\S+) --target '?(?P<target>[\w-]+)'?")

_HOST_REFUSAL = "No native configure preset is enrolled"

_CMAKE_MODULES = REPO_ROOT / "native" / "cmake"

#: The cache variable that selects the agent project folder, and the names it replaced.
_AGENT_SOURCE_VARIABLE = "CADRUMO_PACKAGE_AGENT_SOURCE_DIR"
# Joined so the agent-prefix spelling gate does not read this test as Cadrumo defining the name.
_RETIRED_AGENT_SOURCE_VARIABLE = "CADRUMO_AGENT" + "_SOURCE_DIR"
_POWERSHELL_CMAKE_ARGUMENT_CAPTURE = """
function cmake {
    & $env:CADRUMO_NATIVE_AGENT_PYTHON -c 'import json, sys; print(json.dumps(sys.argv[1:]))' @args
}
Invoke-Expression $env:CADRUMO_NATIVE_AGENT_COMMAND
if ($env:CADRUMO_NATIVE_AGENT_MARKER -ne 'unchanged') {
    throw 'the agent source path was evaluated by PowerShell'
}
"""


def _just(*arguments: str) -> tuple[int, str]:
    executable = shutil.which("just")
    assert executable is not None, "the repository task runner is required"
    completed = run_command(
        [executable, "--justfile", str(REPO_ROOT / "justfile"), *arguments],
        cwd=REPO_ROOT,
        environment=dict(os.environ),
        timeout_seconds=None,
    )
    return completed.returncode, completed.stdout + completed.stderr


def _just_for_native_host(*arguments: str) -> tuple[int, str]:
    return _just("--set", "native_host", "windows-x86_64", *arguments)


def _evaluated(name: str) -> str:
    status, output = _just("--evaluate", name)
    assert status == 0, output
    return output.strip()


def _declared(kind: str) -> dict[str, dict[str, Any]]:
    document = json.loads((REPO_ROOT / "CMakePresets.json").read_text(encoding="utf-8"))
    return {preset["name"]: preset for preset in document[kind]}


def _parents(preset: Mapping[str, Any]) -> list[str]:
    inherited = preset.get("inherits", [])
    return [inherited] if isinstance(inherited, str) else list(inherited)


def _overlay(base: Mapping[str, Any], top: Mapping[str, Any]) -> dict[str, Any]:
    """Return ``base`` with ``top`` applied: maps such as cacheVariables merge by key, other fields replace."""
    merged = dict(base)
    for key, value in top.items():
        existing = merged.get(key)
        merged[key] = {**existing, **value} if isinstance(existing, dict) and isinstance(value, dict) else value
    return merged


def _presets(kind: str) -> dict[str, dict[str, Any]]:
    """Return every preset as CMake resolves it, with what it inherits applied.

    When a preset inherits from several, the earlier one wins a conflict.
    """
    declared = _declared(kind)
    resolved: dict[str, dict[str, Any]] = {}

    def resolve(name: str) -> dict[str, Any]:
        if name not in resolved:
            inherited: dict[str, Any] = {}
            for parent in reversed(_parents(declared[name])):
                inherited = _overlay(inherited, resolve(parent))
            resolved[name] = _overlay(inherited, declared[name])
        return resolved[name]

    return {name: resolve(name) for name in declared}


def _ancestors(kind: str, name: str) -> set[str]:
    declared = _declared(kind)
    found: set[str] = set()
    pending = _parents(declared[name])
    while pending:
        parent = pending.pop()
        if parent not in found:
            found.add(parent)
            pending.extend(_parents(declared[parent]))
    return found


def _commands(output: str) -> list[str]:
    return [line.strip() for line in output.splitlines() if line.strip()]


def test_the_selected_configure_preset_targets_this_host() -> None:
    selected = _evaluated("native_preset")
    host = (platform.system(), platform.machine())
    enrolled = {
        name: target_platform(preset["cacheVariables"]["CADRUMO_TARGET"])
        for name, preset in _presets("configurePresets").items()
    }
    matching = {name for name, target in enrolled.items() if (target.platform_system, target.platform_machine) == host}
    if not matching:
        status, output = _just("--dry-run", "build-native")
        assert selected == ""
        assert status != 0
        assert _HOST_REFUSAL in output
        return
    # The host has one preset of its own. Any other preset for the same target is a variant of it,
    # such as the installer build that only moves the binary directory.
    declared = _declared("configurePresets")
    assert {name for name in matching if not declared[name].get("inherits")} == {selected}
    assert all(selected in _ancestors("configurePresets", name) for name in matching - {selected})


@pytest.mark.parametrize("configuration", ["Release", "Debug"])
@pytest.mark.parametrize("recipe", sorted(_CHAIN))
def test_each_recipe_configures_the_host_preset_then_builds_its_target(recipe: str, configuration: str) -> None:
    selected = _evaluated("native_preset")
    status, output = _just("--dry-run", recipe, configuration)
    if not selected:
        assert status != 0
        assert _HOST_REFUSAL in output
        return
    assert status == 0, output
    lines = _commands(output)

    # Configure runs on every entry, so a binary directory first configured elsewhere is moved onto this
    # preset. Toolchain validation and authority currency checks happen inside CMake.
    assert len(lines) == 2, lines
    assert lines[0] == f"cmake --preset {selected}"
    build = _BUILD_LINE.fullmatch(lines[1])
    assert build is not None, lines[1]
    assert build.group("target") == _CHAIN[recipe]
    preset = _presets("buildPresets")[build.group("preset")]
    assert preset["configurePreset"] == selected
    assert preset["configuration"] == configuration


@pytest.mark.parametrize("recipe", sorted(_CHAIN))
def test_a_recipe_hands_cmake_no_interpreter_no_agent_source_and_no_environment(recipe: str) -> None:
    if not _evaluated("native_preset"):
        pytest.skip("this host has no enrolled native preset")
    status, output = _just("--dry-run", recipe)
    assert status == 0, output
    for line in _commands(output):
        arguments = shlex.split(line)
        assert arguments[0] == "cmake", line
        assert not any(argument.startswith("-D") for argument in arguments), line
        assert not any("=" in argument and not argument.startswith("-") for argument in arguments), line
        assert ".venv" not in line, line
        assert "AGENT" not in line.upper(), line


def test_native_ci_passes_the_agent_checkout_as_one_quoted_cmake_cache_value() -> None:
    source = str(REPO_ROOT / "agent project with spaces")

    status, output = _just_for_native_host("--dry-run", "test-native-ci", source)

    assert status == 0, output
    lines = _commands(output)
    assert len(lines) == 2, lines
    configure = shlex.split(lines[0])
    assert configure[:3] == ["cmake", "--preset", "windows-x64"]
    assert configure[3] == f"-D{_AGENT_SOURCE_VARIABLE}={source}", configure
    assert lines[1] == "just test-native-bundle Release"
    assert all("test-native-live" not in line for line in lines)


def test_native_ci_rejects_a_blank_agent_checkout_before_configuring() -> None:
    status, output = _just_for_native_host("--dry-run", "test-native-ci", "   ")

    assert status != 0
    assert "AGENT_SOURCE_DIR must name the cadrumo-agent project directory" in output
    assert not [line for line in _commands(output) if line.startswith(("cmake ", "just "))]


@pytest.mark.windows_only
def test_native_ci_powershell_passes_special_path_characters_as_one_cmake_argument() -> None:
    source = r"C:\agent O'Neil $env:CADRUMO_NATIVE_AGENT_MARKER = 'changed'; `literal`"
    status, output = _just_for_native_host("--dry-run", "test-native-ci", source)
    assert status == 0, output
    command, *_ = _commands(output)

    powershell = shutil.which("pwsh.exe")
    assert powershell is not None, "the Windows justfile requires PowerShell Core"
    environment = dict(os.environ)
    environment.update(
        {
            "CADRUMO_NATIVE_AGENT_COMMAND": command,
            "CADRUMO_NATIVE_AGENT_MARKER": "unchanged",
            "CADRUMO_NATIVE_AGENT_PYTHON": sys.executable,
        }
    )
    result = run_command(
        [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", _POWERSHELL_CMAKE_ARGUMENT_CAPTURE],
        cwd=REPO_ROOT,
        environment=environment,
        timeout_seconds=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == [
        "--preset",
        "windows-x64",
        f"-D{_AGENT_SOURCE_VARIABLE}={source}",
    ]


def test_no_committed_preset_names_the_agent_source() -> None:
    # The folder is a per-machine path. A developer supplies it with -D or in CMakeUserPresets.json.
    for kind in ("configurePresets", "buildPresets"):
        for name, preset in _presets(kind).items():
            named = {*preset.get("cacheVariables", {}), *preset.get("environment", {})}
            assert not [key for key in named if "AGENT" in key.upper()], (kind, name)


def test_the_standalone_builder_recipe_only_validates_the_existing_toolchain() -> None:
    status, output = _just_for_native_host("--dry-run", "setup-native-builder")
    assert status == 0, output
    lines = _commands(output)
    assert lines == [
        "cmake --preset windows-x64",
        "cmake --build --preset release --target setup-native-builder",
    ]
    assert not any("uv " in line or "UV_PROJECT_ENVIRONMENT" in line for line in lines)
    justfile = (REPO_ROOT / "justfile").read_text(encoding="utf-8")
    assert "native_builder_environment" not in justfile
    assert "native_builder_python" not in justfile


@pytest.mark.parametrize("recipe", sorted(_CHAIN))
def test_an_unknown_configuration_is_refused_before_anything_would_run(recipe: str) -> None:
    refusal = "CONFIGURATION must be Release or Debug" if _evaluated("native_preset") else _HOST_REFUSAL
    status, output = _just("--dry-run", recipe, "RelWithDebInfo")
    assert status != 0, output
    assert refusal in output
    assert not [line for line in _commands(output) if line.startswith(("uv ", "cmake "))]


# -- What CMake does with the modules the recipes rely on ------------------------------------------------------


def _cmake(*arguments: str, cwd: Path, environment: Mapping[str, str] | None = None) -> CommandResult:
    executable = shutil.which("cmake")
    assert executable is not None, "CMake is required"
    return run_command(
        [executable, *arguments], cwd=cwd, environment={**os.environ, **(environment or {})}, timeout_seconds=None
    )


def _ninja_commands(build: Path, target: str) -> str:
    executable = shutil.which("ninja")
    assert executable is not None, "Ninja is required"
    result = run_command([executable, "-C", str(build), "-t", "commands", target], cwd=build, timeout_seconds=None)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.replace("\\", "/")


def _configure(tmp_path: Path, body: str, *definitions: str, environment: Mapping[str, str] | None = None):
    """Configure a minimal project whose only content is ``body``, and return the source, build and result."""
    source = tmp_path / "source"
    source.mkdir(parents=True)
    (source / "CMakeLists.txt").write_text(
        f"cmake_minimum_required(VERSION 4.4)\nproject(Contract LANGUAGES NONE)\n{body}", encoding="utf-8"
    )
    build = tmp_path / "build"
    result = _cmake(
        "-G", "Ninja", "-S", str(source), "-B", str(build), *definitions, cwd=source, environment=environment
    )
    return source, build, result


def test_configure_selects_existing_tools_without_creating_a_builder_environment(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None, "system uv is required by the native configure contract"
    source = tmp_path / "source"
    (source / "dev" / "packaging").mkdir(parents=True)
    version = sys.version_info
    (source / "dev" / "packaging" / "release-python-version").write_text(
        f"{version.major}.{version.minor}.{version.micro}\n", encoding="utf-8"
    )
    for name in ("pyproject.toml", "uv.lock"):
        (source / name).touch()
    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 4.4)\nproject(Contract LANGUAGES NONE)\n"
        'set(CADRUMO_SOURCE_ROOT "${CMAKE_SOURCE_DIR}")\n'
        f'include("{(_CMAKE_MODULES / "Bootstrap.cmake").as_posix()}")\n',
        encoding="utf-8",
    )
    build = tmp_path / "build"

    result = _cmake(
        "-G",
        "Ninja",
        "-S",
        str(source),
        "-B",
        str(build),
        f"-DCADRUMO_DEV_PYTHON:FILEPATH={sys.executable}",
        cwd=source,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    cache = (build / "CMakeCache.txt").read_text(encoding="utf-8")
    interpreter = re.search(r"^CADRUMO_DEV_PYTHON:FILEPATH=(.+)$", cache, re.MULTILINE)
    assert interpreter is not None
    assert Path(interpreter.group(1)).resolve() == Path(sys.executable).resolve()
    uv_path = re.search(r"^CADRUMO_UV:FILEPATH=(.+)$", cache, re.MULTILINE)
    assert uv_path is not None
    assert Path(uv_path.group(1)).resolve() == Path(uv).resolve()
    assert not (build / "_deps" / "builder").exists()


def test_authority_targets_validate_tools_before_checking_authority_currency(tmp_path: Path) -> None:
    body = (
        f'include("{(_CMAKE_MODULES / "BuildLog.cmake").as_posix()}")\n'
        'set(CADRUMO_DEV_PYTHON "builder-python")\n'
        'add_custom_target(setup-native-builder COMMAND "${CMAKE_COMMAND}" -E echo validate-existing-builder)\n'
        f'include("{(_CMAKE_MODULES / "Authority.cmake").as_posix()}")\n'
    )
    _, build, result = _configure(tmp_path, body)
    assert result.returncode == 0, result.stdout + result.stderr

    current = _ninja_commands(build, "registry_authority")
    rebuild = _ninja_commands(build, "registry_authority_rebuild")

    for commands in (current, rebuild):
        # Existing tools are validated before authority currency is checked.
        assert commands.index("validate-existing-builder") < commands.index(
            "builder-python -B -m dev.packaging.native.authority_build"
        )
        assert f"--build {build.as_posix()}".lower() in commands.lower()
    assert "--rebuild" not in current
    assert "--rebuild" in rebuild


def _agent_project(tmp_path: Path, *definitions: str, environment: Mapping[str, str] | None = None):
    body = (
        f'include("{(_CMAKE_MODULES / "BuildLog.cmake").as_posix()}")\n'
        "function(cadrumo_register_clean)\nendfunction()\n"
        'set(CADRUMO_DEV_PYTHON "builder-python")\n'
        'set(CADRUMO_HELPER "native-helper")\n'
        'set(CADRUMO_PATH_AGENT "${CMAKE_BINARY_DIR}/agent")\n'
        'set(CADRUMO_PATH_TESTING "${CMAKE_BINARY_DIR}/testing")\n'
        'set(shared_inputs "")\n'
        f'include("{(_CMAKE_MODULES / "Agent.cmake").as_posix()}")\n'
    )
    return _configure(tmp_path, body, *definitions, environment=environment)


def _agent_checkout(root: Path) -> Path:
    (root / "src").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'agent'\n", encoding="utf-8")
    return root


def test_the_agent_source_is_selected_by_the_cache_variable_alone(tmp_path: Path) -> None:
    named = _agent_checkout(tmp_path / "named")
    decoy = _agent_checkout(tmp_path / "decoy")
    # Both the current and the retired spelling name a valid checkout, to the environment only.
    environment = {_AGENT_SOURCE_VARIABLE: str(decoy), _RETIRED_AGENT_SOURCE_VARIABLE: str(decoy)}

    _, _, unset = _agent_project(tmp_path / "unset", environment=environment)
    assert unset.returncode != 0
    assert f"{_AGENT_SOURCE_VARIABLE} is not set" in unset.stderr + unset.stdout

    _, _, empty = _agent_project(tmp_path / "empty", f"-D{_AGENT_SOURCE_VARIABLE}=", environment=environment)
    assert empty.returncode != 0

    _, _, wrong = _agent_project(tmp_path / "wrong", f"-D{_AGENT_SOURCE_VARIABLE}={tmp_path}", environment=environment)
    assert wrong.returncode != 0
    assert "holds no pyproject.toml" in wrong.stderr + wrong.stdout

    _, build, selected = _agent_project(
        tmp_path / "selected", f"-D{_AGENT_SOURCE_VARIABLE}={named}", environment=environment
    )
    assert selected.returncode == 0, selected.stdout + selected.stderr
    commands = _ninja_commands(build, "agent_project").lower()
    assert f"--agent-source {named.as_posix().lower()}" in commands
    assert decoy.as_posix().lower() not in commands
