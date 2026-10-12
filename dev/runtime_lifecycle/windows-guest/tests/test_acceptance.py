"""Offline acceptance-transport policy; these tests make no installed-health claim."""

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest
from dev.packaging.command_execution import CommandResult, run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.external_tool]

OWNER = Path(__file__).resolve().parents[1]
SOURCE = OWNER.parents[2]
MODULES = (
    "dev/__init__.py",
    "dev/runtime_lifecycle/__init__.py",
    "dev/runtime_lifecycle/harness.py",
    "dev/runtime_lifecycle/installed.py",
    "dev/runtime_lifecycle/client_probes.py",
    "dev/packaging/__init__.py",
    "dev/packaging/command_execution.py",
)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _configuration(tmp_path: Path, *, dispatcher: bytes | None = None) -> dict[str, Any]:
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    (baseline / "windows.vars").write_bytes(b"fixture firmware")
    (baseline / "windows.mac").write_bytes(b"fixture mac")
    uuid = "12345678-1234-1234-1234-123456789abc"
    volume = "owned-guest-volume"
    receipt = {
        "uuid": uuid,
        "volume": volume,
        "snapshot": "clean",
        "normalClock": True,
        "uacEnabled": True,
        "helpersAbsent": True,
        "productTransferred": False,
        "productInstalled": False,
        "guestFullyStopped": True,
        "tpmPresent": False,
    }
    baseline_receipt = baseline / "receipt.json"
    baseline_receipt.write_text(json.dumps(receipt), encoding="utf-8")
    secret = tmp_path / "password.dpapi"
    # ValidateOnly never decrypts this file or executes Docker/WinRM.
    secret.write_bytes(b"not a credential")
    config = {
        "schema": 1,
        "uuid": uuid,
        "sid": "S-1-5-21-1-2-3-1000",
        "computer": "Fixture",
        "account": "SelectedUser",
        "container": "owned-guest",
        "volume": volume,
        "network": "owned-network",
        "guestImage": "sha256:" + "a" * 64,
        "rdpImage": "sha256:" + "b" * 64,
        "tlsPin": "c" * 64,
        "port": 15986,
        "passwordFile": str(secret),
        "fixtureRoot": str(tmp_path),
        "baselineReceipt": str(baseline_receipt),
        "baselineReceiptSha256": _digest(baseline_receipt.read_bytes()),
        "firmwareVarsSha256": _digest((baseline / "windows.vars").read_bytes()),
        "firmwareMacSha256": _digest((baseline / "windows.mac").read_bytes()),
    }
    for cohort, version in (("P1", "0.6.2"), ("P2", "0.6.3")):
        files = {
            "app/python.exe": b"fixture only",
            "app/data/package-manifest.json": json.dumps({"build": {"version": version}}).encode(),
            "services/kit.json": json.dumps({"maintenance": {"version": version}}).encode(),
            "metadata/wix/user-registration.wxs": b"fixture",
            "metadata/wix/machine-registration.wxs": b"fixture",
            "metadata/native/manager_dispatch.py": dispatcher
            if dispatcher is not None
            else (SOURCE / "native/desktop/src-tauri/src/python/manager_dispatch.py").read_bytes(),
        }
        files.update({f"owners/{module}": (SOURCE / module).read_bytes() for module in MODULES})
        # The real sealer records critical metadata and owners, not the whole payload.
        inventory = {
            "version": version,
            "files": {name: _digest(content) for name, content in files.items() if name != "app/python.exe"},
        }
        archive = tmp_path / f"{cohort}.zip"
        with ZipFile(archive, "w") as zip_file:
            for name, content in files.items():
                zip_file.writestr(name, content)
            zip_file.writestr("cohort.json", json.dumps(inventory))
        archive_receipt = tmp_path / f"{cohort}-receipt.json"
        archive_receipt.write_text(
            json.dumps(
                {"path": str(archive), "sha256": _digest(archive.read_bytes()), "bytes": archive.stat().st_size}
            ),
            encoding="utf-8",
        )
        config[cohort] = {
            "archive": str(archive),
            "receipt": str(archive_receipt),
            "sha256": _digest(archive.read_bytes()),
            "version": version,
        }
        if cohort == "P2":
            for name, content in files.items():
                if name.startswith(("app/", "services/")):
                    target = tmp_path / "stage" / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
    return config


