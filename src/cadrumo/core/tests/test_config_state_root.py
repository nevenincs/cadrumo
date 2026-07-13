"""Tests for the installed-vs-checkout storage state-root resolution.

The :mod:`cadrumo.core._config_state_root` seam decides where
:attr:`~cadrumo.core.config.Settings.cadrumo_local_storage_root` defaults: a source
checkout keeps ``PROJECT_ROOT / "var" / "storage"`` while an installed
distribution roots under the platform user-data directory. These tests exercise
the real resolver and the real :class:`~cadrumo.core.config.Settings` validator
chain — no mocks, no monkeypatching of the unit under test. The
``StateRootInputs`` seam injects an ``installed`` or ``checkout`` context
deterministically, and env-provided base directories use the host-absolute
``tmp_path`` fixture so the foreign-platform branches resolve on any host.

The tests cover both the derived-substrate cascade and the fresh-install
roundtrip: token, log, secret, blob, and audit roots follow the installed base,
installed storage resolves off the platform directory, and checkout storage
remains under ``PROJECT_ROOT``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...tests.env_scope import isolated_aeat_env, settings_without_env_file
from .._config_state_root import (
    FormerProductStateError,
    RunMode,
    StateRootInputs,
    default_storage_root,
    detect_run_mode,
    platform_user_data_root,
    resolve_state_root,
)
from ..paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _installed_inputs_under(base: Path, *, platform: str = "win32") -> StateRootInputs:
    """Build an ``installed`` context whose platform base is ``base``.

    The project-root candidate is a marker-free directory (no ``pyproject.toml``
    / ``.git``) so :func:`detect_run_mode` classifies it installed, and the
    per-platform environment variable points at ``base`` — a host-absolute
    ``tmp_path`` — so the resolver's absolute-path acceptance holds on any host.
    """
    candidate = base / "site-packages" / "cadrumo" / "core"
    if platform == "win32":
        environ = {"LOCALAPPDATA": str(base)}
    elif platform == "linux":
        environ = {"XDG_DATA_HOME": str(base)}
    else:
        environ = {}
    return StateRootInputs(
        project_root_candidate=candidate,
        platform=platform,
        environ=environ,
        home=base / "home",
    )


def test_installed_storage_root_derives_every_substrate_dir(tmp_path: Path) -> None:
    """The token, log, secret, blob and audit roots follow the installed base.

    Rooting ``cadrumo_local_storage_root`` at an installed platform-user-data
    directory must cascade through the existing state-root validators so every
    derived substrate directory lives under the same installed base, not under
    ``PROJECT_ROOT``.
    """
    resolution = resolve_state_root(_installed_inputs_under(tmp_path))
    assert resolution.run_mode is RunMode.INSTALLED

    with isolated_aeat_env():
        settings = settings_without_env_file(cadrumo_local_storage_root=resolution.storage_root)

    root = settings.cadrumo_local_storage_root
    assert settings.cadrumo_token_dir == root / "tokens"
    assert settings.cadrumo_log_dir == root / "logs"
    assert settings.cadrumo_secret_store_dir == root / "secrets"
    assert settings.cadrumo_blob_store_dir == root / "blobs"
    assert settings.cadrumo_audit_dir == root / "audit"

    # Every derived root follows the installed base and never the repo root.
    for derived in (
        settings.cadrumo_token_dir,
        settings.cadrumo_log_dir,
        settings.cadrumo_secret_store_dir,
        settings.cadrumo_blob_store_dir,
        settings.cadrumo_audit_dir,
    ):
        # cadrumo_log_dir is declared Optional (an explicit CADRUMO_LOG_DIR override
        # could stay None), but this construction leaves it unset, so the
        # `_resolve_output_dirs_under_storage_root` validator always roots it - the
        # assertion below is real test coverage of that resolution, not just a
        # narrowing hack.
        assert derived is not None
        assert root in derived.parents
        assert PROJECT_ROOT not in derived.parents


def test_explicit_substrate_override_still_wins_over_installed_base(tmp_path: Path) -> None:
    """An explicit substrate directory kwarg overrides the installed derivation.

    The installed default must not defeat an operator's explicit
    ``CADRUMO_SECRET_STORE_DIR``-class override; the derivation only fills the
    field when it was left unset.
    """
    resolution = resolve_state_root(_installed_inputs_under(tmp_path))
    explicit_secret_dir = tmp_path / "operator-secrets"

    with isolated_aeat_env():
        settings = settings_without_env_file(
            cadrumo_local_storage_root=resolution.storage_root,
            cadrumo_secret_store_dir=explicit_secret_dir,
        )

    assert settings.cadrumo_secret_store_dir == explicit_secret_dir
    assert settings.cadrumo_secret_store_dir != settings.cadrumo_local_storage_root / "secrets"
    # The un-overridden siblings still derive from the installed base.
    assert settings.cadrumo_blob_store_dir == settings.cadrumo_local_storage_root / "blobs"


def test_live_default_is_the_checkout_var_storage_root() -> None:
    """The running checkout keeps the historical ``PROJECT_ROOT/var/storage`` default.

    The state-root resolution must be behaviour-preserving for the dev loop:
    this test suite runs from a source checkout, so the live default factory
    must resolve exactly to the pre-change value and classify as a checkout.
    """
    assert default_storage_root() == PROJECT_ROOT / "var" / "storage"


def test_checkout_markers_beat_a_present_platform_env(tmp_path: Path) -> None:
    """A marker-bearing project root resolves to ``var/storage`` even with env set.

    Anti-tautology proof that the detector genuinely keys on the repository
    markers, not on the absence of a platform variable: a real ``pyproject.toml``
    and ``.git`` marker at the candidate root force ``CHECKOUT`` while
    ``LOCALAPPDATA`` is populated, and the checkout root — never the platform
    base — owns the resolved storage directory.
    """
    project_root = tmp_path / "repo"
    project_root.mkdir()
    (project_root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (project_root / ".git").write_text("gitdir: ../elsewhere\n", encoding="utf-8")

    inputs = StateRootInputs(
        project_root_candidate=project_root,
        platform="win32",
        environ={"LOCALAPPDATA": str(tmp_path / "AppData")},
        home=tmp_path / "home",
    )
    resolution = resolve_state_root(inputs)

    assert detect_run_mode(inputs) is RunMode.CHECKOUT
    assert resolution.storage_root == project_root / "var" / "storage"
    assert platform_user_data_root(inputs) not in resolution.storage_root.parents


def test_installed_resolution_lands_off_project_root(tmp_path: Path) -> None:
    """Every platform's installed run resolves under ``<base>/cadrumo/storage``.

    A marker-free candidate under a fake ``site-packages`` classifies installed
    and the storage root lands under the platform user-data base, never under
    the project-root candidate it was detected from and never under the repo
    ``PROJECT_ROOT``.
    """
    failures: list[str] = []
    for platform in ("win32", "linux", "darwin"):
        inputs = _installed_inputs_under(tmp_path / platform, platform=platform)
        resolution = resolve_state_root(inputs)
        if resolution.run_mode is not RunMode.INSTALLED:
            failures.append(f"{platform}: run_mode={resolution.run_mode!r}")
        if resolution.platform_user_data_root.name != "cadrumo":
            failures.append(f"{platform}: user_data_root={resolution.platform_user_data_root}")
        if resolution.storage_root != resolution.platform_user_data_root / "storage":
            failures.append(f"{platform}: storage_root={resolution.storage_root}")
        if PROJECT_ROOT in resolution.storage_root.parents:
            failures.append(f"{platform}: storage root landed under PROJECT_ROOT")
        if inputs.project_root_candidate in resolution.storage_root.parents:
            failures.append(f"{platform}: storage root landed under detected project candidate")

    assert not failures, "\n".join(failures)


def test_windows_localappdata_falls_back_to_appdata_local_when_unset(tmp_path: Path) -> None:
    """Windows with no ``%LOCALAPPDATA%`` roots under ``~/AppData/Local/cadrumo``."""
    inputs = StateRootInputs(
        project_root_candidate=tmp_path / "site-packages" / "cadrumo",
        platform="win32",
        environ={},
        home=tmp_path / "home",
    )
    resolution = resolve_state_root(inputs)

    assert resolution.run_mode is RunMode.INSTALLED
    assert resolution.storage_root == (tmp_path / "home" / "AppData" / "Local" / "cadrumo" / "storage")


def test_relative_platform_env_base_is_ignored(tmp_path: Path) -> None:
    """A non-absolute ``$XDG_DATA_HOME`` is ignored per the XDG spec.

    A relative environment value must not become the base; the resolver falls
    back to ``~/.local/share`` so a malformed override never plants the store at
    a cwd-relative location.
    """
    inputs = StateRootInputs(
        project_root_candidate=tmp_path / "site-packages" / "cadrumo",
        platform="linux",
        environ={"XDG_DATA_HOME": "relative/not/absolute"},
        home=tmp_path / "home",
    )
    resolution = resolve_state_root(inputs)

    assert resolution.storage_root == (tmp_path / "home" / ".local" / "share" / "cadrumo" / "storage")


def test_fresh_installed_cadrumo_state_is_resolved_and_reused(tmp_path: Path) -> None:
    """A fresh installed root is Cadrumo-owned and remains the sole state root."""
    inputs = _installed_inputs_under(tmp_path)
    first = resolve_state_root(inputs)

    first.storage_root.mkdir(parents=True)
    marker = first.storage_root / "fresh-state.marker"
    marker.write_text("cadrumo", encoding="utf-8")

    second = resolve_state_root(inputs)
    assert second.storage_root == tmp_path / "cadrumo" / "storage"
    assert marker.read_text(encoding="utf-8") == "cadrumo"
    assert not (tmp_path / "aeat").exists()


def test_installed_resolution_refuses_former_product_state_without_touching_it(tmp_path: Path) -> None:
    """Recognizable retired ``aeat`` state is refused without adoption or mutation."""
    former_storage = tmp_path / "aeat" / "storage"
    former_storage.mkdir(parents=True)
    marker = former_storage / "opaque-state.bin"
    marker.write_bytes(b"former-product-state")
    inputs = _installed_inputs_under(tmp_path)

    with pytest.raises(FormerProductStateError, match="will not read, move, re-key, delete, or adopt"):
        resolve_state_root(inputs)

    assert marker.read_bytes() == b"former-product-state"
    assert former_storage.is_dir()
    assert not (tmp_path / "cadrumo").exists()


def test_fresh_install_settings_tree_never_lands_under_project_root(tmp_path: Path) -> None:
    """A fresh installed run's full Settings state tree resolves off ``PROJECT_ROOT``.

    The roundtrip proof: resolve an installed storage root, build a real
    ``Settings`` from it, and confirm the encrypted-store root and every derived
    substrate directory land under the platform base and never inside the repo
    tree — the defect this change closes.
    """
    resolution = resolve_state_root(_installed_inputs_under(tmp_path))

    with isolated_aeat_env():
        settings = settings_without_env_file(cadrumo_local_storage_root=resolution.storage_root)

    state_tree = (
        settings.cadrumo_local_storage_root,
        settings.cadrumo_token_dir,
        settings.cadrumo_log_dir,
        settings.cadrumo_secret_store_dir,
        settings.cadrumo_blob_store_dir,
        settings.cadrumo_audit_dir,
    )
    for path in state_tree:
        # cadrumo_log_dir is declared Optional, but this construction leaves it
        # unset, so the resolution validator always roots it - see the same
        # note in test_installed_storage_root_derives_every_substrate_dir above.
        assert path is not None
        assert resolution.platform_user_data_root in path.parents or path == resolution.storage_root
        assert PROJECT_ROOT not in path.parents
        assert path != PROJECT_ROOT / "var" / "storage"
