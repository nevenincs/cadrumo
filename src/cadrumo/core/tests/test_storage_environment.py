"""The one storage root: its variable, its per-user default and how children inherit it."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from ...tests.env_scope import isolated_aeat_env
from ..config import Settings
from ..config_state_root import default_storage_root, live_state_root_inputs, platform_user_data_root
from ..errors.hierarchy import CoreValidationError
from ..storage_environment import (
    STORAGE_ROOT,
    TEMPORARY_FILES_SUBPATH,
    TEMPORARY_VARIABLES,
    TOOL_STORAGE_LOCATIONS,
    ChildEnvironmentProfile,
    child_environment,
    configured_storage_root,
    host_installed_default_root,
    relayed_setting_names,
    storage_directory,
    tool_storage_environment,
    withheld_child_settings,
)
from ..storage_taxonomy import STORAGE_ROOT_SETTINGS_FIELD, StorageCategory
from ..storage_taxonomy_locations import STORAGE_TAXONOMY, storage_location, storage_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _user_environment(tmp_path: Path) -> dict[str, str]:
    """A per-user environment that names every platform's base directory under ``tmp_path``."""
    return {
        "LOCALAPPDATA": str(tmp_path / "local-app-data"),
        "XDG_DATA_HOME": str(tmp_path / "xdg-data"),
        "HOME": str(tmp_path / "home"),
        "USERPROFILE": str(tmp_path / "home"),
    }


def _expected_default(environment: dict[str, str]) -> Path:
    if sys.platform == "win32":
        return Path(environment["LOCALAPPDATA"]) / "cadrumo"
    if sys.platform == "darwin":
        return Path(environment["HOME"]) / "Library" / "Application Support" / "cadrumo"
    return Path(environment["XDG_DATA_HOME"]) / "cadrumo"


def test_unset_root_is_the_per_user_default_whatever_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment = _user_environment(tmp_path)
    monkeypatch.chdir(tmp_path)
    with isolated_aeat_env():
        assert configured_storage_root(environ=environment) == _expected_default(environment)
        assert host_installed_default_root(environment) == _expected_default(environment)
        assert default_storage_root() == configured_storage_root()
        assert platform_user_data_root(live_state_root_inputs()) == default_storage_root()


def test_the_variable_relocates_every_member_beneath_it(tmp_path: Path) -> None:
    root = tmp_path / "relocated"
    with isolated_aeat_env(CADRUMO_STORAGE_ROOT=str(root), CADRUMO_DEV_CACHE_ROOT=""):
        settings = Settings()
        assert configured_storage_root() == root
        assert settings.cadrumo_storage_root == root
        for category in (
            StorageCategory.LOGS,
            StorageCategory.TEMPORARY_FILES,
            StorageCategory.TOKENS,
            StorageCategory.PLAYWRIGHT_BROWSERS,
        ):
            assert storage_path(category, settings=settings) == root / storage_location(category).relative_path()
        assert storage_location(StorageCategory.TEMPORARY_FILES).relative_path() == Path(TEMPORARY_FILES_SUBPATH)
        assert storage_directory("CADRUMO_DEV_CACHE_ROOT", "development/cache") == root / "development" / "cache"


def test_a_removed_member_variable_changes_nothing(tmp_path: Path) -> None:
    root = tmp_path / "root"
    with isolated_aeat_env(
        CADRUMO_STORAGE_ROOT=str(root),
        CADRUMO_LOG_DIR=str(tmp_path / "elsewhere"),
        CADRUMO_TEMP_DIR=str(tmp_path / "scratch"),
    ):
        settings = Settings()
        assert storage_path(StorageCategory.LOGS, settings=settings) == root / "logs"
        assert storage_path(StorageCategory.TEMPORARY_FILES, settings=settings) == root / TEMPORARY_FILES_SUBPATH


def test_a_blank_root_is_unset() -> None:
    with isolated_aeat_env(CADRUMO_STORAGE_ROOT=" \t"):
        assert Settings().cadrumo_storage_root == default_storage_root()


@pytest.mark.parametrize(
    ("relative", "refusal"),
    [
        ("var/alternate", "relative_override_installed"),
        ("./state", "relative_override_installed"),
        ("state", "relative_override_installed"),
        ("~other/state", "invalid_path_input"),
    ],
)
def test_a_relative_root_is_refused(relative: str, refusal: str) -> None:
    with isolated_aeat_env(CADRUMO_STORAGE_ROOT=relative), pytest.raises(CoreValidationError) as raised:
        Settings()
    assert raised.value.context is not None
    assert raised.value.context["storage_root_refusal"] == refusal


def test_the_only_location_setting_is_the_root() -> None:
    controls = Settings.storage_env_var_names()
    assert controls == frozenset({"CADRUMO_STORAGE_ROOT"})
    assert {"CADRUMO_TEMP_DIR", "CADRUMO_LOG_DIR", "CADRUMO_RUNTIME_SOCKET_DIR"}.isdisjoint(Settings.env_var_names())
    assert "CADRUMO_SECRET_PASSPHRASE" not in controls
    assert "CADRUMO_CERTIFICATE_PASSWORD_SECRET" not in controls
    assert "CADRUMO_CLAVE_PERMANENTE_PASSWORD" not in controls
    assert "CADRUMO_AUTH_PROVIDER" not in controls