def _run(tmp_path: Path, config: dict[str, Any] | None) -> CommandResult:
    executable = shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell 7 acceptance host is unavailable")
    path = tmp_path / "config.json"
    if config is not None:
        path.write_text(json.dumps(config), encoding="utf-8")
    return run_command(
        [
            executable,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(OWNER / "acceptance.ps1"),
            "-Config",
            str(path),
            "-Stage",
            str(tmp_path / "stage"),
            "-Source",
            str(SOURCE),
            "-Output",
            str(tmp_path / "output"),
            "-ValidateOnly",
        ],
        cwd=SOURCE,
        timeout_seconds=30,
    )


def test_missing_configuration_fails_before_guest_access(tmp_path: Path) -> None:
    result = _run(tmp_path, None)
    assert result.returncode != 0
    assert "installed_guest_configuration_required" in result.stderr
    assert not (tmp_path / "output").exists()


def test_verified_offline_configuration_is_not_installed_acceptance(tmp_path: Path) -> None:
    result = _run(tmp_path, _configuration(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "no guest executed" in result.stdout
    assert not (tmp_path / "output").exists()


def test_sealed_foreign_dispatcher_cannot_replace_the_production_launch_route(tmp_path: Path) -> None:
    config = _configuration(tmp_path, dispatcher=b"different launch implementation")
    result = _run(tmp_path, config)
    assert result.returncode != 0
    assert "installed_current_dispatcher_mismatch" in result.stderr
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("field", ["P2", "tlsPin", "guestImage", "baselineReceiptSha256"])
def test_missing_successor_or_unpinned_fixture_refuses(tmp_path: Path, field: str) -> None:
    config = _configuration(tmp_path)
    config.pop(field)
    assert _run(tmp_path, config).returncode != 0
    assert not (tmp_path / "output").exists()


def test_changed_current_payload_cannot_borrow_a_sealed_successor(tmp_path: Path) -> None:
    config = _configuration(tmp_path)
    (tmp_path / "stage" / "app" / "python.exe").write_bytes(b"different bytes")
    result = _run(tmp_path, config)
    assert result.returncode != 0
    assert "installed_current_cohort_hash_mismatch" in result.stderr


def test_firmware_change_cannot_borrow_clean_baseline_receipt(tmp_path: Path) -> None:
    config = _configuration(tmp_path)
    (tmp_path / "baseline" / "windows.vars").write_bytes(b"different firmware")
    result = _run(tmp_path, config)
    assert result.returncode != 0
    assert "installed_guest_firmware_digest_mismatch" in result.stderr


def test_extra_stage_member_is_not_part_of_the_sealed_successor(tmp_path: Path) -> None:
    config = _configuration(tmp_path)
    (tmp_path / "stage" / "app" / "unsealed.exe").write_bytes(b"extra bytes")
    result = _run(tmp_path, config)
    assert result.returncode != 0
    assert "installed_current_cohort_member_missing" in result.stderr


def test_archive_receipt_is_checked_before_any_guest_action(tmp_path: Path) -> None:
    config = _configuration(tmp_path)
    receipt = Path(config["P2"]["receipt"])
    receipt.write_text(json.dumps({"path": config["P1"]["archive"], "sha256": config["P2"]["sha256"], "bytes": 1}))
    result = _run(tmp_path, config)
    assert result.returncode != 0
    assert "installed_guest_archive_receipt_mismatch" in result.stderr
    assert not (tmp_path / "output").exists()


def test_promoted_scripts_parse_and_compile_native_declarations_without_guest_actions() -> None:
    executable = shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell 7 acceptance host is unavailable")
    command = (
        "$ErrorActionPreference='Stop'; foreach($file in Get-ChildItem -LiteralPath "
        + "'"
        + str(OWNER).replace("'", "''")
        + "' -Filter '*.ps1')"
        "{$errors=$null;$tokens=$null;"
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$errors);"
        "if($errors){throw 'transport_parse_failed'};"
        "$native=$ast.FindAll({param($node) "
        "$node -is [System.Management.Automation.Language.StringConstantExpressionAst] "
        "-and $node.Value.StartsWith('using System;')},$true);"
        "foreach($declaration in $native){Add-Type -TypeDefinition $declaration.Value}}"
    )
    result = run_command(
        [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=SOURCE,
        timeout_seconds=30,
    )
    assert result.returncode == 0, result.stderr


def test_reboot_readiness_rejects_old_boot_and_closes_rejected_sessions() -> None:
    executable = shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell 7 acceptance host is unavailable")
    # Execute the actual bounded polling owner with offline native observations.
    # This verifies the old-boot race, without launching or authenticating a guest.
    owner = str(OWNER / "acceptance.ps1").replace("'", "''")
    command = (
        "$ErrorActionPreference='Stop';$errors=$null;$tokens=$null;"
        f"$ast=[System.Management.Automation.Language.Parser]::ParseFile('{owner}',"
        "[ref]$tokens,[ref]$errors);if($errors){throw 'parse_failed'};"
        "$function=$ast.Find({param($node) "
        "$node -is [System.Management.Automation.Language.FunctionDefinitionAst] "
        "-and $node.Name -eq 'Wait-FixtureSession'},$true);"
        "Invoke-Expression $function.Extent.Text;"
        "$script:opened=0;$script:closed=@();$script:GuestUuid='offline';"
        "$script:Facts=[Collections.Generic.List[object]]::new();"
        "function Open-GuestSession {$script:opened++;[pscustomobject]@{id=$script:opened}};"
        "function Invoke-Command($Session,$ArgumentList,$ScriptBlock) "
        "{if($Session.id -lt 3){[long]100}else{[long]200}};"
        "function Remove-PSSession($Session) {$script:closed+= $Session.id};"
        "function Start-Sleep($Seconds) {};"
        "$ready=Wait-FixtureSession -PriorBootTicks 100;"
        "@{ready=$ready.id;closed=$script:closed;facts=@($script:Facts.ToArray())}"
        "|ConvertTo-Json -Depth 5 -Compress"
    )
    result = run_command(
        [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=SOURCE,
        timeout_seconds=30,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["ready"] == 3
    assert evidence["closed"] == [1, 2]
    assert evidence["facts"] == [
        {"scope": "machine", "phase": "reboot", "priorBootTicks": 100, "bootTicks": 200, "state": "settled"}
    ]


@pytest.mark.parametrize("invalid", ["none", "oversized", "directory", "reparse"])
def test_native_failure_evidence_is_run_bound_and_refuses_unsafe_entries(tmp_path: Path, invalid: str) -> None:
    executable = shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell 7 acceptance host is unavailable")
    payload = b'{"code":"native_rolled_back"}\n'
    receipt = tmp_path / "receipt.json"
    receipt.write_bytes(payload)
    owner = str(OWNER / "acceptance.ps1").replace("'", "''")
    root = str(tmp_path).replace("'", "''")
    command = (
        "$ErrorActionPreference='Stop';$errors=$null;$tokens=$null;"
        f"$ast=[System.Management.Automation.Language.Parser]::ParseFile('{owner}',"
        "[ref]$tokens,[ref]$errors);"
        "$function=$ast.Find({param($node) "
        "$node -is [System.Management.Automation.Language.FunctionDefinitionAst] "
        "-and $node.Name -eq 'Retain-GuestEvidence'},$true);"
        "Invoke-Expression $function.Extent.Text;"
        f"$script:fixture='{root}';$script:invalid='{invalid}';$directory=$script:fixture;"
        "function Invoke-Command($Session,$ArgumentList,$ScriptBlock) {& $ScriptBlock $ArgumentList};"
        "function Get-Item($LiteralPath) {"
        "if($LiteralPath.StartsWith('C:\\acceptance')) "
        "{[pscustomobject]@{PSIsContainer=$true;Attributes=[IO.FileAttributes]::Directory}} "
        "else{Microsoft.PowerShell.Management\\Get-Item -LiteralPath $LiteralPath}};"
        "function Get-ChildItem($LiteralPath,$Filter) {if($LiteralPath -eq 'C:\\acceptance\\P1\\intents') {"
        "foreach($age in 'old','new') {"
        "$name='native-maintenance-failure-'+$(if($age -eq 'old'){'a'*32}else{'b'*32})+'.json';"
        "[pscustomobject]@{Name=$name;FullName=$LiteralPath+'\\'+$name;DirectoryName=$LiteralPath;"
        "CreationTimeUtc=[DateTime]::Parse($(if($age -eq 'old'){'2020-01-01T00:00:00Z'}"
        "else{'2020-01-03T00:00:00Z'})).ToUniversalTime();"
        "PSIsContainer=($script:invalid -eq 'directory');"
        "Attributes=$(if($script:invalid -eq 'reparse'){[IO.FileAttributes]::ReparsePoint}"
        "else{[IO.FileAttributes]::Normal});"
        "Length=$(if($script:invalid -eq 'oversized'){65537}else{"
        "(Microsoft.PowerShell.Management\\Get-Item ($script:fixture+'/receipt.json')).Length})}}}};"
        "function Get-FileHash($LiteralPath,$Algorithm) {"
        "if($LiteralPath.StartsWith('C:\\acceptance')){$LiteralPath=$script:fixture+'/receipt.json'};"
        "Microsoft.PowerShell.Utility\\Get-FileHash -LiteralPath $LiteralPath -Algorithm $Algorithm};"
        "function Copy-Item($LiteralPath,$Destination,$FromSession) {"
        "if($LiteralPath.StartsWith('C:\\acceptance')){$LiteralPath=$script:fixture+'/receipt.json'};"
        "Microsoft.PowerShell.Management\\Copy-Item -LiteralPath $LiteralPath -Destination $Destination};"
        "$run=@{id='offline';runPath=$script:fixture+'/absent';createdAtUtc='2020-01-02T00:00:00Z'};"
        "Retain-GuestEvidence 'offline' $run 'user' 'hold'"
    )
    result = run_command(
        [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=SOURCE,
        timeout_seconds=30,
    )
    if invalid != "none":
        assert result.returncode != 0
        assert "native_failure_evidence_file_invalid" in result.stderr
        return
    assert result.returncode == 0, result.stderr
    evidence = tmp_path / "user-hold-offline"
    records = json.loads((evidence / "native-maintenance-failures.json").read_text(encoding="utf-8"))
    assert len(records) == 1
    assert records[0]["run"] == "offline"
    assert records[0]["runCreatedAtUtc"] == "2020-01-02T00:00:00Z"
    assert records[0]["cohort"] == "P1"
    assert records[0]["sha256"] == _digest(payload)
    assert (evidence / records[0]["file"]).read_bytes() == payload


def test_native_task_evidence_boundary_precedes_dispatch() -> None:
    executable = shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell 7 acceptance host is unavailable")
    owner = str(OWNER / "transport.ps1").replace("'", "''")
    command = (
        "$ErrorActionPreference='Stop';$errors=$null;$tokens=$null;"
        f"$ast=[System.Management.Automation.Language.Parser]::ParseFile('{owner}',"
        "[ref]$tokens,[ref]$errors);"
        "$function=$ast.Find({param($node) "
        "$node -is [System.Management.Automation.Language.FunctionDefinitionAst] "
        "-and $node.Name -eq 'Start-GuestPhase'},$true);"
        "$boundary=$function.Find({param($node) "
        "$node -is [System.Management.Automation.Language.AssignmentStatementAst] "
        "-and $node.Left -is [System.Management.Automation.Language.VariableExpressionAst] "
        "-and $node.Left.VariablePath.UserPath -eq 'createdAtUtc'},$true);"
        "$dispatch=$function.Find({param($node) "
        "$node -is [System.Management.Automation.Language.InvokeMemberExpressionAst] "
        "-and $node.Member.Value -eq 'Run'},$true);"
        "if(!$boundary -or !$dispatch -or $boundary.Extent.EndOffset -ge $dispatch.Extent.StartOffset) "
        "{throw 'native_evidence_boundary_after_dispatch'}"
    )
    result = run_command(
        [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=SOURCE,
        timeout_seconds=30,
    )
    assert result.returncode == 0, result.stderr
