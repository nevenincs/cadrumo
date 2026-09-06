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
import os
import shutil
import stat
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


def test_final_cleanup_routes_every_uninstall_through_the_retry_helper() -> None:
    """The cleanup never bare-uninstalls: reap + bounded retry, fail-loud verify.

    A handle held on the exercised venv right after the oracle makes the first
    ``scoop uninstall`` fail ("it may be in use"), after which scoop
    AUTO-REPAIRS (relinks ``current``, recreates shims) — so each retry must
    re-run uninstall, and the retained-app assertions stay fail-loud.
    """
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "function Stop-ProcessesUnderPath" in source
    retry_start = source.index("function Invoke-ScoopUninstallWithRetry")
    retry_body = source[retry_start : source.index("function Get-ScoopRoot")]
    # The retry loop reaps first and RE-RUNS uninstall on every attempt.
    assert "Stop-ProcessesUnderPath -Root $AppRoot" in retry_body
    assert "& scoop uninstall $PackageName @ExtraArguments" in retry_body
    assert "for ($attempt = 1; $attempt -le 3" in retry_body
    # The finally-block cleanup routes both the staged app and every newly
    # appeared app through the helper; no bare uninstall remains there.
    finally_body = source[source.index("$cleanupErrors = ") : source.index("function Assert-WindowsContainerRuntime")]
    assert finally_body.count("Invoke-ScoopUninstallWithRetry") == 2
    assert "& scoop uninstall" not in finally_body
    # The fail-loud retained-app assertions survive untouched.
    assert "cleanup retained the staged Scoop app" in finally_body


