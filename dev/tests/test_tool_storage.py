"""Development tool locations stay apart from the product's one storage root."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cadrumo.core.config import Settings
from cadrumo.core.storage_environment import STORAGE_ROOT
from cadrumo.tests.env_scope import isolated_aeat_env
from dev.tool_storage import TOOL_STORAGE_LOCATIONS, storage_directory, tool_storage_environment

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_a_relative_tool_location_resolves_beneath_the_storage_root(tmp_path: Path) -> None:
    root = tmp_path / "relocated"
    with isolated_aeat_env(CADRUMO_STORAGE_ROOT=str(root), CADRUMO_DEV_CACHE_ROOT=""):
        assert storage_directory("CADRUMO_DEV_CACHE_ROOT", "development/cache") == root / "development" / "cache"


def test_location_settings_are_separate_from_development_tools() -> None:
    product = Settings.storage_env_var_names()
    development = frozenset(variable for variable, _default in TOOL_STORAGE_LOCATIONS.values())
    assert product == {STORAGE_ROOT.variable}
    assert "CADRUMO_TOOL_CACHE_DIR" in development
    assert not product & development
    assert not {"XDG_CACHE_HOME", "UV_CACHE_DIR"} & (product | development)
    assert not any(name.startswith("CADRUMO_UV_") for name in development)
    assert not {"UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR", "UV_TOOL_DIR", "UV_TOOL_BIN_DIR"} & set(TOOL_STORAGE_LOCATIONS)


def test_uv_global_paths_remain_owned_by_the_machine_and_uv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    machine_paths = {
        "UV_CACHE_DIR": str(tmp_path / "machine-cache"),
        "UV_PYTHON_INSTALL_DIR": str(tmp_path / "machine-python"),
        "UV_TOOL_DIR": str(tmp_path / "machine-tools"),
        "UV_TOOL_BIN_DIR": str(tmp_path / "machine-tool-bin"),
    }
    retired_controls = {
        "CADRUMO_UV_CACHE_DIR": str(tmp_path / "retired-cache"),
        "CADRUMO_UV_PYTHON_DIR": str(tmp_path / "retired-python"),
        "CADRUMO_UV_TOOL_DIR": str(tmp_path / "retired-tools"),
        "CADRUMO_UV_TOOL_BIN_DIR": str(tmp_path / "retired-tool-bin"),
    }
    for name, value in {**machine_paths, **retired_controls}.items():
        monkeypatch.setenv(name, value)

    managed = tool_storage_environment()
    child = {**os.environ, **managed}
    for name in retired_controls:
        monkeypatch.delenv(name)
    without_retired_controls = tool_storage_environment()

    assert not set(machine_paths) & managed.keys()
    assert {name: child[name] for name in machine_paths} == machine_paths
    assert managed == without_retired_controls
    assert not set(retired_controls) & {variable for variable, _default in TOOL_STORAGE_LOCATIONS.values()}
