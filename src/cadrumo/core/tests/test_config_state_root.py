"""Tests for storage state-root resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ...tests.env_scope import isolated_aeat_env, settings_without_env_file
from ..config_state_root import StateRootInputs, platform_user_data_root
from ..errors.hierarchy import CoreValidationError
from ..paths import resolve_project_path
from ..product_identity import PRODUCT_IDENTITY
from ..storage_taxonomy import StorageCategory
from ..storage_taxonomy_locations import storage_path
from .state_root_projection import resolve_state_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _inputs(base: Path, **environ: str) -> StateRootInputs:
    """Inputs for this host whose per-user base directory is ``base``."""
    variable = {"win32": "LOCALAPPDATA", "darwin": "HOME"}.get(sys.platform, "XDG_DATA_HOME")
    return StateRootInputs(platform=sys.platform, environ={variable: str(base), **environ}, home=base)


def _default(base: Path) -> Path:
    if sys.platform == "darwin":
        return (base / "Library" / "Application Support" / PRODUCT_IDENTITY.python_package).resolve()
    return (base / PRODUCT_IDENTITY.python_package).resolve()


def test_storage_root_derives_every_substrate_dir(tmp_path: Path) -> None:
    """Every substrate remains beneath the selected root."""
    resolution = resolve_state_root(_inputs(tmp_path))

    with isolated_aeat_env():
        settings = settings_without_env_file(cadrumo_storage_root=resolution.storage_root)

    root = settings.cadrumo_storage_root
    substrate = (
        StorageCategory.TOKENS,
        StorageCategory.LOGS,
        StorageCategory.SECRETS,
        StorageCategory.BLOBS,
        StorageCategory.LIVE_STATE,
    )
    resolved = {category: storage_path(category, settings=settings) for category in substrate}

    # Five distinct locations, so the loop below cannot pass by comparing one
    # value against itself five times.
    assert len(set(resolved.values())) == len(substrate), resolved

    for category, derived in resolved.items():
        assert root in derived.parents, category


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_every_platform_defaults_to_its_per_user_directory(tmp_path: Path, platform: str) -> None:
    """The declared per-user base of each platform selects the default root."""
    variable = {"win32": "LOCALAPPDATA", "linux": "XDG_DATA_HOME", "darwin": "HOME"}[platform]
    inputs = StateRootInputs(platform=platform, environ={variable: str(tmp_path / "user")}, home=tmp_path / "home")
    root = resolve_state_root(inputs).storage_root
    expected_parts = {
        "darwin": ("user", "Library", "Application Support", "cadrumo"),
        "win32": ("user", "cadrumo"),
        "linux": ("user", "cadrumo"),
    }[platform]
    assert root.parts[-len(expected_parts) :] == expected_parts


def test_the_root_never_depends_on_the_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = _inputs(tmp_path / "user-data")
    before = resolve_state_root(inputs).storage_root
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()
    (cwd / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    monkeypatch.chdir(cwd)
    assert resolve_state_root(inputs).storage_root == before == _default(tmp_path / "user-data")


def test_relative_paths_anchor_at_the_resolved_storage_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    inputs = _inputs(tmp_path / "user-data")
    assert platform_user_data_root(inputs) == _default(tmp_path / "user-data")
    assert resolve_project_path("certs/x.p12", state_root_inputs=inputs) == (
        _default(tmp_path / "user-data") / "certs" / "x.p12"
    )


def test_an_absolute_override_selects_the_root_and_the_relative_anchor(tmp_path: Path) -> None:
    explicit = tmp_path / "operator"
    inputs = _inputs(tmp_path / "user-data", CADRUMO_STORAGE_ROOT=str(explicit))
    assert resolve_state_root(inputs).storage_root == explicit.resolve()
    assert platform_user_data_root(inputs) == explicit.resolve()


def test_a_relative_root_and_a_missing_base_are_refused(tmp_path: Path) -> None:
    with pytest.raises(CoreValidationError, match="must be an absolute directory"):
        resolve_state_root(_inputs(tmp_path, CADRUMO_STORAGE_ROOT="var/storage"))
    missing = StateRootInputs(platform=sys.platform, environ={}, home=tmp_path)
    with pytest.raises(CoreValidationError, match="per-user data directory"):
        resolve_state_root(missing)


def test_fresh_cadrumo_state_is_resolved_and_reused(tmp_path: Path) -> None:
    """A fresh root remains the sole Cadrumo state root after a write."""
    inputs = _inputs(tmp_path)
    first = resolve_state_root(inputs)
    first.storage_root.mkdir(parents=True)
    marker = first.storage_root / "fresh-state.marker"
    marker.write_text("cadrumo", encoding="utf-8")

    second = resolve_state_root(inputs)
    assert second.storage_root == first.storage_root
    assert marker.read_text(encoding="utf-8") == "cadrumo"
    assert not (tmp_path / "aeat").exists()


def test_settings_tree_follows_the_explicit_storage_root(tmp_path: Path) -> None:
    """A fresh Settings tree follows the explicit storage root."""
    resolution = resolve_state_root(_inputs(tmp_path))
    with isolated_aeat_env():
        settings = settings_without_env_file(cadrumo_storage_root=resolution.storage_root)

    for category in (
        StorageCategory.TOKENS,
        StorageCategory.LOGS,
        StorageCategory.SECRETS,
        StorageCategory.BLOBS,
        StorageCategory.LIVE_STATE,
    ):
        assert resolution.storage_root in storage_path(category, settings=settings).parents, category