def test_location_settings_are_separate_from_development_tools() -> None:
    product = Settings.storage_env_var_names()
    development = frozenset(variable for variable, _default in TOOL_STORAGE_LOCATIONS.values())
    assert product == {STORAGE_ROOT.variable}
    assert "CADRUMO_TOOL_CACHE_DIR" in development
    assert not product & development
    assert not {"XDG_CACHE_HOME", "UV_CACHE_DIR"} & (product | development)
    assert not any(name.startswith("CADRUMO_UV_") for name in development)
    assert not {"UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR", "UV_TOOL_DIR", "UV_TOOL_BIN_DIR"} & set(TOOL_STORAGE_LOCATIONS)
    proxy = {"CADRUMO_PROXY_URL", "CADRUMO_PROXY_USERNAME", "CADRUMO_PROXY_BYPASS"}
    assert relayed_setting_names() == product | {"CADRUMO_AUTHORITY_ROOT"} | proxy


def test_uv_global_paths_remain_owned_by_the_machine_and_uv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    machine_paths = {
        "UV_CACHE_DIR": str(tmp_path / "machine-cache"),
        "UV_PYTHON_INSTALL_DIR": str(tmp_path / "machine-python"),
        "UV_TOOL_DIR": str(tmp_path / "machine-tools"),
        "UV_TOOL_BIN_DIR": str(tmp_path / "machine-tool-bin"),
    }
    retired_controls = {
        "CADRUMO_UV_CACHE_DIR": str(tmp_path / "retired-cache"),
        "CADRUMO_UV_PYTHON_DIR": str(tmp_path / "retired-python"),
        "CADRUMO_UV_TOOL_DIR": str(tmp_path / "retired-tools"),
        "CADRUMO_UV_TOOL_BIN_DIR": str(tmp_path / "retired-tool-bin"),
    }
    for name, value in {**machine_paths, **retired_controls}.items():
        monkeypatch.setenv(name, value)

    managed = tool_storage_environment()
    child = {**os.environ, **managed}
    for name in retired_controls:
        monkeypatch.delenv(name)
    without_retired_controls = tool_storage_environment()

    assert not set(machine_paths) & managed.keys()
    assert {name: child[name] for name in machine_paths} == machine_paths
    assert managed == without_retired_controls
    assert not set(retired_controls) & {variable for variable, _default in TOOL_STORAGE_LOCATIONS.values()}


def _received(tmp_path: Path) -> dict[str, str]:
    return {
        "PATH": "ambient-path",
        "SYSTEMROOT": "ambient-system-root",
        "CADRUMO_STORAGE_ROOT": str(tmp_path / "inherited"),
        "CADRUMO_TEMP_DIR": "worker-temp",
        "CADRUMO_LOG_DIR": str(tmp_path / "logs"),
        "CADRUMO_UV_CACHE_DIR": str(tmp_path / "uv"),
        "CADRUMO_SECRET_PASSPHRASE": "must-not-cross",
        "CADRUMO_LLM_OPENAI_API_KEY": "must-not-cross",
        "AEAT_SEDE_EXPEDIENTES_PATH": "must-not-cross",
        "PYTHONPATH": "must-not-cross",
        "LD_PRELOAD": "must-not-cross",
        "VIRTUAL_ENV": "must-not-cross",
        "CADRUMO_AUTHORITY_ROOT": str(tmp_path / "authority"),
        "XDG_CACHE_HOME": str(tmp_path / "pinned-cache"),
    }


def test_operator_child_drops_member_variables_and_pins_the_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    received = _received(tmp_path)
    environment = child_environment(ChildEnvironmentProfile.OPERATOR, root, received=received, sys_platform="win32")
    temporary = str((root / TEMPORARY_FILES_SUBPATH).resolve())
    assert environment == {
        "PATH": "ambient-path",
        "SYSTEMROOT": "ambient-system-root",
        "CADRUMO_STORAGE_ROOT": str(root.resolve()),
        "CADRUMO_AUTHORITY_ROOT": str(tmp_path / "authority"),
        "XDG_CACHE_HOME": str(tmp_path / "pinned-cache"),
        # Interpreter and loader names are not settings of this command line;
        # a packaged image's host defines them, and outside a package they pass.
        "PYTHONPATH": "must-not-cross",
        "LD_PRELOAD": "must-not-cross",
        "VIRTUAL_ENV": "must-not-cross",
        "TEMP": temporary,
        "TMP": temporary,
        "TMPDIR": temporary,
    }
    assert (root / TEMPORARY_FILES_SUBPATH).is_dir()


