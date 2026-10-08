"""The native build recipes enter CMake with the managed builder and real presets.

CMake owns the build graph, so nothing here builds. Each case asks the real
``just`` driver what a recipe would run and compares that with the presets
CMake itself reads and the target platforms the packaging contract declares,
both of which are authored independently of the justfile.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
from typing import Any

import pytest

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command
from dev.packaging.runtime_wheelhouse_contract import target_platform

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

#: Each build-chain recipe and the CMake target it ends on.
_CHAIN = {
    "build-native": "bundle",
    "test-native-bundle": "verify",
    "build-native-package": "zip",
    "test-native-package": "verify-package",
}

_BUILD_LINE = re.compile(r"cmake --build --preset (?P<preset>\S+) --target '?(?P<target>[\w-]+)'?")

_HOST_REFUSAL = "No native configure preset is enrolled"


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


def _evaluated(name: str) -> str:
    status, output = _just("--evaluate", name)
    assert status == 0, output
    return output.strip()


def _presets(kind: str) -> dict[str, dict[str, Any]]:
    document = json.loads((REPO_ROOT / "CMakePresets.json").read_text(encoding="utf-8"))
    return {preset["name"]: preset for preset in document[kind]}


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
    assert {selected} == matching


@pytest.mark.parametrize("configuration", ["Release", "Debug"])
@pytest.mark.parametrize("recipe", sorted(_CHAIN))
def test_each_recipe_configures_with_the_builder_before_its_target(recipe: str, configuration: str) -> None:
    selected = _evaluated("native_preset")
    status, output = _just("--dry-run", recipe, configuration)
    if not selected:
        assert status != 0
        assert _HOST_REFUSAL in output
        return
    assert status == 0, output
    lines = _commands(output)

    provision = next(index for index, line in enumerate(lines) if line.startswith("uv sync "))
    environment = _evaluated("native_builder_environment")
    assert any("UV_PROJECT_ENVIRONMENT" in line and environment in line for line in lines[:provision])
    assert any("CADRUMO_EDITABLE_AUTHORITY" in line and "skip" in line for line in lines[:provision])
    assert "--locked" in lines[provision]
    assert "dev/packaging/release-python-version" in lines[provision]
    assert not any(".venv" in line for line in lines)

    authority = next(index for index, line in enumerate(lines) if "publish-authority --if-stale" in line)
    configure = lines.index(f"cmake --preset {selected} '-DCADRUMO_DEV_PYTHON={_evaluated('native_builder_python')}'")
    assert provision < configure
    assert authority < configure
    assert configure == len(lines) - 2

    build = _BUILD_LINE.fullmatch(lines[-1])
    assert build is not None, lines[-1]
    assert build.group("target") == _CHAIN[recipe]
    preset = _presets("buildPresets")[build.group("preset")]
    assert preset["configurePreset"] == selected
    assert preset["configuration"] == configuration


@pytest.mark.parametrize("recipe", sorted(_CHAIN))
def test_an_unknown_configuration_is_refused_before_anything_would_run(recipe: str) -> None:
    refusal = "CONFIGURATION must be Release or Debug" if _evaluated("native_preset") else _HOST_REFUSAL
    status, output = _just("--dry-run", recipe, "RelWithDebInfo")
    assert status != 0, output
    assert refusal in output
    assert not [line for line in _commands(output) if line.startswith(("uv ", "cmake "))]
