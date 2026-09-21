"""Sanitized installed-CLI profile setup for the ASSETS-01 TUI journey."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from dev.acceptance.assets.installed_journey import build_assets_installed_environment

_SCHEMA_VERSION = "assets-01-installed-cli-profile-setup-v1"

type ProfileSetupCommandId = Literal["profile_create", "profile_login", "profile_complete_setup", "profile_status"]
type CleanupStatus = Literal["not_needed", "terminated", "failed"]


@dataclass(frozen=True, slots=True)
class InstalledCliCommandReceipt:
    """Safe outcome metadata for one installed CLI command."""

    command: ProfileSetupCommandId
    command_sha256: str
    process_id: int
    return_code: int | None
    timed_out: bool
    cleanup: CleanupStatus
    stdout_sha256: str
    stderr_sha256: str
    response_status: str | None
    error_code: str | None
    setup_state: str | None
    configured: bool | None

    def to_dict(self) -> dict[str, object]:
        """Serialize only nonsecret command and response identities."""
        return {
            "command": self.command,
            "command_sha256": self.command_sha256,
            "process_id": self.process_id,
            "return_code": self.return_code,
            "timed_out": self.timed_out,
            "cleanup": self.cleanup,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "response_status": self.response_status,
            "error_code": self.error_code,
            "setup_state": self.setup_state,
            "configured": self.configured,
        }


@dataclass(frozen=True, slots=True)
class InstalledCliProfileSetupReceipt:
    """Terminal receipt for a supported public profile-readiness scenario."""

    schema_version: str
    status: Literal["proven", "failed"]
    executable_sha256: str
    commands: tuple[InstalledCliCommandReceipt, ...]
    failure_stage: ProfileSetupCommandId | Literal["readiness_assertion"] | None

    def to_dict(self) -> dict[str, object]:
        """Serialize without the synthetic credential, command arguments, or payloads."""
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "executable_sha256": self.executable_sha256,
            "commands": [command.to_dict() for command in self.commands],
            "failure_stage": self.failure_stage,
        }


class InstalledCliProfileSetupError(RuntimeError):
    """A public installed CLI step did not establish a ready profile."""

    def __init__(self, *, receipt: InstalledCliProfileSetupReceipt) -> None:
        """Keep the sanitized receipt available to the calling acceptance driver."""
        super().__init__("installed CLI profile setup did not establish canonical readiness")
        self.receipt = receipt


def _digest(payload: bytes) -> str:
    """Record a stream identity without retaining its content."""
    return hashlib.sha256(payload).hexdigest()


def _public_response_metadata(stdout: bytes, stderr: bytes) -> tuple[str | None, str | None, str | None, bool | None]:
    """Extract only public envelope state from controlled JSON streams."""
    response_status: str | None = None
    error_code: str | None = None
    setup_state: str | None = None
    configured: bool | None = None
    for stream in (stdout, stderr):
        try:
            raw: object = json.loads(stream.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        document = cast("dict[str, object]", raw)
        status = document.get("status")
        if isinstance(status, str):
            response_status = status
        error = document.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            if isinstance(code, str):
                error_code = code
        result = document.get("result")
        if isinstance(result, dict):
            result_mapping = cast("dict[str, object]", result)
            state = result_mapping.get("setup_state")
            if isinstance(state, str):
                setup_state = state
            result_configured = result_mapping.get("configured")
            if isinstance(result_configured, bool):
                configured = result_configured
    return response_status, error_code, setup_state, configured


def _run_command(
    *,
    command: ProfileSetupCommandId,
    executable: Path,
    argv: tuple[str, ...],
    stdin_payload: bytes,
    workspace_root: Path,
    storage_root: Path,
    timeout_seconds: float,
    launcher_prefix: tuple[str, ...] = (),
) -> InstalledCliCommandReceipt:
    """Run one public command with a pipe that closes after its secret payload."""
    full_argv = (str(executable), *launcher_prefix, *argv)
    command_sha256 = hashlib.sha256("\0".join(full_argv).encode("utf-8")).hexdigest()
    process = subprocess.Popen(  # noqa: S603 - fixed scenario argv and owned executable
        full_argv,
        cwd=workspace_root,
        env=build_assets_installed_environment(storage_root=storage_root),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    timed_out = False
    cleanup: CleanupStatus = "not_needed"
    try:
        stdout, stderr = process.communicate(input=stdin_payload, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            process.terminate()
            stdout, stderr = process.communicate(timeout=10.0)
            cleanup = "terminated"
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                stdout, stderr = process.communicate(timeout=10.0)
                cleanup = "terminated"
            except subprocess.TimeoutExpired:
                stdout = b""
                stderr = b""
                cleanup = "failed"
    response_status, error_code, setup_state, configured = _public_response_metadata(stdout, stderr)
    return InstalledCliCommandReceipt(
        command=command,
        command_sha256=command_sha256,
        process_id=process.pid,
        return_code=process.returncode,
        timed_out=timed_out,
        cleanup=cleanup,
        stdout_sha256=_digest(stdout),
        stderr_sha256=_digest(stderr),
        response_status=response_status,
        error_code=error_code,
        setup_state=setup_state,
        configured=configured,
    )


def _write_receipt(*, path: Path, receipt: InstalledCliProfileSetupReceipt) -> None:
    """Atomically write the sanitized receipt under the scenario-owned root."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _failed_receipt(
    *,
    executable_sha256: str,
    commands: list[InstalledCliCommandReceipt],
    stage: ProfileSetupCommandId | Literal["readiness_assertion"],
) -> InstalledCliProfileSetupReceipt:
    """Build one truthful terminal failure receipt."""
    return InstalledCliProfileSetupReceipt(
        schema_version=_SCHEMA_VERSION,
        status="failed",
        executable_sha256=executable_sha256,
        commands=tuple(commands),
        failure_stage=stage,
    )


