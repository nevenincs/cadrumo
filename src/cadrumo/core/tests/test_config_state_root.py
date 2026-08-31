"""Tests for platform-user-data storage state-root resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...tests import REPO_ROOT
from ...tests.env_scope import isolated_aeat_env, settings_without_env_file
from .._config_state_root import (
    FormerProductStateError,
    StateRootInputs,
    live_state_root_inputs,
    platform_user_data_root,
    resolve_state_root,
)
from ..storage_taxonomy import StorageCategory, storage_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _state_root_inputs_under(base: Path, *, platform: str = "win32") -> StateRootInputs:
    """Build deterministic state-root inputs whose platform base is ``base``."""
    if platform == "win32":
        environ = {"LOCALAPPDATA": str(base)}
    elif platform == "linux":
        environ = {"XDG_DATA_HOME": str(base)}
    else:
        environ = {}
    return StateRootInputs(platform=platform, environ=environ, home=base / "home")


def test_storage_root_derives_every_substrate_dir(tmp_path: Path) -> None:
    """Every substrate directory follows the platform root and none escapes to the checkout.

    Which subpath each one lands on is :mod:`test_output_dir_state_root`'s
    oracle and is deliberately not restated here -- five name equalities in
    this module were a strict duplicate of that table.

    What is left is the property the oracle does not own: each substrate
    category resolves *beneath* the resolved root, and beneath the checkout
    never. That is not the accessor agreeing with itself. A derivation
    validator that failed to fire leaves the field carrying its
    ``REPO_ROOT/var`` placeholder, which fails both halves at once -- which is
    the regression this test has always existed to catch.
    """
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
        assert REPO_ROOT not in derived.parents, category


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


def test_the_live_default_follows_the_captured_platform_inputs(tmp_path: Path) -> None:
    """The default is the platform user-data storage dir for the captured inputs.

    Driven through the injectable seam rather than the ambient process. The
    live default legitimately REFUSES on a host carrying retired ``aeat``
    state (see the former-product test below), and that refusal is a property
    of the developer's machine, not of the resolver — asserting against the
    live process would make this test pass or fail on whether the person
    running it once installed the retired product.

    Captures the live inputs only to confirm the seam reflects the real
    process shape, then resolves against a clean base.
    """
    live = live_state_root_inputs()
    assert live.platform, "the live seam must capture a real platform string"

    inputs = _state_root_inputs_under(tmp_path / "AppData")

    assert resolve_state_root(inputs).storage_root == platform_user_data_root(inputs) / "storage"


def test_repository_markers_do_not_change_platform_resolution(tmp_path: Path) -> None:
    """Repository-shaped files have no bearing on the platform storage root."""
    project_root = tmp_path / "repo"
    project_root.mkdir()
    (project_root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (project_root / ".git").write_text("gitdir: ../elsewhere\n", encoding="utf-8")
    inputs = _state_root_inputs_under(tmp_path / "AppData")
    resolution = resolve_state_root(inputs)
    assert resolution.storage_root == platform_user_data_root(inputs) / "storage"
    assert project_root not in resolution.storage_root.parents


def test_platform_resolution_lands_under_platform_user_data(tmp_path: Path) -> None:
    """Every supported platform resolves under ``<base>/cadrumo/storage``."""
    failures: list[str] = []
    for platform in ("win32", "linux", "darwin"):
        inputs = _state_root_inputs_under(tmp_path / platform, platform=platform)
        resolution = resolve_state_root(inputs)
        if resolution.platform_user_data_root.name != "cadrumo":
            failures.append(f"{platform}: user_data_root={resolution.platform_user_data_root}")
        if resolution.storage_root != resolution.platform_user_data_root / "storage":
            failures.append(f"{platform}: storage_root={resolution.storage_root}")
        if REPO_ROOT in resolution.storage_root.parents:
            failures.append(f"{platform}: storage root landed under REPO_ROOT")
    assert not failures, "\n".join(failures)


def test_windows_localappdata_falls_back_to_appdata_local_when_unset(tmp_path: Path) -> None:
    """Windows with no ``%LOCALAPPDATA%`` uses ``~/AppData/Local/cadrumo``."""
    inputs = StateRootInputs(platform="win32", environ={}, home=tmp_path / "home")
    resolution = resolve_state_root(inputs)
    assert resolution.storage_root == (tmp_path / "home" / "AppData" / "Local" / "cadrumo" / "storage")


def test_relative_platform_env_base_is_ignored(tmp_path: Path) -> None:
    """A relative ``$XDG_DATA_HOME`` falls back to the platform default."""
    inputs = StateRootInputs(
        platform="linux",
        environ={"XDG_DATA_HOME": "relative/not/absolute"},
        home=tmp_path / "home",
    )
    resolution = resolve_state_root(inputs)
    assert resolution.storage_root == (tmp_path / "home" / ".local" / "share" / "cadrumo" / "storage")


def test_fresh_cadrumo_state_is_resolved_and_reused(tmp_path: Path) -> None:
    """A fresh root remains the sole Cadrumo state root after a write."""
    inputs = _state_root_inputs_under(tmp_path)
    first = resolve_state_root(inputs)
    first.storage_root.mkdir(parents=True)
    marker = first.storage_root / "fresh-state.marker"
    marker.write_text("cadrumo", encoding="utf-8")

    second = resolve_state_root(inputs)
    assert second.storage_root == tmp_path / "cadrumo" / "storage"
    assert marker.read_text(encoding="utf-8") == "cadrumo"
    assert not (tmp_path / "aeat").exists()


def test_resolution_refuses_former_product_state_without_touching_it(tmp_path: Path) -> None:
    """Recognizable retired ``aeat`` state is refused without mutation."""
    former_storage = tmp_path / "aeat" / "storage"
    former_storage.mkdir(parents=True)
    marker = former_storage / "opaque-state.bin"
    marker.write_bytes(b"former-product-state")
    inputs = _state_root_inputs_under(tmp_path)

    with pytest.raises(FormerProductStateError, match="will not read, move, re-key, delete, or adopt"):
        resolve_state_root(inputs)

    assert marker.read_bytes() == b"former-product-state"
    assert former_storage.is_dir()
    assert not (tmp_path / "cadrumo").exists()


def test_settings_tree_never_lands_under_repository_root(tmp_path: Path) -> None:
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
        assert REPO_ROOT not in path.parents
        assert path != REPO_ROOT / "var" / "storage"
