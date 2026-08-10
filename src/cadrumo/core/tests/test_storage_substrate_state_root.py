"""State-root derivation for secure storage substrate settings.

The ``"secrets"``, ``"blobs"``, and ``"live-state"`` literals at the
default-derivation assertions are deliberate: each is the independent oracle
for what its settings field (``cadrumo_secret_store_dir``,
``cadrumo_blob_store_dir``, ``cadrumo_live_state_dir``) defaults to when
unoverridden, not scaffolding. Re-deriving any of them from the taxonomy would
make the assertion compare the settings derivation against itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from ...tests import REPO_ROOT
from ...tests.env_scope import isolated_aeat_env, settings_without_env_file
from ..config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"secrets", "blobs", "live-state"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring.

``"live-state"`` here names the on-disk directory segment
``cadrumo_live_state_dir`` resolves to (``storage_root / "live-state"``).
"""


def _settings_from_env(**env: str) -> Settings:
    with isolated_aeat_env(**env):
        return settings_without_env_file()


def _assert_shared_storage_dirs(settings: Settings, storage_root: Path) -> None:
    assert settings.cadrumo_blob_store_dir == storage_root / "blobs"
    assert settings.cadrumo_live_state_dir == storage_root / "live-state"


def test_secure_storage_dirs_default_under_local_storage_root(tmp_path: Path) -> None:
    storage_root = tmp_path / "state"

    settings = _settings_from_env(CADRUMO_LOCAL_STORAGE_ROOT=str(storage_root))

    assert settings.cadrumo_secret_store_dir == storage_root / "secrets"
    _assert_shared_storage_dirs(settings, storage_root)
    assert settings.cadrumo_secret_store_dir != REPO_ROOT / "var" / "secrets"


def test_explicit_secret_store_dir_env_override_wins(tmp_path: Path) -> None:
    storage_root = tmp_path / "state"
    explicit_secret_store = tmp_path / "operator-secrets"

    settings = _settings_from_env(
        CADRUMO_LOCAL_STORAGE_ROOT=str(storage_root),
        CADRUMO_SECRET_STORE_DIR=str(explicit_secret_store),
    )

    assert settings.cadrumo_secret_store_dir == explicit_secret_store
    _assert_shared_storage_dirs(settings, storage_root)
