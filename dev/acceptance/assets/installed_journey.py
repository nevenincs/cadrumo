"""Supervise one ASSETS-01 installed-TUI child without false success on a hang."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

_SCHEMA_VERSION = "assets-01-installed-tui-supervisor-v2"
type InstalledAssetTuiJourney = Literal[
    "probe",
    "home",
    "profile",
    "profile_ready",
    "ledger",
    "asset_screen",
    "asset_method_lifecycle",
    "asset_readback",
    "asset_cli_readback",
]


@dataclass(frozen=True, slots=True)
class InstalledTuiProcessReceipt:
    """Sanitized result of supervising an owned installed-TUI child."""

    schema_version: str
    status: Literal["proven", "failed"]
    command_sha256: str
    process_id: int
    return_code: int | None
    last_stage: str | None
    timed_out: bool
    cleanup: Literal["not_needed", "terminated", "failed"]
    stdout_sha256: str
    stderr_sha256: str
    child_status: str | None
    required_stage_missing: str | None
    failure_class: str | None
    failure_identity: str | None

    def to_dict(self) -> dict[str, object]:
        """Return a receipt with no command arguments, secret, or raw output."""
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "command_sha256": self.command_sha256,
            "process_id": self.process_id,
            "return_code": self.return_code,
            "last_stage": self.last_stage,
            "timed_out": self.timed_out,
            "cleanup": self.cleanup,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "child_status": self.child_status,
            "required_stage_missing": self.required_stage_missing,
            "failure_class": self.failure_class,
            "failure_identity": self.failure_identity,
        }


class InstalledTuiProcessError(RuntimeError):
    """A child failed, exited incompletely, or required timeout cleanup."""

    def __init__(self, message: str, *, receipt: InstalledTuiProcessReceipt) -> None:
        """Retain the safe supervisor receipt as structured failure evidence."""
        super().__init__(message)
        self.receipt = receipt


def build_assets_installed_environment(*, storage_root: Path) -> dict[str, str]:
    """Keep host launch prerequisites but remove ambient product configuration."""
    environment = {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}
    # The harness module is found from its working directory.  A source-tree
    # Python path or another virtual-environment marker would invalidate the
    # installed-product origin assertion before the journey even starts.
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment.pop("VIRTUAL_ENV", None)
    environment["CADRUMO_LOCAL_STORAGE_ROOT"] = str(storage_root)
    environment["CADRUMO_OUTPUT_LANGUAGE"] = "en"
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def read_receipt_progress(path: Path) -> tuple[str | None, str | None, tuple[str, ...]]:
    """Read only the controlled progress fields from a child receipt.

    The child rewrites its receipt while the supervisor polls it, and Windows
    refuses a read that meets that write with a sharing violation.  An
    unreadable receipt is therefore "no progress yet"; the terminal status is
    still taken from the read after the child exits, and a receipt that stays
    unreadable leaves the run failed.
    """
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None, ()
    if not isinstance(raw, dict):
        return None, None, ()
    payload = cast("dict[str, object]", raw)
    stage = payload.get("stage")
    status = payload.get("status")
    raw_stages = payload.get("completed_stages")
    stages = tuple(item for item in raw_stages if isinstance(item, str)) if isinstance(raw_stages, list) else ()
    return (stage if isinstance(stage, str) else None, status if isinstance(status, str) else None, stages)


def required_installed_tui_stages(
    *,
    journey: InstalledAssetTuiJourney,
    profile_bootstrap: Literal["register", "existing"],
) -> tuple[str, ...]:
    """Return the non-negotiable public stages for one declared journey.

    A clean launcher exit is not evidence that its injected autopilot ever ran.
    The supervisor checks this same contract independently from the child so a
    future child regression cannot turn early launcher completion into proof.
    """
    required = ["installed_origin"]
    if profile_bootstrap == "register":
        required.append("registration")
    else:
        required.extend(("existing_profile", "session_admitted"))
    required.append("launcher_autopilot")
    if journey in {
        "home",
        "profile",
        "profile_ready",
        "ledger",
        "asset_screen",
        "asset_method_lifecycle",
        "asset_readback",
        "asset_cli_readback",
    }:
        required.append("home_ready")
    if journey in {"profile", "profile_ready"}:
        required.append("profile_ready")
    if journey == "profile_ready":
        required.append("profile_completed")
    if journey in {"ledger", "asset_screen", "asset_method_lifecycle", "asset_readback", "asset_cli_readback"}:
        required.append("ledger_ready")
    if journey in {"asset_screen", "asset_method_lifecycle", "asset_readback", "asset_cli_readback"}:
        required.append("asset_screen_ready")
    if journey == "asset_method_lifecycle":
        required.extend(
            (
                "asset_created",
                "asset_inspected",
                "asset_corrected",
                "asset_forecast",
                "asset_claim",
                "asset_claim_replay",
                "asset_filing_handoff",
            )
        )
    if journey == "asset_readback":
        required.append("asset_readback")
    if journey == "asset_cli_readback":
        required.append("asset_cli_readback")
    required.append("launcher_exit")
    return tuple(required)


def _first_missing_required_stage(
    completed_stages: tuple[str, ...],
    *,
    journey: InstalledAssetTuiJourney,
    profile_bootstrap: Literal["register", "existing"],
) -> str | None:
    """Identify the first required stage absent from a terminal receipt."""
    completed = set(completed_stages)
    return next(
        (
            stage
            for stage in required_installed_tui_stages(
                journey=journey,
                profile_bootstrap=profile_bootstrap,
            )
            if stage not in completed
        ),
        None,
    )


def _digest(output: bytes | None) -> str:
    """Summarize child streams without putting their contents in a receipt."""
    return hashlib.sha256(output or b"").hexdigest()


def _failure_class(stderr: bytes | None) -> str | None:
    """Classify a Python failure without retaining its potentially private text."""
    if not stderr:
        return None
    text = stderr.decode("utf-8", errors="replace")
    for name in (
        "ModuleNotFoundError",
        "ImportError",
        "SyntaxError",
        "TypeError",
        "AttributeError",
        "RuntimeError",
        "ValueError",
        "AssertionError",
        "FileNotFoundError",
        "PermissionError",
    ):
        if f"{name}:" in text:
            return name
    return "unclassified_child_stderr"


def _failure_identity(stderr: bytes | None) -> str | None:
    """Return one redacted terminal diagnostic line for runner triage only."""
    if not stderr:
        return None
    lines = [line.strip() for line in stderr.decode("utf-8", errors="replace").splitlines() if line.strip()]
    if not lines:
        return "unclassified_empty_stderr"
    identity = lines[-1]
    identity = re.sub(r"[A-Za-z]:\\[^\s]+", "<path>", identity)
    identity = re.sub(r"(['\"]).*?\1", "<redacted>", identity)
    identity = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}", "<id>", identity)
    return identity[:240]


def run_installed_tui_probe(
    *,
    python_executable: Path,
    workspace_root: Path,
    storage_root: Path,
    receipt_path: Path,
    profile_label: str,
    passphrase: str,
    journey: InstalledAssetTuiJourney = "probe",
    profile_bootstrap: Literal["register", "existing"] = "register",
    timeout_seconds: float = 75.0,
    child_module: str = "dev.acceptance.assets.installed_tui_child",
) -> InstalledTuiProcessReceipt:
    """Run the assets installed-TUI probe and clean up only its identified child.

    The caller owns ``storage_root`` and must provide a fresh, empty directory.
    A timeout is an explicit failed result; termination merely prevents an
    orphaned Textual process from contaminating subsequent acceptance runs.
    """
    if not python_executable.is_file():
        raise ValueError("installed TUI probe requires an existing Python executable")
    if profile_bootstrap == "register":
        if storage_root.exists() and any(storage_root.iterdir()):
            raise ValueError("installed TUI registration probe requires an empty scenario storage root")
        storage_root.mkdir(parents=True, exist_ok=True)
    elif not storage_root.is_dir() or not any(storage_root.iterdir()):
        raise ValueError("installed TUI existing-profile probe requires a populated scenario storage root")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    argv = (
        str(python_executable.resolve()),
        "-X",
        "utf8",
        "-u",
        "-m",
        child_module,
        "--workspace-root",
        str(workspace_root.resolve()),
        "--receipt",
        str(receipt_path.resolve()),
        "--profile-label",
        profile_label,
        "--journey",
        journey,
        "--profile-bootstrap",
        profile_bootstrap,
    )
    command_sha = hashlib.sha256("\0".join(argv).encode("utf-8")).hexdigest()
    process = subprocess.Popen(  # noqa: S603 - argv is fixed by this scenario-owned supervisor
        argv,
        cwd=workspace_root,
        env=build_assets_installed_environment(storage_root=storage_root),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    stdin = process.stdin
    if stdin is None:
        process.terminate()
        process.wait(timeout=10.0)
        raise RuntimeError("installed TUI child did not expose its required stdin channel")
    stdin.write(json.dumps({"profile_passphrase": passphrase}).encode("utf-8"))
    stdin.close()
    last_stage: str | None = None
    child_status: str | None = None
    completed_stages: tuple[str, ...] = ()
    timed_out = False
    cleanup: Literal["not_needed", "terminated", "failed"] = "not_needed"
    deadline = time.monotonic() + timeout_seconds
    while process.poll() is None and time.monotonic() < deadline:
        last_stage, child_status, completed_stages = read_receipt_progress(receipt_path)
        time.sleep(0.1)
    if process.poll() is None:
        timed_out = True
        last_stage, child_status, completed_stages = read_receipt_progress(receipt_path)
        try:
            process.terminate()
            process.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                cleanup = "failed"
            else:
                cleanup = "terminated"
        else:
            cleanup = "terminated"
    stdout, stderr = process.communicate(timeout=10.0)
    last_stage, child_status, completed_stages = read_receipt_progress(receipt_path)
    required_stage_missing = _first_missing_required_stage(
        completed_stages,
        journey=journey,
        profile_bootstrap=profile_bootstrap,
    )
    failure_identity = (
        f"missing_required_stage:{required_stage_missing}"
        if process.returncode == 0 and child_status == "proven" and required_stage_missing is not None
        else _failure_identity(stderr)
    )
    receipt = InstalledTuiProcessReceipt(
        schema_version=_SCHEMA_VERSION,
        status=(
            "proven"
            if process.returncode == 0 and child_status == "proven" and required_stage_missing is None and not timed_out
            else "failed"
        ),
        command_sha256=command_sha,
        process_id=process.pid,
        return_code=process.returncode,
        last_stage=last_stage,
        timed_out=timed_out,
        cleanup=cleanup,
        stdout_sha256=_digest(stdout),
        stderr_sha256=_digest(stderr),
        child_status=child_status,
        required_stage_missing=required_stage_missing,
        failure_class=_failure_class(stderr),
        failure_identity=failure_identity,
    )
    receipt_path.with_name("supervisor-receipt.json").write_text(
        json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if receipt.status != "proven":
        raise InstalledTuiProcessError(
            "installed assets TUI child did not complete successfully",
            receipt=receipt,
        )
    return receipt


def _read_passphrase_from_stdin() -> str:
    """Receive the synthetic profile credential without placing it in argv."""
    try:
        raw: object = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise ValueError("installed TUI supervisor requires one credential JSON object on stdin") from exc
    payload = cast("dict[str, object]", raw) if isinstance(raw, dict) else None
    passphrase = payload.get("profile_passphrase") if payload is not None else None
    if not isinstance(passphrase, str) or not passphrase:
        raise ValueError("installed TUI supervisor credential JSON lacks profile_passphrase")
    return passphrase


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Supervise a staged ASSETS-01 installed-TUI probe.")
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--storage-root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--profile-label", required=True)
    parser.add_argument(
        "--journey",
        choices=(
            "probe",
            "home",
            "profile",
            "profile_ready",
            "ledger",
            "asset_screen",
            "asset_method_lifecycle",
            "asset_readback",
            "asset_cli_readback",
        ),
        default="probe",
    )
    parser.add_argument("--profile-bootstrap", choices=("register", "existing"), default="register")
    parser.add_argument("--timeout-seconds", default=75.0, type=float)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the supervisor as a sanitized command-line acceptance boundary."""
    args = _parser().parse_args(argv)
    try:
        receipt = run_installed_tui_probe(
            python_executable=args.python,
            workspace_root=args.workspace_root,
            storage_root=args.storage_root,
            receipt_path=args.receipt,
            profile_label=args.profile_label,
            passphrase=_read_passphrase_from_stdin(),
            journey=args.journey,
            profile_bootstrap=args.profile_bootstrap,
            timeout_seconds=args.timeout_seconds,
        )
    except (InstalledTuiProcessError, ValueError) as exc:
        if isinstance(exc, InstalledTuiProcessError):
            print(json.dumps(exc.receipt.to_dict(), sort_keys=True))
        else:
            print(json.dumps({"status": "failed", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(receipt.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - executable module boundary
    raise SystemExit(main())


__all__ = [
    "InstalledTuiProcessError",
    "InstalledTuiProcessReceipt",
    "build_assets_installed_environment",
    "main",
    "read_receipt_progress",
    "required_installed_tui_stages",
    "run_installed_tui_probe",
]
