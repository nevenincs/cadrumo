"""The desktop's Python fallback prepares the canonical operator workspace."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from cadrumo.core.config import Settings
from cadrumo.core.storage_environment import STORAGE_ROOT
from dev._paths import REPO_ROOT

from ...command_execution import CommandResult, run_command

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _project(root: Path) -> CommandResult:
    environment = {
        key: value for key, value in os.environ.items() if key.upper() not in Settings.storage_env_var_names()
    }
    environment[STORAGE_ROOT.variable] = str(root)
    return run_command(
        [sys.executable, str(REPO_ROOT / "native/desktop/src-tauri/src/python/environment.py")],
        cwd=REPO_ROOT,
        environment=environment,
        timeout_seconds=None,
    )


def test_projection_creates_workspace_and_keeps_absolute_storage_pin(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    result = _project(root)
    assert result.returncode == 0, result.stderr
    projected = json.loads(result.stdout)
    assert Path(projected["console_workspace"]) == root / "workspace"
    assert (root / "workspace").is_dir()
    assert Path(projected["environment"][STORAGE_ROOT.variable]) == root
    (root / "workspace" / "operator.txt").write_text("synthetic operator file")
    assert _project(root).returncode == 0
    assert (root / "workspace" / "operator.txt").read_text() == "synthetic operator file"


def test_projection_refuses_workspace_file(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    root.mkdir()
    (root / "workspace").write_text("synthetic non-directory")
    assert _project(root).returncode != 0


def test_projection_refuses_linked_workspace(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    root.mkdir()
    destination = tmp_path / "elsewhere"
    destination.mkdir()
    try:
        (root / "workspace").symlink_to(destination, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation unavailable")
    assert _project(root).returncode != 0
    assert not list(destination.iterdir())
