"""Verify a fresh uv-managed development environment from the frozen lock."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .._paths import REPO_ROOT
from ._smoke_common import (
    assert_cadrumo_version_output,
    assert_installed_data,
    record_proof,
    relative_manifest_path,
    require_executable,
    resolve_work_dir,
    run_checked,
    venv_bin_dir,
    venv_cadrumo_path,
    venv_python_path,
    write_smoke_manifest,
)

_DEV_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("ruff", "--version"),
    ("pytest", "--version"),
    ("ty", "--version"),
    ("pyrefly", "--version"),
    ("lint-imports", "--version"),
    ("deptry", "--version"),
    ("vulture", "--version"),
    ("radon", "--version"),
    ("complexipy", "--help"),
    ("vaultspec-core", "--version"),
    ("vaultspec-rag", "--version"),
)


def _venv_script(venv: Path, command: str) -> str:
    """Return a console script from the isolated development environment."""
    suffix = ".exe" if os.name == "nt" else ""
    return str(venv_bin_dir(venv) / f"{command}{suffix}")


def _sync_dev_environment(repo_root: Path, work_dir: Path, uv: str, python: str) -> Path:
    """Create a clean non-editable dev environment using the frozen lock."""
    venv = work_dir / "dev-venv"
    env = {
        **os.environ,
        "UV_PROJECT_ENVIRONMENT": str(venv),
    }
    run_checked(
        [
            uv,
            "sync",
            "--frozen",
            "--all-extras",
            "--all-groups",
            "--no-editable",
            "--python",
            python,
        ],
        cwd=repo_root,
        env=env,
    )
    run_checked(
        [
            uv,
            "sync",
            "--frozen",
            "--all-extras",
            "--all-groups",
            "--no-editable",
            "--check",
            "--python",
            python,
        ],
        cwd=repo_root,
        env=env,
    )
    run_checked([uv, "pip", "check", "--python", str(venv_python_path(venv))], cwd=repo_root)
    return venv
    record_proof("frozen uv all-extras/all-groups sync")
    record_proof("non-editable project install")
    record_proof("uv sync check")
    record_proof("pip dependency check")


def _assert_dev_commands(work_dir: Path, venv: Path) -> None:
    """Verify the declared developer command surface starts in the clean venv.

    The proof is recorded only once a command has actually run. Recorded
    unconditionally after the loop, an emptied command list would have
    satisfied the manifest proof contract having started nothing - and that
    contract exists precisely to stop a claim appearing without its assertion.
    """
    if not _DEV_COMMANDS:
        raise SystemExit("the developer command surface is empty; this lane would prove nothing")
    for command in _DEV_COMMANDS:
        executable, *args = command
        run_checked([_venv_script(venv, executable), *args], cwd=work_dir)
    record_proof("developer command surface")


def _assert_dev_imports(work_dir: Path, venv: Path) -> None:
    """Verify heavyweight dev, optional, and runtime packages import together."""
    code = """
import anthropic
import googleapiclient.discovery
import playwright.async_api
import pytest
import torch
import yaml

print("dev-imports-ok")
"""
    run_checked([str(venv_python_path(venv)), "-c", code], cwd=work_dir)
    record_proof("dev optional runtime imports")


def _assert_dev_cli(work_dir: Path, venv: Path) -> None:
    """Verify the non-editable project install exposes the AEAT console script."""
    version = run_checked([str(venv_cadrumo_path(venv)), "--version"], cwd=work_dir)
    assert_cadrumo_version_output(version, context="in dev venv")
    record_proof("installed CLI version smoke")


def main(argv: list[str] | None = None) -> int:
    """Run the fresh development-environment packaging smoke gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python",
        default=f"{sys.version_info.major}.{sys.version_info.minor}",
        help="Expected Python major.minor for the isolated uv project environment.",
    )
    parser.add_argument("--work-dir", help="Empty directory for the isolated development environment.")
    args = parser.parse_args(argv)

    repo_root = REPO_ROOT
    uv = require_executable("uv")
    work_dir = resolve_work_dir(repo_root, args.work_dir, prefix="dev")
    print(f"dev packaging smoke work dir: {work_dir}", flush=True)

    print("syncing frozen all-extras/all-groups development environment", flush=True)
    venv = _sync_dev_environment(repo_root, work_dir, uv, args.python)

    print("verifying developer command surface", flush=True)
    _assert_dev_commands(work_dir, venv)
    _assert_dev_imports(work_dir, venv)
    _assert_dev_cli(work_dir, venv)
    assert_installed_data(work_dir, venv)

    manifest = write_smoke_manifest(
        work_dir,
        lane="dev-environment",
        artifacts={"venv": relative_manifest_path(work_dir, venv)},
        declared=(
            "frozen uv all-extras/all-groups sync",
            "non-editable project install",
            "uv sync check",
            "pip dependency check",
            "developer command surface",
            "dev optional runtime imports",
            "installed CLI version smoke",
            "installed bundled data resources",
        ),
        details={"python": args.python},
    )

    print(f"dev packaging smoke passed: {venv}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