def _command_failed(command: InstalledCliCommandReceipt) -> bool:
    """Classify every timeout, cleanup problem, and nonzero exit as failed."""
    return command.return_code != 0 or command.timed_out or command.cleanup == "failed"


def run_installed_cli_profile_setup(
    *,
    aeat_executable: Path,
    workspace_root: Path,
    storage_root: Path,
    receipt_path: Path,
    profile_label: str,
    passphrase: str,
    timeout_seconds: float = 90.0,
) -> InstalledCliProfileSetupReceipt:
    """Create, reopen, complete, and verify a synthetic profile through installed CLI commands."""
    if not aeat_executable.is_file():
        raise ValueError("installed CLI profile setup requires an existing aeat executable")
    if storage_root.exists() and any(storage_root.iterdir()):
        raise ValueError("installed CLI profile setup requires an empty scenario storage root")
    storage_root.mkdir(parents=True, exist_ok=True)
    executable_sha256 = hashlib.sha256(aeat_executable.read_bytes()).hexdigest()
    commands: list[InstalledCliCommandReceipt] = []
    creation_secrets = json.dumps(
        {"passphrase": passphrase, "passphrase_confirmation": passphrase}, separators=(",", ":")
    ).encode("utf-8")
    profile_secrets = json.dumps({"profile_passphrase": passphrase}, separators=(",", ":")).encode("utf-8")

    create = _run_command(
        command="profile_create",
        executable=aeat_executable,
        argv=(
            "--format",
            "json",
            "config",
            "profile",
            "create",
            profile_label,
            "--quiet",
            "--secrets-stdin",
            "--entity-type",
            "natural_person",
            "--tax-id",
            "12345678Z",
            "--name",
            "Assets",
            "--surnames",
            "Acceptance",
            "--fiscal-residency",
            "resident_irpf",
            "--tax-residence-jurisdiction-scope",
            "common_regime",
            "--tax-residence-ccaa",
            "madrid",
            "--irpf-income-categories",
            "actividad_economica",
            "--activity",
            "consultoria",
            "--irpf-estimation-regime",
            "directa_simplificada",
            "--iva-regime",
            "GENERAL",
            "--iva-m303-regime-composition",
            "general",
            "--no-iva-redeme-enrolled",
            "--no-iva-cash-accounting-regime-enrolled",
            "--no-iva-voluntary-sii-enrolled",
            "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
        ),
        stdin_payload=creation_secrets,
        workspace_root=workspace_root,
        storage_root=storage_root,
        timeout_seconds=timeout_seconds,
    )
    commands.append(create)
    if _command_failed(create):
        receipt = _failed_receipt(executable_sha256=executable_sha256, commands=commands, stage="profile_create")
        _write_receipt(path=receipt_path, receipt=receipt)
        raise InstalledCliProfileSetupError(receipt=receipt)

    login = _run_command(
        command="profile_login",
        executable=aeat_executable,
        argv=("--format", "json", "config", "login", profile_label, "--secrets-stdin"),
        stdin_payload=json.dumps({"passphrase": passphrase}, separators=(",", ":")).encode("utf-8"),
        workspace_root=workspace_root,
        storage_root=storage_root,
        timeout_seconds=timeout_seconds,
    )
    commands.append(login)
    if _command_failed(login):
        receipt = _failed_receipt(executable_sha256=executable_sha256, commands=commands, stage="profile_login")
        _write_receipt(path=receipt_path, receipt=receipt)
        raise InstalledCliProfileSetupError(receipt=receipt)

    complete_setup = _run_command(
        command="profile_complete_setup",
        executable=aeat_executable,
        argv=(
            "--format",
            "json",
            "--profile-secrets-stdin",
            "config",
            "profile",
            "complete-setup",
        ),
        stdin_payload=profile_secrets,
        workspace_root=workspace_root,
        storage_root=storage_root,
        timeout_seconds=timeout_seconds,
    )
    commands.append(complete_setup)
    if _command_failed(complete_setup):
        receipt = _failed_receipt(
            executable_sha256=executable_sha256,
            commands=commands,
            stage="profile_complete_setup",
        )
        _write_receipt(path=receipt_path, receipt=receipt)
        raise InstalledCliProfileSetupError(receipt=receipt)
    if complete_setup.setup_state != "complete":
        receipt = _failed_receipt(executable_sha256=executable_sha256, commands=commands, stage="readiness_assertion")
        _write_receipt(path=receipt_path, receipt=receipt)
        raise InstalledCliProfileSetupError(receipt=receipt)

    status = _run_command(
        command="profile_status",
        executable=aeat_executable,
        argv=("--format", "json", "--profile-secrets-stdin", "config", "profile", "status"),
        stdin_payload=profile_secrets,
        workspace_root=workspace_root,
        storage_root=storage_root,
        timeout_seconds=timeout_seconds,
    )
    commands.append(status)
    if _command_failed(status) or status.configured is not True:
        receipt = _failed_receipt(
            executable_sha256=executable_sha256,
            commands=commands,
            stage="profile_status" if _command_failed(status) else "readiness_assertion",
        )
        _write_receipt(path=receipt_path, receipt=receipt)
        raise InstalledCliProfileSetupError(receipt=receipt)

    receipt = InstalledCliProfileSetupReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        executable_sha256=executable_sha256,
        commands=tuple(commands),
        failure_stage=None,
    )
    _write_receipt(path=receipt_path, receipt=receipt)
    return receipt


__all__ = [
    "InstalledCliCommandReceipt",
    "InstalledCliProfileSetupError",
    "InstalledCliProfileSetupReceipt",
    "run_installed_cli_profile_setup",
]
