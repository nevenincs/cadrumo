"""Focused tests for installed CLI receipt parsing."""

from __future__ import annotations

import json
import secrets
import subprocess
from pathlib import Path

import pytest

from dev.acceptance import installed_cli as installed_cli_module
from dev.acceptance.installed_cli import InstalledCli, decode_cli_document

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_cli_document_decoder_recovers_error_envelope_after_stderr_diagnostic() -> None:
    document = decode_cli_document(
        "",
        'diagnostic before envelope\n{"schema_version":"2","status":"error","error":{"code":"REFUSED"}}\n',
    )

    assert document["status"] == "error"
    assert document["error"]["code"] == "REFUSED"


def test_installed_cli_rebuilds_the_child_environment_and_delivers_secrets_only_on_stdin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shared adapter isolates one installed process without exposing its unlock secret."""
    executable = tmp_path / "aeat.exe"
    authority_root = tmp_path / "authority"
    storage_root = tmp_path / "storage"
    executable.write_bytes(b"installed executable")
    authority_root.mkdir()
    storage_root.mkdir()
    monkeypatch.setenv("CADRUMO_UNRELATED", "must-not-reach-child")
    monkeypatch.setenv("PYTHONPATH", "must-not-reach-child")
    monkeypatch.setenv("PYTHONHOME", "must-not-reach-child")
    monkeypatch.setenv("VIRTUAL_ENV", "must-not-reach-child")
    passphrase = secrets.token_urlsafe(24)
    observed: list[dict[str, object]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed.append({"argv": argv, **kwargs})
        return subprocess.CompletedProcess(
            argv,
            0,
            '{"schema_version":"2","status":"success","notices":[{"code":"NOTICE"}]}',
            "",
        )

    monkeypatch.setattr(installed_cli_module.subprocess, "run", fake_run)
    cli = InstalledCli(executable, storage_root=storage_root, authority_root=authority_root, passphrase=passphrase)

    cli.create_profile(year=2025)

    assert len(observed) == 2
    first, second = observed
    assert passphrase not in first["argv"]
    assert passphrase not in second["argv"]
    assert json.loads(str(first["input"])) == {
        "passphrase": passphrase,
        "passphrase_confirmation": passphrase,
    }
    assert json.loads(str(second["input"])) == {"profile_passphrase": passphrase}
    environment = first["env"]
    assert isinstance(environment, dict)
    assert environment["CADRUMO_LOCAL_STORAGE_ROOT"] == str(storage_root.resolve())
    assert environment["CADRUMO_AUTHORITY_ROOT"] == str(authority_root.resolve())
    assert "CADRUMO_UNRELATED" not in environment
    assert "PYTHONPATH" not in environment
    assert "PYTHONHOME" not in environment
    assert "VIRTUAL_ENV" not in environment
    assert tuple(cli.commands) == (
        installed_cli_module.CommandEvidence("config profile create", 0, "success", ("NOTICE",)),
        installed_cli_module.CommandEvidence("config profile complete-setup", 0, "success", ("NOTICE",)),
    )


def test_installed_cli_records_a_non_json_refusal_without_retaining_its_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An accepted refusal retains its actual exit code and no raw diagnostic payload."""
    executable = tmp_path / "aeat.exe"
    authority_root = tmp_path / "authority"
    storage_root = tmp_path / "storage"
    executable.write_bytes(b"installed executable")
    authority_root.mkdir()
    storage_root.mkdir()

    def fake_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 2, "", "private command diagnostic")

    monkeypatch.setattr(installed_cli_module.subprocess, "run", fake_run)
    cli = InstalledCli(
        executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=secrets.token_urlsafe(24),
    )

    document = cli.run(("app", "ledger", "list"), allow_error=True)

    assert document["status"] == "error"
    assert document["error"] == {
        "code": "acceptance.installed_cli.non_json_failure",
        "context": {
            "returncode": 2,
            "stderr_length": len("private command diagnostic"),
            "stderr_sha256": "6d8fd9a66eef07138c4f3a0895a15858e2334816ee228be10b1f5e20702edb53",
        },
    }
    assert cli.commands == [installed_cli_module.CommandEvidence("app ledger list", 2, "non_json_failure", ())]
