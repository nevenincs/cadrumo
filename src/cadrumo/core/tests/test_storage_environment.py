"""Repository defaults and environment-controlled storage relocation."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...tests.env_scope import isolated_aeat_env
from ..config import Settings
from ..config_state_root import default_storage_root, live_state_root_inputs, platform_user_data_root
from ..storage_environment import configured_storage_root, project_root, storage_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_unset_root_defaults_to_repository_even_from_another_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = project_root()
    monkeypatch.chdir(tmp_path)
    with isolated_aeat_env():
        assert default_storage_root() == repository / "var" / "storage"
        assert platform_user_data_root(live_state_root_inputs()) == repository


def test_shared_root_relocates_settings_and_relative_refinements(tmp_path: Path) -> None:
    root = tmp_path / "relocated"
    with isolated_aeat_env(CADRUMO_STORAGE_ROOT=str(root), CADRUMO_LOG_DIR="diagnostics", CADRUMO_DEV_CACHE_ROOT=""):
        settings = Settings()
        assert configured_storage_root() == root
        assert settings.cadrumo_local_storage_root == root
        assert settings.cadrumo_log_dir == root / "diagnostics"
        assert settings.cadrumo_temp_dir == root / "tmp"
        assert settings.cadrumo_runtime_socket_dir == root / "runtime"
        assert settings.cadrumo_playwright_browsers_dir == root / "components" / "playwright"
        assert storage_directory("CADRUMO_DEV_CACHE_ROOT", "development/cache") == root / "development" / "cache"


def test_local_refinement_and_absolute_member_override_win(tmp_path: Path) -> None:
    local = tmp_path / "backend"
    logs = tmp_path / "logs"
    with isolated_aeat_env(
        CADRUMO_STORAGE_ROOT=str(tmp_path / "shared"),
        CADRUMO_LOCAL_STORAGE_ROOT=str(local),
        CADRUMO_LOG_DIR=str(logs),
    ):
        settings = Settings()
        assert configured_storage_root() == local
        assert settings.cadrumo_local_storage_root == local
        assert settings.cadrumo_log_dir == logs
        assert settings.cadrumo_token_dir == local / "tokens"


def test_blank_overrides_are_unset_and_relative_root_anchors_to_repository() -> None:
    with isolated_aeat_env(
        CADRUMO_STORAGE_ROOT=" var/alternate ", CADRUMO_LOCAL_STORAGE_ROOT=" \t", CADRUMO_TEMP_DIR=" "
    ):
        settings = Settings()
        root = project_root() / "var" / "alternate"
        assert settings.cadrumo_local_storage_root == root
        assert settings.cadrumo_temp_dir == root / "tmp"


def test_isolated_launch_allowlist_carries_storage_controls_without_credentials() -> None:
    controls = Settings.storage_env_var_names()
    assert {
        "CADRUMO_STORAGE_ROOT",
        "CADRUMO_TEMP_DIR",
        "CADRUMO_RUNTIME_SOCKET_DIR",
        "CADRUMO_OLLAMA_HOME_DIR",
    } <= controls
    assert "CADRUMO_SECRET_PASSPHRASE" not in controls
    assert "CADRUMO_CERTIFICATE_PASSWORD_SECRET" not in controls
    assert "CADRUMO_CLAVE_PERMANENTE_PASSWORD" not in controls
    assert "CADRUMO_AUTH_PROVIDER" not in controls