def test_strict_child_carries_only_pins_and_the_authority_root(tmp_path: Path) -> None:
    root = tmp_path / "neutral" / "state"
    received = _received(tmp_path)
    environment = child_environment(
        ChildEnvironmentProfile.STRICT, root, received=received, base={}, sys_platform="win32"
    )
    temporary = str((root / "tmp").resolve())
    assert environment == {
        "CADRUMO_STORAGE_ROOT": str(root.resolve()),
        "CADRUMO_AUTHORITY_ROOT": str(tmp_path / "authority"),
        "TEMP": temporary,
        "TMP": temporary,
        "TMPDIR": temporary,
    }
    ambient = child_environment(ChildEnvironmentProfile.STRICT, root, received=received, sys_platform="win32")
    assert set(ambient) == {
        *environment,
        "PATH",
        "SYSTEMROOT",
        "XDG_CACHE_HOME",
        "PYTHONPATH",
        "LD_PRELOAD",
        "VIRTUAL_ENV",
    }
    assert ambient["XDG_CACHE_HOME"] == received["XDG_CACHE_HOME"]


@pytest.mark.parametrize("profile", list(ChildEnvironmentProfile))
def test_packaged_pywin32_cache_resolves_beneath_the_root_without_a_host_pin(
    tmp_path: Path, profile: ChildEnvironmentProfile
) -> None:
    location = storage_location(StorageCategory.PYWIN32_GENERATED_CACHE)
    assert location.scope is STORAGE_TAXONOMY[StorageCategory.PYWIN32_GENERATED_CACHE].scope
    root = (tmp_path / "root").resolve()
    assert root.joinpath(location.relative_path()) == root / "cache" / "pywin32" / "gen_py"
    received = {"XDG_CACHE_HOME": str(tmp_path / "former-cache-pin")}
    for sys_platform in ("win32", "linux"):
        environment = child_environment(profile, root, received=received, base={}, sys_platform=sys_platform)
        assert "XDG_CACHE_HOME" not in environment
        assert environment[STORAGE_ROOT.variable] == str(root)


def test_pinned_names_come_from_the_declaration() -> None:
    assert (STORAGE_ROOT.variable, *TEMPORARY_VARIABLES) == (
        "CADRUMO_STORAGE_ROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
    )
    assert STORAGE_ROOT_SETTINGS_FIELD == "cadrumo_storage_root"


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
        "CADRUMO_AUTHORITY_ROOT".lower(): str(tmp_path / "authority-pin"),
    }
    environment = child_environment(ChildEnvironmentProfile.OPERATOR, root, received=received, sys_platform=platform)
    assert environment[STORAGE_ROOT.variable] == str(root.resolve())
    if platform == "win32":
        assert "pythonpath" not in environment
        assert environment["PYTHONPATH"] == "lower-case-value"
        assert environment["PATH"] == "ambient"
        assert environment["CADRUMO_AUTHORITY_ROOT"] == str(tmp_path / "authority-pin")
        assert environment["TEMP"] == str(root / "tmp")
        assert STORAGE_ROOT.variable.lower() not in environment
    else:
        assert environment["pythonpath"] == "lower-case-value"
        assert environment["dyld_insert_libraries"] == "lower-case-loader"
        assert environment["DYLD_INSERT_LIBRARIES"] == "blocked-loader"
        assert environment["Path"] == "ambient"
        assert "CADRUMO_AUTHORITY_ROOT" not in environment
        assert environment["TEMP"] == str(root / "tmp")


def test_operator_child_follows_the_operators_proxy_but_never_receives_the_password_setting(tmp_path: Path) -> None:
    root = tmp_path / "root"
    proxy = {
        "CADRUMO_PROXY_URL": "http://lane:synthetic-proxy-word@127.0.0.1:3128",
        "CADRUMO_PROXY_USERNAME": "lane",
        "CADRUMO_PROXY_BYPASS": "example.invalid",
        "CADRUMO_PROXY_PASSWORD_SECRET": "must-not-cross",
    }
    received = {**_received(tmp_path), **proxy}
    operator = child_environment(ChildEnvironmentProfile.OPERATOR, root, received=received, sys_platform="win32")
    assert {name: operator.get(name) for name in proxy} == {
        **proxy,
        "CADRUMO_PROXY_PASSWORD_SECRET": None,
    }
    strict = child_environment(ChildEnvironmentProfile.STRICT, root, received=received, sys_platform="win32")
    assert not any(name.startswith("CADRUMO_PROXY_") for name in strict)
    assert "CADRUMO_PROXY_URL" in relayed_setting_names()
    assert "CADRUMO_PROXY_PASSWORD_SECRET" not in relayed_setting_names()


def test_a_process_holding_the_proxy_withholds_it_from_the_environment_its_children_inherit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    word = "synthetic-proxy-word"
    monkeypatch.setenv("CADRUMO_PROXY_URL", f"http://lane:{word}@127.0.0.1:3128")
    monkeypatch.setenv("CADRUMO_PROXY_PASSWORD_SECRET", word)
    monkeypatch.setenv("CADRUMO_LOG_DIR", "kept")
    with withheld_child_settings():
        assert not any(name.upper().startswith("CADRUMO_PROXY_") for name in os.environ)
        assert os.environ["CADRUMO_LOG_DIR"] == "kept"
    assert os.environ["CADRUMO_PROXY_URL"] == f"http://lane:{word}@127.0.0.1:3128"
    assert os.environ["CADRUMO_PROXY_PASSWORD_SECRET"] == word