def _run_uninstall_retry(interpreter: str, *, app_root: Path, scoop_bin_dir: Path) -> subprocess.CompletedProcess[str]:
    """Drive the SHIPPED retry helper against a real scripted scoop on PATH.

    The variable is spelled ``PATH``, in capitals, because PowerShell inherits
    the platform's environment-variable case rules: on Windows ``$env:Path``
    and ``$env:PATH`` are one variable, but on macOS and Linux they are two.
    Writing ``$env:Path`` there created a second, unread variable and left the
    real search path untouched, so the scripted scoop this test places on it
    was never found and the shipped helper died on a missing command -- a
    failure that looks exactly like the helper being broken.
    """
    driver = f"""
$source = Get-Content -Raw -LiteralPath '{_SCRIPT}'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) {{ throw "smoke_scoop.ps1 does not parse: $($errors[0])" }}
foreach ($name in @('Stop-ProcessesUnderPath', 'Invoke-ScoopUninstallWithRetry')) {{
    $fn = $ast.FindAll({{ param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
    }}, $true)[0]
    Invoke-Expression $fn.Extent.Text
}}
$env:PATH = '{scoop_bin_dir}' + [System.IO.Path]::PathSeparator + $env:PATH
$ErrorActionPreference = 'Stop'
$retryArguments = @{{
    PackageName = 'cadrumo-scoop-acquisition'
    AppRoot = '{app_root}'
    ExtraArguments = @('--purge')
    SettleSeconds = 0
}}
$result = Invoke-ScoopUninstallWithRetry @retryArguments
Write-Output "RESULT=$result"
"""
    return subprocess.run(  # noqa: S603 - explicit resolved interpreter, literal in-test driver
        [interpreter, "-NoProfile", "-Command", driver],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


def _write_scripted_scoop(scoop_bin_dir: Path, app_root: Path, *, succeed_on_attempt: int) -> Path:
    """Write a real ``scoop`` substitute: fails with the app retained until attempt N."""
    scoop_bin_dir.mkdir(parents=True, exist_ok=True)
    script = scoop_bin_dir / "scoop_script.py"
    script.write_text(
        f"""
import json, shutil, sys
from pathlib import Path

scoop_bin_dir = Path({str(scoop_bin_dir)!r})
app_root = Path({str(app_root)!r})
succeed_on = {succeed_on_attempt}
counter = scoop_bin_dir / "attempts.txt"
attempt = int(counter.read_text() or "0") + 1 if counter.is_file() else 1
counter.write_text(str(attempt))
with (scoop_bin_dir / "calls.log").open("a", encoding="utf-8") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[1] != "uninstall":
    raise SystemExit(2)
if attempt >= succeed_on:
    shutil.rmtree(app_root, ignore_errors=True)
    raise SystemExit(0)
sys.stderr.write("Couldn't remove the app; it may be in use\\n")
raise SystemExit(1)
""",
        encoding="utf-8",
    )
    if sys.platform.startswith("win"):
        launcher = scoop_bin_dir / "scoop.cmd"
        launcher.write_text(
            f'@echo off\r\n"{sys.executable}" "{script}" %*\r\nexit /b %errorlevel%\r\n',
            encoding="utf-8",
        )
    else:
        launcher = scoop_bin_dir / "scoop"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return launcher


def test_process_reap_is_separator_anchored_to_the_app_root(tmp_path: Path) -> None:
    """A sibling dir sharing the root's name prefix never gets its process reaped.

    Two REAL processes run from copied interpreters: one under the app root
    (must be reaped) and one under ``<root>-foo`` (must survive — an
    unanchored StartsWith would match it and kill an unrelated app on the
    shared runner).
    """
    interpreter = _interpreter()
    if interpreter is None:
        return  # structural contract asserted above; no interpreter on this host
    root = tmp_path / "apps" / "python"
    sibling = tmp_path / "apps" / "python-foo"
    if sys.platform.startswith("win"):
        source = Path(os.environ["COMSPEC"])
        holder_name = "hold.exe"
        hold_arguments = "@('/c', 'ping', '-n', '60', '127.0.0.1')"
    else:
        source = Path("/bin/sleep")
        holder_name = "hold"
        hold_arguments = "@('60')"
    under_exe = root / holder_name
    sibling_exe = sibling / holder_name
    for target in (under_exe, sibling_exe):
        target.parent.mkdir(parents=True, exist_ok=True)
        # copy, not copy2: copy2 replicates BSD file flags, and on macOS the
        # system /bin/sleep carries the SIP `restricted` flag, which no user may
        # set on the copy. The mode bits copy carries are all this needs -- the
        # chmod below adds the execute bit either way.
        shutil.copy(source, target)
        if not sys.platform.startswith("win"):
            target.chmod(target.stat().st_mode | stat.S_IEXEC)
    driver = f"""
$source = Get-Content -Raw -LiteralPath '{_SCRIPT}'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$errors)
$fn = $ast.FindAll({{ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Stop-ProcessesUnderPath'
}}, $true)[0]
Invoke-Expression $fn.Extent.Text
$underProcess = Start-Process -FilePath '{under_exe}' -ArgumentList {hold_arguments} -PassThru
$siblingProcess = Start-Process -FilePath '{sibling_exe}' -ArgumentList {hold_arguments} -PassThru
try {{
    Stop-ProcessesUnderPath -Root '{root}'
    Start-Sleep -Milliseconds 500
    Write-Output "UNDER_EXITED=$($underProcess.HasExited)"
    Write-Output "SIBLING_EXITED=$($siblingProcess.HasExited)"
}}
finally {{
    foreach ($held in @($underProcess, $siblingProcess)) {{
        try {{ Stop-Process -Id $held.Id -Force -ErrorAction Stop }} catch {{ }}
    }}
}}
"""
    completed = subprocess.run(  # noqa: S603 - explicit resolved interpreter, literal in-test driver
        [interpreter, "-NoProfile", "-Command", driver],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr
    assert "UNDER_EXITED=True" in completed.stdout
    assert "SIBLING_EXITED=False" in completed.stdout


def test_uninstall_retry_reruns_until_windows_releases_the_handle(tmp_path: Path) -> None:
    """Attempts 1-2 fail in-use; attempt 3 succeeds — helper returns True."""
    interpreter = _interpreter()
    if interpreter is None:
        return  # structural contract asserted above; no interpreter on this host
    app_root = tmp_path / "apps" / "cadrumo-scoop-acquisition"
    (app_root / "0.2.1").mkdir(parents=True)
    scoop_bin_dir = tmp_path / "scoop"
    _write_scripted_scoop(scoop_bin_dir, app_root, succeed_on_attempt=3)
    completed = _run_uninstall_retry(interpreter, app_root=app_root, scoop_bin_dir=scoop_bin_dir)
    assert completed.returncode == 0, completed.stderr
    assert "RESULT=True" in completed.stdout
    assert not app_root.exists()
    calls = (scoop_bin_dir / "calls.log").read_text(encoding="utf-8").splitlines()
    # Every retry RE-RAN uninstall (scoop auto-repairs after a failure).
    assert len(calls) == 3
    assert all('"uninstall"' in call for call in calls)


def test_uninstall_retry_stays_fail_loud_when_the_app_never_releases(tmp_path: Path) -> None:
    """Three failed attempts return False so the caller's refusal fires."""
    interpreter = _interpreter()
    if interpreter is None:
        return  # structural contract asserted above; no interpreter on this host
    app_root = tmp_path / "apps" / "cadrumo-scoop-acquisition"
    (app_root / "0.2.1").mkdir(parents=True)
    scoop_bin_dir = tmp_path / "scoop"
    _write_scripted_scoop(scoop_bin_dir, app_root, succeed_on_attempt=99)
    completed = _run_uninstall_retry(interpreter, app_root=app_root, scoop_bin_dir=scoop_bin_dir)
    assert completed.returncode == 0, completed.stderr
    assert "RESULT=False" in completed.stdout
    assert app_root.exists()
    calls = (scoop_bin_dir / "calls.log").read_text(encoding="utf-8").splitlines()
    assert len(calls) == 3


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
