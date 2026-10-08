"""Repository defaults and environment-controlled storage relocation."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...tests.env_scope import isolated_aeat_env
from .. import storage_environment as storage_environment_module
from ..config import Settings
from ..config_state_root import default_storage_root, live_state_root_inputs, platform_user_data_root
from ..errors.hierarchy import CoreValidationError
from ..storage_environment import (
    PROCESS_ENVIRONMENT,
    STORAGE_ROOT,
    TOOL_STORAGE_LOCATIONS,
    ChildEnvironmentProfile,
    StorageMode,
    StorageModeEvidence,
    child_environment,
    configured_storage_root,
    detect_storage_mode,
    development_tool_env_var_names,
    product_env_var_names,
    storage_directory,
)
from ..storage_taxonomy import (
    STORAGE_ROOT_SETTINGS_FIELD,
    FingerprintParticipation,
    StorageCategory,
    StorageGrouping,
    StorageLifecycle,
    StorageOverridePolicy,
)
from ..storage_taxonomy_locations import STORAGE_TAXONOMY, storage_location, storage_path
from .checkout import project_root

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
        "CADRUMO_LOCAL_STORAGE_ROOT",
        "CADRUMO_TEMP_DIR",
        "CADRUMO_RUNTIME_SOCKET_DIR",
        "CADRUMO_OLLAMA_HOME_DIR",
    } <= controls
    # The development root variable is honoured only in a checkout; children inherit the pinned root.
    assert STORAGE_ROOT.development_variable not in controls
    assert "CADRUMO_SECRET_PASSPHRASE" not in controls
    assert "CADRUMO_CERTIFICATE_PASSWORD_SECRET" not in controls
    assert "CADRUMO_CLAVE_PERMANENTE_PASSWORD" not in controls
    assert "CADRUMO_AUTH_PROVIDER" not in controls


def test_checkout_module_is_development_from_any_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    evidence = detect_storage_mode(Path(storage_environment_module.__file__))
    assert evidence == StorageModeEvidence(StorageMode.DEVELOPMENT, project_root())
    assert (project_root() / "pyproject.toml").is_file()


def test_module_outside_a_checkout_is_installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    site = tmp_path / "Lib" / "site-packages"
    module = site.joinpath(*STORAGE_ROOT.checkout_module[1:])
    module.parent.mkdir(parents=True)
    module.write_bytes(Path(storage_environment_module.__file__).read_bytes())
    # A marker beside the package is not a checkout: the module must sit at src/<package>/core.
    (site / STORAGE_ROOT.checkout_marker).write_text("[project]\n", encoding="utf-8")
    monkeypatch.chdir(project_root())
    assert detect_storage_mode(module) == StorageModeEvidence(StorageMode.INSTALLED, None)


def test_checkout_layout_without_marker_is_installed(tmp_path: Path) -> None:
    module = tmp_path.joinpath(*STORAGE_ROOT.checkout_module)
    module.parent.mkdir(parents=True)
    module.write_bytes(Path(storage_environment_module.__file__).read_bytes())
    assert detect_storage_mode(module).mode is StorageMode.INSTALLED
    (tmp_path / STORAGE_ROOT.checkout_marker).write_text("[project]\n", encoding="utf-8")
    assert detect_storage_mode(module) == StorageModeEvidence(StorageMode.DEVELOPMENT, tmp_path.resolve())


def test_allowlist_split_separates_product_controls_from_development_tools() -> None:
    product = product_env_var_names()
    development = development_tool_env_var_names()
    overridable = {
        location.settings_field.upper()
        for location in STORAGE_TAXONOMY.values()
        if location.override_policy is StorageOverridePolicy.OPERATOR_OVERRIDABLE and location.settings_field
    }
    assert {"CADRUMO_LOCAL_STORAGE_ROOT", "CADRUMO_WEBVIEW_DIR", "CADRUMO_TEMP_DIR"} <= product
    assert product == overridable | {"CADRUMO_LOCAL_STORAGE_ROOT"}
    assert "CADRUMO_STORAGE_ROOT" not in product
    assert development == {variable for variable, _default in TOOL_STORAGE_LOCATIONS.values()}
    assert "CADRUMO_TOOL_CACHE_DIR" in development
    assert not product & development
    assert not {"XDG_CACHE_HOME", "UV_CACHE_DIR"} & (product | development)
    assert Settings.storage_env_var_names() == product


def test_desktop_webview_member_defaults_beneath_the_root_and_follows_its_setting(tmp_path: Path) -> None:
    location = storage_location(StorageCategory.DESKTOP_WEBVIEW)
    assert (location.subpath, location.settings_field) == ("webview", "cadrumo_webview_dir")
    assert location.override_policy is StorageOverridePolicy.OPERATOR_OVERRIDABLE
    assert location.grouping is StorageGrouping.CACHE
    assert location.lifecycle is StorageLifecycle.UNBOUNDED_BY_DESIGN
    assert location.fingerprint_participation is FingerprintParticipation.EXCLUDED
    root = tmp_path / "root"
    explicit = tmp_path / "profiles"
    with isolated_aeat_env(CADRUMO_LOCAL_STORAGE_ROOT=str(root)):
        assert storage_path(StorageCategory.DESKTOP_WEBVIEW, settings=Settings()) == root / "webview"
    with isolated_aeat_env(CADRUMO_LOCAL_STORAGE_ROOT=str(root), CADRUMO_WEBVIEW_DIR=str(explicit)):
        assert storage_path(StorageCategory.DESKTOP_WEBVIEW, settings=Settings()) == explicit


def _received(tmp_path: Path) -> dict[str, str]:
    return {
        "PATH": "ambient-path",
        "SYSTEMROOT": "ambient-system-root",
        "CADRUMO_STORAGE_ROOT": str(tmp_path / "shared"),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "inherited"),
        "CADRUMO_TEMP_DIR": "worker-temp",
        "CADRUMO_LOG_DIR": str(tmp_path / "logs"),
        "CADRUMO_UV_CACHE_DIR": str(tmp_path / "uv"),
        "CADRUMO_SECRET_PASSPHRASE": "must-not-cross",
        "CADRUMO_LLM_OPENAI_API_KEY": "must-not-cross",
        "AEAT_STATUS_DETAIL_URL_TEMPLATE": "must-not-cross",
        "PYTHONPATH": "must-not-cross",
        "LD_PRELOAD": "must-not-cross",
        "VIRTUAL_ENV": "must-not-cross",
        "CADRUMO_AUTHORITY_ROOT": str(tmp_path / "authority"),
        "XDG_CACHE_HOME": str(tmp_path / "pinned-cache"),
    }


def test_operator_child_keeps_allowlisted_overrides_and_pins_the_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    received = _received(tmp_path)
    environment = child_environment(ChildEnvironmentProfile.OPERATOR, root, received=received, sys_platform="win32")
    temporary = str((root / "worker-temp").resolve())
    assert environment == {
        "PATH": "ambient-path",
        "SYSTEMROOT": "ambient-system-root",
        "CADRUMO_LOCAL_STORAGE_ROOT": str(root.resolve()),
        "CADRUMO_TEMP_DIR": "worker-temp",
        "CADRUMO_LOG_DIR": str(tmp_path / "logs"),
        "CADRUMO_AUTHORITY_ROOT": str(tmp_path / "authority"),
        "XDG_CACHE_HOME": str(tmp_path / "pinned-cache"),
        "TEMP": temporary,
        "TMP": temporary,
        "TMPDIR": temporary,
    }
    assert (root / "worker-temp").is_dir()


def test_strict_child_carries_only_pins_and_host_inherited_values(tmp_path: Path) -> None:
    root = tmp_path / "neutral" / "state"
    received = _received(tmp_path)
    environment = child_environment(
        ChildEnvironmentProfile.STRICT, root, received=received, base={}, sys_platform="win32"
    )
    temporary = str((root / "tmp").resolve())
    assert environment == {
        "CADRUMO_LOCAL_STORAGE_ROOT": str(root.resolve()),
        "CADRUMO_AUTHORITY_ROOT": str(tmp_path / "authority"),
        "TEMP": temporary,
        "TMP": temporary,
        "TMPDIR": temporary,
    }
    ambient = child_environment(ChildEnvironmentProfile.STRICT, root, received=received, sys_platform="win32")
    assert set(ambient) == {*environment, "PATH", "SYSTEMROOT", "XDG_CACHE_HOME"}
    assert ambient["XDG_CACHE_HOME"] == received["XDG_CACHE_HOME"]


@pytest.mark.parametrize("profile", list(ChildEnvironmentProfile))
def test_packaged_pywin32_cache_resolves_beneath_the_root_without_a_host_pin(
    tmp_path: Path, profile: ChildEnvironmentProfile
) -> None:
    location = storage_location(StorageCategory.PYWIN32_GENERATED_CACHE)
    assert location.override_policy is StorageOverridePolicy.FIXED
    assert location.settings_field is None
    root = (tmp_path / "root").resolve()
    assert root.joinpath(location.relative_path()) == root / "cache" / "pywin32" / "gen_py"
    received = {"XDG_CACHE_HOME": str(tmp_path / "former-cache-pin")}
    for sys_platform in ("win32", "linux"):
        environment = child_environment(profile, root, received=received, base={}, sys_platform=sys_platform)
        assert "XDG_CACHE_HOME" not in environment
        assert environment[STORAGE_ROOT.variable] == str(root)


def test_pinned_names_and_precedence_come_from_the_declaration() -> None:
    assert (STORAGE_ROOT.variable, *PROCESS_ENVIRONMENT.temporary_variables) == (
        "CADRUMO_LOCAL_STORAGE_ROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
    )
    assert STORAGE_ROOT.precedence == ("CADRUMO_LOCAL_STORAGE_ROOT", "CADRUMO_STORAGE_ROOT")
    assert STORAGE_ROOT.root_variables(StorageMode.INSTALLED) == ("CADRUMO_LOCAL_STORAGE_ROOT",)
    assert STORAGE_ROOT_SETTINGS_FIELD == "cadrumo_local_storage_root"


@pytest.mark.parametrize("profile", list(ChildEnvironmentProfile))
def test_child_refuses_relative_pin_without_creating_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: ChildEnvironmentProfile
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(CoreValidationError, match="absolute storage root pin"):
        child_environment(profile, Path("relative-state"), received={})
    assert not (tmp_path / "relative-state").exists()


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_child_environment_uses_platform_variable_case_rules(tmp_path: Path, platform: str) -> None:
    root = tmp_path / "state"
    received = {
        "Path": "ambient",
        "pythonpath": "lower-case-value",
        "dyld_insert_libraries": "lower-case-loader",
        "DYLD_INSERT_LIBRARIES": "blocked-loader",
        STORAGE_ROOT.variable.lower(): "must-not-replace-pin",
        "CADRUMO_TEMP_DIR".lower(): "alternate-temp",
        "CADRUMO_AUTHORITY_ROOT".lower(): str(tmp_path / "authority-pin"),
    }
    environment = child_environment(ChildEnvironmentProfile.OPERATOR, root, received=received, sys_platform=platform)
    assert environment[STORAGE_ROOT.variable] == str(root.resolve())
    assert "DYLD_INSERT_LIBRARIES" not in environment
    if platform == "win32":
        assert "pythonpath" not in environment and "PYTHONPATH" not in environment
        assert "DYLD_INSERT_LIBRARIES" not in environment
        assert environment["PATH"] == "ambient"
        assert environment["CADRUMO_AUTHORITY_ROOT"] == str(tmp_path / "authority-pin")
        assert environment["TEMP"] == str(root / "alternate-temp")
        assert STORAGE_ROOT.variable.lower() not in environment
    else:
        assert environment["pythonpath"] == "lower-case-value"
        assert environment["dyld_insert_libraries"] == "lower-case-loader"
        assert environment["Path"] == "ambient"
        assert "CADRUMO_AUTHORITY_ROOT" not in environment
        assert environment["TEMP"] == str(root / "tmp")
