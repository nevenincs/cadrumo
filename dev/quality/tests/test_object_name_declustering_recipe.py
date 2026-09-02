"""Rendered and executed contracts for the object-name declustering recipe."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Final, cast

import pytest

from ..._paths import REPO_ROOT
from ...ci.lane_reachability import resolve_just_executable
from ..object_name_declustering import _parser

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPOSITORY_ROOT: Final = REPO_ROOT
_RECIPE: Final = "fix-object-names"
_CLI_PREFIX: Final = [
    "run",
    "--no-sync",
    "python",
    "-m",
    "dev.quality.object_name_declustering",
]


def _just(*args: str, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - resolved real just binary and fixed repository recipe.
        [resolve_just_executable(), *args],
        cwd=_REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _dump() -> dict[str, object]:
    result = _just("--unstable", "--dump", "--dump-format", "json")
    assert result.returncode == 0, result.stderr
    document: object = json.loads(result.stdout)
    assert isinstance(document, dict)
    recipes = cast("dict[str, object]", document)["recipes"]
    assert isinstance(recipes, dict)
    recipe = cast("dict[str, object]", recipes)[_RECIPE]
    assert isinstance(recipe, dict)
    return cast("dict[str, object]", recipe)


@pytest.fixture
def _pwsh_runtime() -> str:
    executable = shutil.which("pwsh.exe")
    if executable is None:
        pytest.skip("the Justfile recipe requires pwsh.exe")
    return executable


@pytest.fixture
def uv_probe(tmp_path: Path, _pwsh_runtime: str) -> tuple[dict[str, str], Path]:
    """Shadow ``uv`` with a PowerShell probe that records exact received argv."""
    probe = tmp_path / "probe.ps1"
    probe.write_text(
        """param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Remaining)
$json = ConvertTo-Json -Compress -InputObject @($Remaining)
[System.IO.File]::WriteAllText($env:OBJECT_NAME_ARGV_CAPTURE, $json)
exit [int]$env:OBJECT_NAME_PROBE_EXIT_CODE
""",
        encoding="utf-8",
    )
    executable = tmp_path / "uv.cmd"
    executable.write_text(
        '@pwsh.exe -NoLogo -NoProfile -File "%~dp0probe.ps1" %*\n',
        encoding="utf-8",
    )
    capture = tmp_path / "argv.json"
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join((str(tmp_path), environment["PATH"]))
    environment["OBJECT_NAME_ARGV_CAPTURE"] = str(capture)
    environment["OBJECT_NAME_PROBE_EXIT_CODE"] = "0"
    return environment, capture


def _captured_argv(capture: Path) -> list[str]:
    payload = json.loads(capture.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert all(isinstance(argument, str) for argument in payload)
    return [argument for argument in payload if isinstance(argument, str)]


def test_recipe_is_discoverable_in_the_mutations_group() -> None:
    result = _just("--list", "--list-heading", "")

    assert result.returncode == 0, result.stderr
    assert "[mutations]" in result.stdout
    mutations = result.stdout.split("[mutations]", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]
    assert f"{_RECIPE} *ARGS" in mutations


def test_real_justfile_dump_pins_the_complete_safe_recipe_contract() -> None:
    recipe = _dump()

    assert recipe["doc"] == (
        "Rehearse a reviewed object-name component by default; live application requires explicit arguments."
    )
    assert recipe["parameters"] == [
        {
            "default": None,
            "export": False,
            "help": None,
            "kind": "star",
            "long": None,
            "name": "ARGS",
            "pattern": None,
            "short": None,
            "value": None,
        }
    ]
    assert recipe["attributes"] == [
        {"group": "mutations"},
        "positional-arguments",
        {"script": {"arguments": ["-NoLogo", "-File"], "command": "pwsh.exe"}},
    ]
    assert recipe["body"] == [
        ["& uv run --no-sync python -m dev.quality.object_name_declustering @args"],
        ["exit $LASTEXITCODE"],
    ]
    assert recipe["dependencies"] == []
    assert recipe["private"] is False
    assert recipe["shebang"] is True


def test_no_argument_show_and_dry_run_contain_no_apply_authority() -> None:
    shown = _just("--show", _RECIPE)
    dry_run = _just("--dry-run", _RECIPE)

    assert shown.returncode == dry_run.returncode == 0
    assert "dev.quality.object_name_declustering @args" in shown.stdout
    assert dry_run.stdout == ""
    assert dry_run.stderr.splitlines() == [
        "& uv run --no-sync python -m dev.quality.object_name_declustering @args",
        "exit $LASTEXITCODE",
    ]
    for rendered in (shown.stdout, dry_run.stderr):
        assert " apply" not in rendered
        assert "--receipt" not in rendered
        assert "--receipt-id" not in rendered
    assert _parser().parse_args([]).mode == "rehearse"


def test_no_argument_invocation_reaches_the_cli_default_rehearsal_without_apply(
    uv_probe: tuple[dict[str, str], Path],
) -> None:
    environment, capture = uv_probe

    result = _just(_RECIPE, environment=environment)

    assert result.returncode == 0, result.stderr
    argv = _captured_argv(capture)
    assert argv == _CLI_PREFIX
    assert "apply" not in argv
    assert "--receipt" not in argv


@pytest.mark.parametrize(
    "arguments",
    [
        ("inventory", "--json"),
        ("plan", "--manifest", "dev/quality/reviewed.toml"),
        (
            "apply",
            "--manifest",
            "dev/quality/reviewed.toml",
            "--receipt",
            "receipt.json",
            "--receipt-id",
            "receipt-123",
            "--json",
        ),
    ],
)
def test_explicit_modes_and_arguments_are_forwarded_exactly(
    uv_probe: tuple[dict[str, str], Path],
    arguments: tuple[str, ...],
) -> None:
    environment, capture = uv_probe

    result = _just(_RECIPE, *arguments, environment=environment)

    assert result.returncode == 0, result.stderr
    assert _captured_argv(capture) == [*_CLI_PREFIX, *arguments]


def test_recipe_propagates_the_powershell_child_exit_code(
    uv_probe: tuple[dict[str, str], Path],
) -> None:
    environment, capture = uv_probe
    environment["OBJECT_NAME_PROBE_EXIT_CODE"] = "23"

    result = _just(_RECIPE, "verify", environment=environment)

    assert _captured_argv(capture) == [*_CLI_PREFIX, "verify"]
    assert result.returncode == 23


@pytest.mark.parametrize(
    "invalid_mode",
    [
        "mode with spaces",
        "mode&Write-Output-injected",
        "mode;Write-Output-injected",
        "mode'with-quote",
        "mode$(Write-Output-injected)",
    ],
)
def test_invalid_mode_metacharacters_remain_one_argv_and_propagate_exit_two(
    invalid_mode: str,
    _pwsh_runtime: str,
) -> None:
    result = _just(_RECIPE, invalid_mode)

    assert result.returncode == 2
    assert result.stdout == ""
    assert f"invalid choice: {invalid_mode!r}" in result.stderr
    assert "injected\n" not in result.stdout


def test_explicit_nonexistent_manifest_makes_real_rehearsal_fail_closed(
    tmp_path: Path,
    _pwsh_runtime: str,
) -> None:
    relative_manifest = Path("dev/quality/tests") / f"missing-{tmp_path.name}.toml"
    manifest = _REPOSITORY_ROOT / relative_manifest
    assert not manifest.exists()

    result = _just(_RECIPE, "rehearse", "--manifest", relative_manifest.as_posix())

    assert result.returncode == 2
    assert result.stdout == ""
    assert "manifest path is not a regular file" in result.stderr
    assert not manifest.exists()
