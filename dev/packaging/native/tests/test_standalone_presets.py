"""Standalone CMake projects build into ``build/<configure preset name>``, and the desktop tools default there."""

from __future__ import annotations

import base64
import json
import os
import platform
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

DESKTOP = REPO_ROOT / "native/desktop"
RUNNERS = ("run-packaged.ps1", "run-backend.ps1")
# Runs the runner's own preset reader and its own default assignment, and nothing after them.
_RUNNER_DEFAULT = """
$ErrorActionPreference = 'Stop'
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile(<runner>, [ref]$null, [ref]$errors)
if ($errors) { throw "The runner does not parse: $errors" }
$reader = $ast.Find({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-DesktopPreset'
}, $false)
$default = @($ast.EndBlock.Statements | Where-Object {
    $_ -is [Management.Automation.Language.IfStatementAst] -and
    $_.Clauses[0].Item1.Extent.Text -eq '-not $BuildDirectory'
})
if (-not $reader -or $default.Count -ne 1) { throw 'The runner has no single preset-derived BuildDirectory default.' }
$Repository = <repository>
$Desktop = <desktop>
$BuildDirectory = ''
. ([scriptblock]::Create($reader.Extent.Text))
. ([scriptblock]::Create($default[0].Extent.Text))
[Console]::Out.WriteLine($BuildDirectory)
"""


def _standalone_projects() -> list[Path]:
    """Every directory beneath ``native/`` that declares its own CMake project."""
    projects = []
    for directory, names, files in os.walk(REPO_ROOT / "native"):
        names[:] = [name for name in names if name != "node_modules"]
        if "CMakeLists.txt" in files:
            text = (Path(directory) / "CMakeLists.txt").read_text(encoding="utf-8")
            if re.search(r"^\s*project\(", text, re.MULTILINE):
                projects.append(Path(directory))
    return sorted(projects)


def _configure_presets(project: Path) -> list[dict[str, Any]]:
    presets = json.loads((project / "CMakePresets.json").read_text(encoding="utf-8"))["configurePresets"]
    assert presets, f"{project} declares no configure preset"
    return presets


def _same_directory(actual: str | Path, expected: Path) -> bool:
    return os.path.normcase(os.path.normpath(actual)) == os.path.normcase(os.path.normpath(expected))


def _binary_directory(project: Path, preset: dict[str, Any]) -> str:
    directory: object = preset["binaryDir"]
    name: object = preset["name"]
    assert isinstance(directory, str) and isinstance(name, str)
    expanded = directory.replace("${sourceDir}", project.as_posix()).replace("${presetName}", name)
    assert "$" not in expanded, f"{preset['name']} resolves its binary directory outside the preset file"
    return expanded


def test_standalone_binary_directory_is_named_by_its_configure_preset() -> None:
    projects = _standalone_projects()
    assert DESKTOP in projects
    root_names = [preset["name"] for preset in _configure_presets(REPO_ROOT)]
    names = list(root_names)
    for project in projects:
        for preset in _configure_presets(project):
            names.append(preset["name"])
            assert _same_directory(_binary_directory(project, preset), REPO_ROOT / "build" / preset["name"]), preset
    assert len(names) == len(set(names)), "Two configure presets would share one binary directory"


def _desktop_directory(name: str) -> Path:
    (preset,) = [preset for preset in _configure_presets(DESKTOP) if preset["name"] == name]
    assert preset["condition"] == {"type": "equals", "lhs": "${hostSystemName}", "rhs": platform.system()}
    return REPO_ROOT / "build" / name


def test_frontend_bootstrap_defaults_to_the_host_desktop_preset() -> None:
    node = shutil.which("node")
    assert node is not None
    script = (DESKTOP / "frontend/scripts/bootstrap.mjs").as_uri()
    result = run_command(
        [
            node,
            "--input-type=module",
            "-e",
            f"import {{ hostPreset }} from {json.dumps(script)}; console.log(JSON.stringify(hostPreset()));",
        ],
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    selected = json.loads(result.stdout)
    assert _same_directory(selected["binaryDir"], _desktop_directory(selected["name"]))


@pytest.mark.skipif(os.name != "nt", reason="The desktop test runners are Windows PowerShell scripts")
@pytest.mark.parametrize("runner", RUNNERS)
def test_desktop_runner_defaults_to_the_windows_desktop_preset(runner: str) -> None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    assert powershell is not None

    harness = _RUNNER_DEFAULT
    for name, path in {"<runner>": DESKTOP / "tests" / runner, "<repository>": REPO_ROOT, "<desktop>": DESKTOP}.items():
        harness = harness.replace(name, "'" + str(path).replace("'", "''") + "'")
    result = run_command(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            base64.b64encode(harness.encode("utf-16-le")).decode("ascii"),
        ],
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    (windows,) = [
        preset["name"]
        for preset in _configure_presets(DESKTOP)
        if preset["cacheVariables"]["CADRUMO_TARGET"] == "windows-x86-64"
    ]
    assert _same_directory(result.stdout.strip().splitlines()[-1], _desktop_directory(windows))
