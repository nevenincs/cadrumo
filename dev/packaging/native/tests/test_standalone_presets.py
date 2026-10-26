"""Standalone CMake projects build into ``build/<configure preset name>``; the desktop has no build of its own."""

from __future__ import annotations

import base64
import json
import os
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
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-HostBuildDirectory'
}, $false)
$default = @($ast.EndBlock.Statements | Where-Object {
    $_ -is [Management.Automation.Language.IfStatementAst] -and
    $_.Clauses[0].Item1.Extent.Text -eq '-not $BuildDirectory'
})
if (-not $reader -or $default.Count -ne 1) { throw 'The runner has no single preset-derived BuildDirectory default.' }
$Repository = <repository>
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
    assert projects
    root_names = [preset["name"] for preset in _configure_presets(REPO_ROOT)]
    names = list(root_names)
    for project in projects:
        for preset in _configure_presets(project):
            names.append(preset["name"])
            assert _same_directory(_binary_directory(project, preset), REPO_ROOT / "build" / preset["name"]), preset
    assert len(names) == len(set(names)), "Two configure presets would share one binary directory"


def test_desktop_has_no_build_tree_of_its_own() -> None:
    assert DESKTOP not in _standalone_projects()
    assert not (DESKTOP / "CMakePresets.json").exists()


@pytest.mark.skipif(os.name != "nt", reason="The desktop test runners are Windows PowerShell scripts")
@pytest.mark.parametrize("runner", RUNNERS)
def test_desktop_runner_defaults_to_the_windows_repository_preset(runner: str) -> None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    assert powershell is not None

    harness = _RUNNER_DEFAULT
    for name, path in {"<runner>": DESKTOP / "tests" / runner, "<repository>": REPO_ROOT}.items():
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
        for preset in _configure_presets(REPO_ROOT)
        if preset.get("cacheVariables", {}).get("CADRUMO_TARGET") == "windows-x86-64"
    ]
    assert _same_directory(result.stdout.strip().splitlines()[-1], REPO_ROOT / "build" / windows)


@pytest.mark.windows_only
def test_backend_environment_unsets_absent_values_and_restores_the_original_environment() -> None:
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    assert powershell is not None
    runner = str(DESKTOP / "tests/run-backend.ps1").replace("'", "''")
    harness = """
$ErrorActionPreference = 'Stop'
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile('<runner>', [ref]$null, [ref]$errors)
if ($errors) { throw "The runner does not parse: $errors" }
$setter = $ast.Find({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Set-TestEnvironment'
}, $false)
. ([scriptblock]::Create($setter.Extent.Text))
$saved = @{}
$present = 'CADRUMO_TEST_RUNNER_PRESENT'
$absent = 'CADRUMO_TEST_RUNNER_ABSENT'
Set-Item -LiteralPath "Env:$present" -Value 'original'
Remove-Item -LiteralPath "Env:$absent" -ErrorAction SilentlyContinue
Set-TestEnvironment $present 'overridden'
Set-TestEnvironment $absent 'temporary'
Set-TestEnvironment $present $null
Set-TestEnvironment $absent $null
$environment = [Environment]::GetEnvironmentVariables('Process')
if ($environment.Contains($present) -or $environment.Contains($absent)) { throw 'Null must remove the variable' }
foreach ($name in $saved.Keys) { Set-TestEnvironment $name $saved[$name] }
$environment = [Environment]::GetEnvironmentVariables('Process')
if ($environment[$present] -ne 'original') { throw 'The original value was not restored' }
if ($environment.Contains($absent)) { throw 'An originally absent variable must remain absent' }
""".replace("<runner>", runner)
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
