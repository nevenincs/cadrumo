"""Tool bootstrap and Python resolution obey the same storage overrides."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from cadrumo.core.storage_environment import TOOL_STORAGE_LOCATIONS, tool_storage_environment
from dev._paths import REPO_ROOT
from dev.docs.build_paths import DOCS_BUILD_ROOT_ENV, docs_build_root
from dev.packaging.command_execution import run_command

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


@pytest.mark.parametrize("member", ["", "relative-cache", "absolute-cache"])
def test_just_tool_paths_match_the_canonical_resolver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, member: str
) -> None:
    executable = shutil.which("just")
    assert executable is not None, "the repository task runner is required"
    monkeypatch.setenv("CADRUMO_STORAGE_ROOT", str(tmp_path / "shared storage"))
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", "")
    controls = (*tuple(variable for variable, _default in TOOL_STORAGE_LOCATIONS.values()), DOCS_BUILD_ROOT_ENV)
    override = str(tmp_path / member) if member == "absolute-cache" else member
    for name in controls:
        monkeypatch.setenv(name, override)
    for name, expected in tool_storage_environment().items():
        monkeypatch.setenv(name, str(tmp_path / "ambient tool storage"))
        completed = run_command(
            [executable, "--justfile", str(REPO_ROOT / "justfile"), "--evaluate", name],
            cwd=REPO_ROOT,
            environment=dict(os.environ),
            timeout_seconds=30,
        )
        assert completed.returncode == 0, completed.stderr
        assert Path(completed.stdout.strip()).resolve() == Path(expected)
    completed = run_command(
        [executable, "--justfile", str(REPO_ROOT / "justfile"), "--evaluate", DOCS_BUILD_ROOT_ENV],
        cwd=REPO_ROOT,
        environment=dict(os.environ),
        timeout_seconds=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert Path(completed.stdout.strip()).resolve() == docs_build_root()


@pytest.mark.parametrize("member", ["", "relative-data", "absolute-data"])
def test_native_builder_environment_is_a_member_of_the_tool_data_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, member: str
) -> None:
    """The release builder moves with the declared tool data location and is never the project environment."""
    executable = shutil.which("just")
    assert executable is not None, "the repository task runner is required"
    monkeypatch.setenv("CADRUMO_STORAGE_ROOT", str(tmp_path / "shared storage"))
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", "")
    control, _default = TOOL_STORAGE_LOCATIONS["XDG_DATA_HOME"]
    monkeypatch.setenv(control, str(tmp_path / member) if member == "absolute-data" else member)
    data_home = Path(tool_storage_environment()["XDG_DATA_HOME"])
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "ambient tool storage"))
    evaluated: dict[str, str] = {}
    for name in ("native_builder_environment", "native_builder_python"):
        completed = run_command(
            [executable, "--justfile", str(REPO_ROOT / "justfile"), "--evaluate", name],
            cwd=REPO_ROOT,
            environment=dict(os.environ),
            timeout_seconds=30,
        )
        assert completed.returncode == 0, completed.stderr
        evaluated[name] = completed.stdout.strip()
    environment = Path(evaluated["native_builder_environment"]).resolve()
    assert environment.parent == data_home
    assert not environment.is_relative_to(REPO_ROOT / ".venv")
    # CMake stores a program it found with forward slashes; the handed-over path keeps that one spelling.
    assert "\\" not in evaluated["native_builder_python"]
    assert Path(evaluated["native_builder_python"]).resolve().is_relative_to(environment)
