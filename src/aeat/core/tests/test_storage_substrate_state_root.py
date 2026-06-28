"""State-root derivation for secure storage substrate settings."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...tests.env_scope import isolated_aeat_env
from ..config import PROJECT_ROOT, Settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _settings_from_env(**env: str) -> Settings:
    with isolated_aeat_env(**env):
        return Settings(_env_file=None)


def test_secure_storage_dirs_default_under_local_storage_root(tmp_path: Path) -> None:
    storage_root = tmp_path / "state"

    settings = _settings_from_env(AEAT_LOCAL_STORAGE_ROOT=str(storage_root))

    assert settings.aeat_secret_store_dir == storage_root / "secrets"
    assert settings.aeat_blob_store_dir == storage_root / "blobs"
    assert settings.aeat_audit_dir == storage_root / "audit"
    assert settings.aeat_secret_store_dir != PROJECT_ROOT / "var" / "secrets"


def test_explicit_secret_store_dir_env_override_wins(tmp_path: Path) -> None:
    storage_root = tmp_path / "state"
    explicit_secret_store = tmp_path / "operator-secrets"

    settings = _settings_from_env(
        AEAT_LOCAL_STORAGE_ROOT=str(storage_root),
        AEAT_SECRET_STORE_DIR=str(explicit_secret_store),
    )

    assert settings.aeat_secret_store_dir == explicit_secret_store
    assert settings.aeat_blob_store_dir == storage_root / "blobs"
    assert settings.aeat_audit_dir == storage_root / "audit"
