"""Verify a fresh uv-managed development environment from the frozen lock."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .smoke_core import (
    _assert_installed_data,
    _executable,
    _manifest_path,
    _run,
    _venv_aeat,
    _venv_bin,
    _venv_python,
    _work_dir,
    _write_smoke_manifest,
)

_DEV_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("ruff", "--version"),
    ("pytest", "--version"),
    ("ty", "--version"),
    ("pyright", "--version"),
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
    return str(_venv_bin(venv) / f"{command}{suffix}")


def _sync_dev_environment(repo_root: Path, work_dir: Path, uv: str, python: str) -> Path:
    """Create a clean non-editable dev environment using the frozen lock."""
    venv = work_dir / "dev-venv"
    env = {
        **os.environ,
        "UV_PROJECT_ENVIRONMENT": str(venv),
    }
    _run(
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
    _run(
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
    _run([uv, "pip", "check", "--python", str(_venv_python(venv))], cwd=repo_root)
    return venv


def _assert_dev_commands(work_dir: Path, venv: Path) -> None:
    """Verify the declared developer command surface starts in the clean venv."""
    for command in _DEV_COMMANDS:
        executable, *args = command
        _run([_venv_script(venv, executable), *args], cwd=work_dir)


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
    _run([str(_venv_python(venv)), "-c", code], cwd=work_dir)


def _assert_dev_cli(work_dir: Path, venv: Path) -> None:
    """Verify the non-editable project install exposes the AEAT console script."""
    version = _run([str(_venv_aeat(venv)), "--version"], cwd=work_dir)
    if "aeat " not in version.stdout:
        raise SystemExit(f"unexpected aeat --version output in dev venv: {version.stdout!r}")


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

    repo_root = Path(__file__).resolve().parents[2]
    uv = _executable("uv")
    work_dir = _work_dir(repo_root, args.work_dir, prefix="dev")
    print(f"dev packaging smoke work dir: {work_dir}", flush=True)

    print("syncing frozen all-extras/all-groups development environment", flush=True)
    venv = _sync_dev_environment(repo_root, work_dir, uv, args.python)

    print("verifying developer command surface", flush=True)
    _assert_dev_commands(work_dir, venv)
    _assert_dev_imports(work_dir, venv)
    _assert_dev_cli(work_dir, venv)
    _assert_installed_data(work_dir, venv)

    manifest = _write_smoke_manifest(
        work_dir,
        lane="dev-environment",
        artifacts={"venv": _manifest_path(work_dir, venv)},
        checks=(
            "frozen uv all-extras/all-groups sync",
            "non-editable project install",
            "uv sync check",
            "pip check",
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
