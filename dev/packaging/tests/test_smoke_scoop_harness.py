"""Tests for the Scoop container harness's native-command invocation contract.

The container child runs under Windows PowerShell 5.1 with the script-wide
``$ErrorActionPreference = "Stop"``, where the first merged (``2>&1``) stderr
line of a native command becomes a terminating NativeCommandError even when
the command exits 0 — uv (driven by the Scoop manifest installer) writes
informational lines like "Using CPython ... interpreter at" to stderr, which
false-failed the lane. ``Invoke-Native`` must therefore gate on the exit code
alone under a scoped ``Continue`` preference, without silencing stderr.

The execution tests drive the SHIPPED function text (AST-extracted from
``smoke_scoop.ps1``) in a real PowerShell subprocess against real native
commands; where no PowerShell interpreter exists (POSIX CI without pwsh) the
structural contract assertions still bind. Full-container behavior is verified
manually via ``smoke_scoop.ps1 -Mode Container`` on a Windows-container host
(the packaging-scoop workflow's own run is the end-to-end proof).
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SCRIPT: Final = Path(__file__).resolve().parents[1] / "smoke_scoop.ps1"


def _interpreter() -> str | None:
    """Resolve a real PowerShell interpreter; mandatory on Windows.

    Windows prefers ``powershell`` (5.1): that is the engine whose merged
    stderr becomes a terminating NativeCommandError under a Stop preference,
    i.e. the exact regression environment of the container child. pwsh 7.2+
    no longer promotes native stderr, so it only proves the happy path.
    """
    if sys.platform.startswith("win"):
        resolved = shutil.which("powershell") or shutil.which("pwsh")
        assert resolved is not None, "a Windows host must expose powershell or pwsh"
        return resolved
    return shutil.which("pwsh")


def test_invoke_native_gates_on_exit_code_not_stderr_presence() -> None:
    """The shipped function scopes Continue and decides by exit code only."""
    source = _SCRIPT.read_text(encoding="utf-8")
    # The script keeps its global fail-fast posture...
    assert '$ErrorActionPreference = "Stop"' in source
    # ...while Invoke-Native scopes Continue around the native invocation and
    # restores the caller's preference afterwards, gating on the exit code.
    start = source.index("function Invoke-Native")
    body = source[start : source.index("function Get-ScoopRoot")]
    assert '$ErrorActionPreference = "Continue"' in body
    assert "$ErrorActionPreference = $previousPreference" in body
    assert body.count("$LASTEXITCODE") >= 1
    assert "2>&1" in body  # stderr stays captured, never silenced


def _run_invoke_native(interpreter: str, inner_command: str, extra: str = "") -> subprocess.CompletedProcess[str]:
    """Execute the SHIPPED Invoke-Native text against a real native command.

    The inner command rides ``-EncodedCommand`` so no quoting layer (Windows
    PowerShell's native-argument quoting mangles embedded double quotes) can
    distort what the child interpreter executes.
    """
    encoded = base64.b64encode(inner_command.encode("utf-16-le")).decode("ascii")
    driver = f"""
$source = Get-Content -Raw -LiteralPath '{_SCRIPT}'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) {{ throw "smoke_scoop.ps1 does not parse: $($errors[0])" }}
$fn = $ast.FindAll({{ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Invoke-Native'
}}, $true)[0]
Invoke-Expression $fn.Extent.Text
$ErrorActionPreference = 'Stop'
Invoke-Native -FilePath '{interpreter}' -ArgumentList @('-NoProfile', '-EncodedCommand', '{encoded}') {extra}
Write-Output 'INVOKE-NATIVE-SURVIVED'
"""
    return subprocess.run(  # noqa: S603 - explicit resolved interpreter, literal in-test driver
        [interpreter, "-NoProfile", "-Command", driver],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def test_informational_stderr_with_exit_zero_survives() -> None:
    """uv-style stderr chatter on a successful command must not fail the lane."""
    interpreter = _interpreter()
    if interpreter is None:
        return  # structural contract asserted above; no interpreter on this host
    completed = _run_invoke_native(
        interpreter,
        '[Console]::Error.WriteLine("Using CPython 3.13.11 interpreter at cpython-3.13.11"); exit 0',
    )
    assert completed.returncode == 0, completed.stderr
    assert "INVOKE-NATIVE-SURVIVED" in completed.stdout


def test_nonzero_exit_still_fails_loudly_with_captured_output(tmp_path: Path) -> None:
    """A real failure still throws, and the captured log keeps the stderr detail."""
    interpreter = _interpreter()
    if interpreter is None:
        return  # structural contract asserted above; no interpreter on this host
    log = tmp_path / "native.log"
    completed = _run_invoke_native(
        interpreter,
        '[Console]::Error.WriteLine("real failure detail"); exit 3',
        extra=f"-OutputPath '{log}'",
    )
    assert completed.returncode != 0
    assert "INVOKE-NATIVE-SURVIVED" not in completed.stdout
    assert "exit code 3" in completed.stdout + completed.stderr
    assert "real failure detail" in log.read_text(encoding="utf-8")
