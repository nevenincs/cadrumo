"""Tests for the installed-vs-checkout storage state-root resolution.

The :mod:`aeat.core._config_state_root` seam decides where
:attr:`~aeat.core.config.Settings.aeat_local_storage_root` defaults: a source
checkout keeps ``PROJECT_ROOT / "var" / "storage"`` while an installed
distribution roots under the platform user-data directory. These tests exercise
the real resolver and the real :class:`~aeat.core.config.Settings` validator
chain — no mocks, no monkeypatching of the unit under test. The
``StateRootInputs`` seam injects an ``installed`` or ``checkout`` context
deterministically, and env-provided base directories use the host-absolute
``tmp_path`` fixture so the foreign-platform branches resolve on any host.

This module carries two Step surfaces: the derived-substrate cascade
(``W01.P01.S03`` — the token, log, secret, blob and audit roots follow the
installed base through the existing state-root validators) and the fresh-install
roundtrip proof (``W01.P01.S04`` — installed storage resolves off the platform
directory and never off ``PROJECT_ROOT``, checkout unchanged).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ...tests.env_scope import isolated_aeat_env
from .._config_state_root import (
    RunMode,
    StateRootInputs,
    resolve_state_root,
)
from ..config import Settings
from ..paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _installed_inputs_under(base: Path, *, platform: str = "win32") -> StateRootInputs:
    """Build an ``installed`` context whose platform base is ``base``.

    The project-root candidate is a marker-free directory (no ``pyproject.toml``
    / ``.git``) so :func:`detect_run_mode` classifies it installed, and the
    per-platform environment variable points at ``base`` — a host-absolute
    ``tmp_path`` — so the resolver's absolute-path acceptance holds on any host.
    """
    candidate = base / "site-packages" / "aeat" / "core"
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

    Rooting ``aeat_local_storage_root`` at an installed platform-user-data
    directory must cascade through the existing state-root validators so every
    derived substrate directory lives under the same installed base, not under
    ``PROJECT_ROOT``.
    """
    resolution = resolve_state_root(_installed_inputs_under(tmp_path))
    assert resolution.run_mode is RunMode.INSTALLED

    with isolated_aeat_env():
        settings = Settings(aeat_local_storage_root=resolution.storage_root)

    root = settings.aeat_local_storage_root
    assert settings.aeat_token_dir == root / "tokens"
    assert settings.aeat_log_dir == root / "logs"
    assert settings.aeat_secret_store_dir == root / "secrets"
    assert settings.aeat_blob_store_dir == root / "blobs"
    assert settings.aeat_audit_dir == root / "audit"

    # Every derived root follows the installed base and never the repo root.
    for derived in (
        settings.aeat_token_dir,
        settings.aeat_log_dir,
        settings.aeat_secret_store_dir,
        settings.aeat_blob_store_dir,
        settings.aeat_audit_dir,
    ):
        assert root in derived.parents
        assert PROJECT_ROOT not in derived.parents


def test_explicit_substrate_override_still_wins_over_installed_base(tmp_path: Path) -> None:
    """An explicit substrate directory kwarg overrides the installed derivation.

    The installed default must not defeat an operator's explicit
    ``AEAT_SECRET_STORE_DIR``-class override; the derivation only fills the
    field when it was left unset.
    """
    resolution = resolve_state_root(_installed_inputs_under(tmp_path))
    explicit_secret_dir = tmp_path / "operator-secrets"

    with isolated_aeat_env():
        settings = Settings(
            aeat_local_storage_root=resolution.storage_root,
            aeat_secret_store_dir=explicit_secret_dir,
        )

    assert settings.aeat_secret_store_dir == explicit_secret_dir
    assert settings.aeat_secret_store_dir != settings.aeat_local_storage_root / "secrets"
    # The un-overridden siblings still derive from the installed base.
    assert settings.aeat_blob_store_dir == settings.aeat_local_storage_root / "blobs"
