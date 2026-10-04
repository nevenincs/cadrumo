"""Tests for repository-backed storage state-root resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ...tests.env_scope import isolated_aeat_env, settings_without_env_file
from ..config_state_root import (
    StateRootInputs,
    live_state_root_inputs,
    resolve_state_root,
)
from ..errors.hierarchy import CoreValidationError
from ..paths import resolve_project_path
from ..product_identity import PRODUCT_IDENTITY
from ..storage_environment import StorageMode
from ..storage_environment import project_root as authored_project_root
from ..storage_taxonomy import StorageCategory
from ..storage_taxonomy_locations import storage_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _state_root_inputs_under(base: Path, *, platform: str = "win32") -> StateRootInputs:
    """Build deterministic state-root inputs whose platform base is ``base``."""
    if platform == "win32":
        environ = {"LOCALAPPDATA": str(base)}
    elif platform == "linux":
        environ = {"XDG_DATA_HOME": str(base)}
    else:
        environ = {}
    return StateRootInputs(platform=platform, environ=environ, home=base / "home", repository_root=base)


def test_storage_root_derives_every_substrate_dir(tmp_path: Path) -> None:
    """Every derived substrate remains beneath the selected root."""
    resolution = resolve_state_root(_state_root_inputs_under(tmp_path))

    with isolated_aeat_env():
        settings = settings_without_env_file(cadrumo_local_storage_root=resolution.storage_root)

    root = settings.cadrumo_local_storage_root
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


def test_explicit_substrate_override_still_wins(tmp_path: Path) -> None:
    """An explicit substrate directory kwarg overrides the derived path.

    Measured against a control built from the same root *without* the
    override, so "the override won" is a comparison between two resolutions
    rather than the accessor agreeing with itself. The control is what keeps
    the first assertion from going vacuous: it proves the chosen override
    target is not simply where derivation would have put the directory anyway.

    Where the derived location lands is deliberately not restated here. That
    is :mod:`test_output_dir_state_root`'s subject, which owns the hand-written
    ``DERIVED_OUTPUT_SUBPATHS`` oracle and pins it against the declaration in
    both directions. Restating a subpath here would be a third copy of a name
    that already has one authority and one oracle.
    """
    resolution = resolve_state_root(_state_root_inputs_under(tmp_path))
    explicit_secret_dir = tmp_path / "operator-secrets"

    with isolated_aeat_env():
        derived = settings_without_env_file(cadrumo_local_storage_root=resolution.storage_root)
        overridden = settings_without_env_file(
            cadrumo_local_storage_root=resolution.storage_root,
            cadrumo_secret_store_dir=explicit_secret_dir,
        )

    assert storage_path(StorageCategory.SECRETS, settings=overridden) == explicit_secret_dir
    assert storage_path(StorageCategory.SECRETS, settings=derived) != explicit_secret_dir
    # Overriding one substrate directory must not disturb a sibling that is
    # still deriving. Two independently built Settings, so this compares a
    # resolution against a resolution rather than a value against itself.
    assert storage_path(StorageCategory.BLOBS, settings=overridden) == storage_path(
        StorageCategory.BLOBS,
        settings=derived,
    )


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_every_platform_defaults_to_the_project(tmp_path: Path, platform: str) -> None:
    """Ambient operating-system data directories cannot select the storage default."""
    inputs = _state_root_inputs_under(tmp_path / "project", platform=platform)
    resolution = resolve_state_root(inputs)
    assert resolution.platform_user_data_root == tmp_path / "project"
    assert resolution.storage_root == tmp_path / "project" / "var" / "storage"


def test_unspecified_project_anchor_uses_the_authored_checkout(tmp_path: Path) -> None:
    inputs = StateRootInputs(platform="win32", environ={"LOCALAPPDATA": str(tmp_path)}, home=tmp_path)
    assert resolve_state_root(inputs).storage_root == authored_project_root() / "var" / "storage"
    assert live_state_root_inputs().repository_root == authored_project_root()


def test_relative_root_override_uses_the_project_anchor(tmp_path: Path) -> None:
    inputs = StateRootInputs(
        platform="linux", environ={"CADRUMO_STORAGE_ROOT": "custom"}, home=tmp_path, repository_root=tmp_path
    )
    assert resolve_state_root(inputs).storage_root == tmp_path / "custom"


def _installed_inputs(base: Path, **environ: str) -> StateRootInputs:
    """Installed-mode inputs for this host whose per-user base is ``base``."""
    variable = {"win32": "LOCALAPPDATA", "darwin": "HOME"}.get(sys.platform, "XDG_DATA_HOME")
    return StateRootInputs(
        platform=sys.platform,
        environ={variable: str(base), **environ},
        home=base,
        mode=StorageMode.INSTALLED,
    )


def _installed_default(base: Path) -> Path:
    if sys.platform == "darwin":
        return (base / "Library" / "Application Support" / PRODUCT_IDENTITY.python_package).resolve()
    return (base / PRODUCT_IDENTITY.python_package).resolve()


def test_installed_inputs_anchor_at_the_per_user_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    resolution = resolve_state_root(_installed_inputs(tmp_path / "user-data"))
    assert resolution.platform_user_data_root == _installed_default(tmp_path / "user-data")
    assert resolution.storage_root == _installed_default(tmp_path / "user-data")
    assert resolve_project_path("certs/x.p12", state_root_inputs=_installed_inputs(tmp_path / "user-data")) == (
        _installed_default(tmp_path / "user-data") / "certs" / "x.p12"
    )


def test_installed_inputs_refuse_a_relative_root_and_a_missing_base(tmp_path: Path) -> None:
    with pytest.raises(CoreValidationError, match="must be an absolute directory"):
        resolve_state_root(_installed_inputs(tmp_path, CADRUMO_LOCAL_STORAGE_ROOT="var/storage"))
    missing = StateRootInputs(platform=sys.platform, environ={}, home=tmp_path, mode=StorageMode.INSTALLED)
    with pytest.raises(CoreValidationError, match="per-user data directory"):
        resolve_state_root(missing)


def test_installed_inputs_keep_an_absolute_override(tmp_path: Path) -> None:
    explicit = tmp_path / "operator"
    resolution = resolve_state_root(_installed_inputs(tmp_path / "user-data", CADRUMO_LOCAL_STORAGE_ROOT=str(explicit)))
    assert resolution.storage_root == explicit.resolve()
    assert resolution.platform_user_data_root == _installed_default(tmp_path / "user-data")


def test_installed_mode_with_a_repository_root_is_refused(tmp_path: Path) -> None:
    inputs = StateRootInputs(platform=sys.platform, environ={}, home=tmp_path, mode=StorageMode.INSTALLED)
    with pytest.raises(ValueError, match="installed state root has no repository root"):
        resolve_state_root(inputs.model_copy(update={"repository_root": tmp_path}))


def test_fresh_cadrumo_state_is_resolved_and_reused(tmp_path: Path) -> None:
    """A fresh root remains the sole Cadrumo state root after a write."""
    inputs = _state_root_inputs_under(tmp_path)
    first = resolve_state_root(inputs)
    first.storage_root.mkdir(parents=True)
    marker = first.storage_root / "fresh-state.marker"
    marker.write_text("cadrumo", encoding="utf-8")

    second = resolve_state_root(inputs)
    assert second.storage_root == tmp_path / "var" / "storage"
    assert marker.read_text(encoding="utf-8") == "cadrumo"
    assert not (tmp_path / "aeat").exists()


def test_settings_tree_follows_the_explicit_storage_root(tmp_path: Path) -> None:
    """A fresh Settings tree follows the explicit platform storage root."""
    resolution = resolve_state_root(_state_root_inputs_under(tmp_path))
    with isolated_aeat_env():
        settings = settings_without_env_file(cadrumo_local_storage_root=resolution.storage_root)

    state_tree = (
        settings.cadrumo_local_storage_root,
        settings.cadrumo_token_dir,
        settings.cadrumo_log_dir,
        settings.cadrumo_secret_store_dir,
        settings.cadrumo_blob_store_dir,
        settings.cadrumo_live_state_dir,
    )
    for path in state_tree:
        assert path is not None
        assert resolution.platform_user_data_root in path.parents or path == resolution.storage_root
        assert resolution.storage_root in path.parents or path == resolution.storage_root
