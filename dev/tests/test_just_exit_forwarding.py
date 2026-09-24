"""Every justfile recipe line hands its command's own exit status to `just`.

`dev/EXIT-CODES.md` gives statuses meaning -- a tool that is missing, a tool
that broke, a selection that ran nothing -- and a gate that shells out through
`just` can only act on that meaning if the status survives the recipe shell.
PowerShell's `-Command` host exits 1 for any failing native command, which once
reduced every one of those statuses to a generic failure. These tests run the
repository's own shell settings through the real `just` driver, so a setting
that stops forwarding fails here rather than in a gate that misreads a broken
tool as a finding.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from dev.exit_codes import PYTEST_NO_TESTS_COLLECTED, TOOL_BROKEN, TOOL_MISSING
from dev.packaging.command_execution import CommandResult, run_command

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

#: Repository root: this file is `<root>/dev/tests/<name>.py`.
ROOT = Path(__file__).resolve().parents[2]

#: The settings that choose the shell every recipe line runs in.
_SHELL_SETTING = re.compile(r"^set (?:windows-)?shell\s*:=.*$", re.MULTILINE)


def _shell_settings() -> str:
    settings = [match.group(0) for match in _SHELL_SETTING.finditer((ROOT / "justfile").read_text(encoding="utf-8"))]
    assert settings, "the justfile declares no recipe shell, so there is nothing to prove"
    return "\n".join(settings)


def _run_recipe(tmp_path: Path, *lines: str) -> CommandResult:
    """Run ``lines`` as one recipe under the repository's shell settings."""
    justfile = tmp_path / "justfile"
    body = "".join(f"    {line}\n" for line in lines)
    justfile.write_text(f"{_shell_settings()}\n\nprobe:\n{body}", encoding="utf-8")
    just_executable = shutil.which("just")
    assert just_executable is not None, "the real just driver is required to prove the recipe shell"
    return run_command(
        [just_executable, "--justfile", str(justfile), "probe"],
        cwd=tmp_path,
        errors="replace",
        timeout_seconds=60,
    )


@pytest.mark.parametrize("status", [TOOL_BROKEN, TOOL_MISSING, PYTEST_NO_TESTS_COLLECTED])
def test_a_failing_command_reaches_just_with_its_own_status(tmp_path: Path, status: int) -> None:
    result = _run_recipe(tmp_path, f'@python -c "raise SystemExit({status})"')

    assert result.returncode == status, result.stdout + result.stderr


def test_a_passing_command_passes(tmp_path: Path) -> None:
    result = _run_recipe(tmp_path, '@python -c "pass"')

    assert result.returncode == 0, result.stdout + result.stderr


def test_a_recipe_stops_at_its_failing_line_with_that_lines_status(tmp_path: Path) -> None:
    result = _run_recipe(
        tmp_path,
        '@python -c "print(1)"',
        f'@python -c "raise SystemExit({TOOL_BROKEN})"',
        '@python -c "print(3)"',
    )

    assert result.returncode == TOOL_BROKEN, result.stdout + result.stderr
    assert result.stdout.split() == ["1"]


def test_single_quoted_arguments_reach_the_command_whole(tmp_path: Path) -> None:
    """The reason this repository runs recipes in pwsh at all: `-m 'unit and not perf'` stays one argument."""
    result = _run_recipe(tmp_path, "@python -c \"import sys; print(sys.argv[1:])\" -m 'unit and not perf'")

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "['-m', 'unit and not perf']"
