"""State-root derivation for secure storage substrate settings."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...tests import REPO_ROOT
from ...tests.env_scope import isolated_aeat_env, settings_without_env_file
from ..config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _settings_from_env(**env: str) -> Settings:
    with isolated_aeat_env(**env):
        return settings_without_env_file()


def _assert_shared_storage_dirs(settings: Settings, storage_root: Path) -> None:
    assert settings.cadrumo_blob_store_dir == storage_root / "blobs"
    assert settings.cadrumo_audit_dir == storage_root / "audit"


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
